# Helpers for scripts/demo.ps1: resolve ENGINE_API_KEY the same way the server does.
# Precedence (matches the server): explicit -ApiKey > ENGINE_API_KEY environment variable > project .env file.
# Key values are never written to the console.

function Read-DotEnvValue {
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)][string]$Name)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    $value = $null
    # UTF-8 with BOM detection; works for LF and CRLF files.
    foreach ($line in [System.IO.File]::ReadAllLines((Resolve-Path -LiteralPath $Path).Path, [System.Text.Encoding]::UTF8)) {
        $text = $line.Trim()
        if (-not $text -or $text.StartsWith("#")) { continue }
        if ($text.StartsWith("export ")) { $text = $text.Substring(7).TrimStart() }
        $eq = $text.IndexOf("=")
        if ($eq -lt 1 -or $text.Substring(0, $eq).Trim() -ne $Name) { continue }
        $raw = $text.Substring($eq + 1).Trim()
        if ($raw.Length -ge 2 -and ($raw[0] -eq '"' -or $raw[0] -eq "'")) {
            $close = $raw.IndexOf($raw[0], 1)
            $raw = if ($close -gt 0) { $raw.Substring(1, $close - 1) } else { $raw.Substring(1) }
        } else {
            $raw = $raw -replace '(^|\s+)#.*$', ''   # inline comment (unquoted values), as python-dotenv does
        }
        $value = $raw.Trim()                          # last occurrence wins, as in python-dotenv
    }
    return $value
}

function Resolve-EngineApiKey {
    param([string]$ExplicitKey = "", [string]$EnvFile = "")
    if ($ExplicitKey -and $ExplicitKey.Trim()) {
        return @{ Key = $ExplicitKey.Trim(); Source = "-ApiKey parameter" }
    }
    if ($env:ENGINE_API_KEY -and $env:ENGINE_API_KEY.Trim()) {
        return @{ Key = $env:ENGINE_API_KEY.Trim(); Source = "ENGINE_API_KEY environment variable" }
    }
    if ($EnvFile) {
        $fromFile = Read-DotEnvValue -Path $EnvFile -Name "ENGINE_API_KEY"
        if ($fromFile) { return @{ Key = $fromFile; Source = ".env file" } }
    }
    return @{ Key = ""; Source = "none configured" }
}

function New-DemoHeaders {
    param([Parameter(Mandatory)][string]$ActorRef, [string]$ApiKey = "")
    $headers = @{ "X-Actor-Ref" = $ActorRef }
    if ($ApiKey) { $headers["X-API-Key"] = $ApiKey }
    return $headers
}
