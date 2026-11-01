# MARG Mentor Intelligence Engine - demonstration script (DEMO DATA)
# Prerequisites: the API is running (uv run uvicorn app.main:app) and demo data is seeded.
# Usage (PowerShell):  .\scripts\demo.ps1            or  .\scripts\demo.ps1 -BaseUrl http://127.0.0.1:8000
# API key: if -ApiKey is omitted, ENGINE_API_KEY is taken from the environment, then from the project .env
# (same precedence as the server). The key value is never printed.
param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$ApiKey = "",
    [string]$EnvFile = (Join-Path (Split-Path -Parent $PSScriptRoot) ".env")
)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
. (Join-Path $PSScriptRoot "lib\DemoAuth.ps1")

$auth = Resolve-EngineApiKey -ExplicitKey $ApiKey -EnvFile $EnvFile
$H = New-DemoHeaders -ActorRef "MEN-001" -ApiKey $auth.Key
if ($auth.Key) { "API key: sent in X-API-Key (source: {0})" -f $auth.Source } else { "API key: not sent (none configured)" }

trap {
    $status = $null
    if ($_.Exception.Response) { $status = [int]$_.Exception.Response.StatusCode }
    if ($status -eq 401) {
        Write-Host "HTTP 401 from the engine. The X-API-Key sent (source: $($auth.Source)) does not match the running server." -ForegroundColor Red
        Write-Host "Check ENGINE_API_KEY in .env, then restart the server: it reads .env only at startup." -ForegroundColor Red
    }
    break
}

