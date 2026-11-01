"""Task Intelligence Agent: deadlines, dependencies, deterministic priority, missing inputs, next action."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.base_agent import AgentContext, AgentInput, Analysis, BaseAgent, keep_known
from app.providers.base import ComplexityHint, DataSection, LLMRequest
from app.schemas.common import MissingData, TaskStatus
from app.services.planning import priorities_for
from app.services.priority import OPEN_STATUSES, analyse_dependencies, rank_tasks
from app.utils.datetime_utils import fmt_local


class TaskPrioritisationInput(AgentInput):
    include_closed: bool = Field(default=False, description="Also list completed/cancelled tasks")


class NextActionInsight(BaseModel):
    task_ref: str
    recommendation: str = Field(max_length=400)
    reason: str = Field(max_length=400)


class TaskInsights(BaseModel):
    summary: str = Field(max_length=1200)
    next_actions: list[NextActionInsight] = Field(max_length=10)
    cautions: list[str] = Field(default_factory=list, max_length=6)


class TaskIntelligenceAgent(BaseAgent[TaskPrioritisationInput]):
    agent_id = "task_intelligence"
    description = "Calculates deterministic task priorities, detects dependencies and missing inputs, suggests next actions"
    input_model = TaskPrioritisationInput
    prompt_id = "task_intelligence"
    insight_model = TaskInsights
    complexity = ComplexityHint.standard

    def analyse(self, ctx: AgentContext, inp: TaskPrioritisationInput) -> Analysis:
        s, now, tz = ctx.snapshot, ctx.now, ctx.tz
        results = priorities_for(
            s, now, ctx.settings.deadline_horizon_days, ctx.settings.dependency_points_per_blocked_task
        )
        deps = analyse_dependencies(s.tasks)
        ranking = rank_tasks(results, s.tasks, now)
        by_id = {t.id: t for t in s.tasks}
        missing: list[MissingData] = []
        tasks_out = []
        for r in ranking:
            t, res = by_id[r["task_ref"]], results[r["task_ref"]]
            for f in res.missing_factors:
                missing.append(
                    MissingData(
                        entity_type="task",
                        entity_ref=t.id,
                        field=f,
                        impact="Priority score not assigned until this input is recorded",
                    )
                )
            if t.estimated_minutes is None:
                missing.append(
                    MissingData(
                        entity_type="task",
                        entity_ref=t.id,
                        field="estimated_minutes",
                        impact="Task cannot be time-planned",
                    )
                )
            tasks_out.append(
                {
                    "rank": r["rank"],
                    "ordering_basis": r["ordering_basis"],
                    "task_ref": t.id,
                    "title": t.title,
                    "category": t.category,
                    "status": t.status.value,
                    "due_at": fmt_local(t.due_at, tz),
                    "overdue": bool(t.due_at and t.due_at < now),
                    "estimated_minutes": t.estimated_minutes,
                    "school_ref": t.school_ref,
                    "priority": res.model_dump(mode="json"),
                    "blocked_by": deps.blocked_by_open.get(t.id, []),
                    "next_action": self._next_action(
                        t.id,
                        res.missing_factors,
                        deps.blocked_by_open.get(t.id, []),
                        bool(t.due_at and t.due_at < now),
                        t.status,
                    ),
                }
            )
        closed = []
        if inp.include_closed:
            closed = [
                {"task_ref": t.id, "title": t.title, "status": t.status.value}
                for t in s.tasks
                if t.status not in OPEN_STATUSES
            ]
        facts = {
            "summary": {
                "open_tasks": len(results),
                "scored": sum(1 for r in results.values() if r.status == "complete"),
                "incomplete_scores": sum(1 for r in results.values() if r.status == "incomplete"),
                "overdue": sum(1 for t in tasks_out if t["overdue"]),
                "by_priority": {
                    p: sum(1 for r in results.values() if r.priority and r.priority.value == p)
                    for p in ("critical", "high", "medium", "low")
                },
            },
            "formula": "0.30*urgency + 0.25*impact + 0.20*risk + 0.15*deadline_proximity + 0.10*workload_dependency",
            "tasks": tasks_out,
            "dependencies": deps.model_dump(),
            "closed_tasks": closed,
        }
        return Analysis(facts=facts, known_refs=set(results), missing_data=missing)

    @staticmethod
    def _next_action(
        ref: str, missing: list[str], blocked_by: list[str], overdue: bool, status: TaskStatus
    ) -> str:
        if blocked_by:
            return f"Complete dependency first: {', '.join(blocked_by)}"
        steps = []
        if overdue:
            steps.append("Overdue - complete it or agree a revised deadline")
        elif status == TaskStatus.in_progress:
            steps.append("Continue and complete")
        else:
            steps.append("Schedule time to start")
        if missing:
            steps.append(f"record missing inputs ({', '.join(missing)})")
        return "; ".join(steps)

    def needs_llm(self, ctx: AgentContext, inp: TaskPrioritisationInput, analysis: Analysis) -> bool:
        return bool(analysis.known_refs)

    def llm_request(self, ctx: AgentContext, inp: TaskPrioritisationInput, analysis: Analysis) -> LLMRequest:
        top = [
            {
                k: t[k]
                for k in ("task_ref", "title", "status", "due_at", "overdue", "blocked_by", "next_action")
            }
            | {
                "score": t["priority"]["score"],
                "priority": t["priority"]["priority"],
                "missing_factors": t["priority"]["missing_factors"],
            }
            for t in analysis.facts["tasks"][:12]
        ]
        return LLMRequest(
            prompt_id=self.prompt_id or "",
            data=[DataSection("prioritised_tasks", top), DataSection("summary", analysis.facts["summary"])],
            instruction=(
                "Explain the ordering in plain language, recommend the next concrete action for up to five "
                "of the most important tasks, and list cautions such as missing inputs or dependencies."
            ),
        )

    def validate_insights(self, insights: TaskInsights, analysis: Analysis) -> TaskInsights:  # type: ignore[override]
        insights.next_actions = keep_known(insights.next_actions, "task_ref", analysis.known_refs)
        return insights