function Step($title) { Write-Host ""; Write-Host "=== $title ===" -ForegroundColor Cyan }
function Post($path, $body) {
    Invoke-RestMethod -Method Post -Uri "$BaseUrl$path" -Headers $H -ContentType "application/json; charset=utf-8" `
        -Body ([System.Text.Encoding]::UTF8.GetBytes(($body | ConvertTo-Json -Depth 10)))
}
function Get-Api($path) { Invoke-RestMethod -Method Get -Uri "$BaseUrl$path" -Headers $H }

Step "1. Health"
$ready = Invoke-RestMethod "$BaseUrl/health/ready"
"status={0} database={1}/{2} ai={3} backend={4}" -f $ready.status, $ready.checks.database.database, `
    $ready.checks.database.schema, $ready.checks.ai_provider.status, $ready.checks.backend.mode

$info = (Get-Api "/api/v1/demo/info").data
$day = $info.anchor_date
"Demo anchor date (seed data is relative to it): $day"

Step "2. Task prioritisation (deterministic score; incomplete when inputs are missing)"
$r = (Post "/api/v1/tasks/prioritise" @{ mentor_ref = "MEN-001" }).data
"execution={0} status={1} ai_status={2}" -f $r.execution_id, $r.status, $r.ai_status
$r.result.facts.tasks | Select-Object -First 8 rank, task_ref, @{n="priority";e={$_.priority.priority}}, `
    @{n="score";e={$_.priority.score}}, @{n="missing";e={$_.priority.missing_factors -join ","}}, next_action | Format-Table -AutoSize

Step "3. Daily plan for $day"
$r = (Post "/api/v1/plans/daily" @{ mentor_ref = "MEN-001"; date = $day }).data
$r.result.facts.timeline | Select-Object @{n="start";e={$_.start.Substring(11,5)}}, @{n="end";e={$_.end.Substring(11,5)}}, ref, title, source | Format-Table -AutoSize
"Cannot fit / not schedulable:"
$r.result.facts.cannot_fit_or_not_schedulable | Select-Object ref, reason | Format-Table -AutoSize
if ($r.result.ai_insights) { "AI overview: " + $r.result.ai_insights.content.overview }

Step "4. Workload analysis (7 days)"
$r = (Post "/api/v1/workload/analysis" @{ mentor_ref = "MEN-001"; start_date = $day }).data
$w = $r.result.facts.workload
"Workload index={0}% status={1} lower_bound={2} overloaded_days={3}" -f $w.workload_index, $w.status, $w.index_is_lower_bound, ($w.overloaded_days -join ",")

Step "5. Schedule conflicts and reschedule proposals"
$r = (Post "/api/v1/schedule/analysis" @{ mentor_ref = "MEN-001"; start_date = $day }).data
$r.result.facts.conflicts | Where-Object { $_.type -eq "overlap" } | Select-Object entries, detail | Format-Table -AutoSize -Wrap
$proposal = $r.result.proposals | Select-Object -First 1
if ($proposal) { "Proposal {0}: {1} {2} -> {3} [{4}]" -f $proposal.proposal_id, $proposal.action_type, $proposal.target_ref, $proposal.payload.new_start, $proposal.status }

Step "6. Follow-up analysis"
$r = (Post "/api/v1/followups/analysis" @{ mentor_ref = "MEN-001" }).data
$r.result.facts.counts | Format-List

Step "7. School visit planning"
$r = (Post "/api/v1/school-visits/plan" @{ mentor_ref = "MEN-001"; start_date = $day }).data
$r.result.facts.recommended_visits | Select-Object school_ref, @{n="score";e={$_.attention.attention_score}}, `
    @{n="slot";e={$_.suggested_slot.start}}, slot_note | Format-Table -AutoSize

Step "8. Communication draft (Tamil) - NOT sent"
$r = (Post "/api/v1/communications/drafts" @{ mentor_ref = "MEN-001"; followup_ref = "FU-001"; language = "ta" }).data
"generated_by=" + $r.result.facts.draft.generated_by
$r.result.facts.draft.body
$msgProposal = $r.result.proposals[0]
"Send proposal {0}: level={1} status={2}" -f $msgProposal.proposal_id, $msgProposal.autonomy_level, $msgProposal.status

Step "9. Weekly plan and weekly report"
$r = (Post "/api/v1/plans/weekly" @{ mentor_ref = "MEN-001"; week_start = $day }).data
"Deadlines this week: " + (($r.result.facts.deadlines_this_week | ForEach-Object { $_.task_ref }) -join ", ")
$r = (Post "/api/v1/reports" @{ mentor_ref = "MEN-001"; period = "weekly" }).data
"Records: completed={0} open={1} overdue={2}" -f $r.result.facts.records.tasks_completed.Count, $r.result.facts.records.tasks_open, $r.result.facts.records.tasks_overdue.Count

Step "10. Approval workflow"
if ($proposal) {
    $a = (Post "/api/v1/proposals/$($proposal.proposal_id)/approve" @{ note = "Approved during demo" }).data
    "Reschedule proposal after approval: status={0} result={1}" -f $a.status, ($a.execution_result | ConvertTo-Json -Compress)
}
$m = (Post "/api/v1/proposals/$($msgProposal.proposal_id)/approve" @{ note = "OK to send" }).data
"Message proposal after approval: status={0} (delivery is done by the MARG application, never by the engine)" -f $m.status

Step "11. Duplicate request protection"
$first = Post "/api/v1/time/analysis" @{ mentor_ref = "MEN-001"; start_date = $day }
$again = Post "/api/v1/time/analysis" @{ mentor_ref = "MEN-001"; start_date = $day }
"First: replayed={0}  Second: replayed={1}  same execution: {2}" -f $first.meta.replayed, $again.meta.replayed, `
    ($first.data.execution_id -eq $again.data.execution_id)

Step "12. Cross-mentor access is denied"
try { Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/tasks/prioritise" -Headers $H -ContentType "application/json" -Body '{"mentor_ref":"MEN-002"}' | Out-Null; "UNEXPECTED: allowed" }
catch { "Denied as expected: HTTP " + $_.Exception.Response.StatusCode.value__ }

Write-Host ""; Write-Host "Demo complete. API documentation: $BaseUrl/docs" -ForegroundColor Green
