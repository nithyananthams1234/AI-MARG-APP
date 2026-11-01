"""Agent registry and event routing."""

from __future__ import annotations

from app.agents.base_agent import BaseAgent
from app.agents.communication_agent import CommunicationAgent
from app.agents.followup_agent import FollowupAgent
from app.agents.planning_agents import DailyPlanningAgent, WeeklyPlanningAgent
from app.agents.reporting_agent import ReportingAgent
from app.agents.schedule_agent import ScheduleAgent
from app.agents.school_visit_agent import SchoolVisitPlanningAgent
from app.agents.task_agent import TaskIntelligenceAgent
from app.agents.time_agent import TimeManagementAgent
from app.agents.workload_agent import WorkloadAgent
from app.core.actions import ACTIONS


class UnknownAgentError(LookupError):
    pass


class AgentRegistry:
    def __init__(self, agents: list[BaseAgent]):
        self._agents: dict[str, BaseAgent] = {}
        for agent in agents:
            if agent.agent_id in self._agents:
                raise ValueError(f"Duplicate agent id {agent.agent_id}")
            unknown = agent.allowed_actions - ACTIONS.keys()
            if unknown:
                raise ValueError(f"Agent {agent.agent_id} references unknown actions {unknown}")
            self._agents[agent.agent_id] = agent

    def get(self, agent_id: str) -> BaseAgent:
        try:
            return self._agents[agent_id]
        except KeyError:
            raise UnknownAgentError(f"Unknown agent {agent_id!r}") from None

    def describe(self) -> list[dict]:
        return [
            {
                "agent_id": a.agent_id,
                "version": a.version,
                "description": a.description,
                "uses_claude": a.insight_model is not None,
                "prompt": f"{a.prompt_id}/v1" if a.prompt_id else None,
                "allowed_proposals": sorted(a.allowed_actions),
                "input_schema": a.input_model.model_json_schema(),
            }
            for a in self._agents.values()
        ]


def default_registry() -> AgentRegistry:
    return AgentRegistry(
        [
            TaskIntelligenceAgent(),
            TimeManagementAgent(),
            ScheduleAgent(),
            WorkloadAgent(),
            FollowupAgent(),
            SchoolVisitPlanningAgent(),
            DailyPlanningAgent(),
            WeeklyPlanningAgent(),
            ReportingAgent(),
            CommunicationAgent(),
        ]
    )


# Event type -> (agent, allow Claude). Background events run deterministically to control cost;
# planning triggers may use Claude.
EVENT_ROUTES: dict[str, tuple[str, bool]] = {
    "TASK_CREATED": ("task_intelligence", False),
    "TASK_UPDATED": ("task_intelligence", False),
    "TASK_OVERDUE": ("task_intelligence", False),
    "DEADLINE_APPROACHING": ("task_intelligence", False),
    "TASK_COMPLETED": ("reporting", False),
    "SCHOOL_VISIT_CREATED": ("schedule_intelligence", False),
    "SCHOOL_VISIT_RESCHEDULED": ("schedule_intelligence", False),
    "SCHOOL_VISIT_COMPLETED": ("school_visit_planning", False),
    "FOLLOWUP_CREATED": ("followup_management", False),
    "FOLLOWUP_OVERDUE": ("followup_management", False),
    "TEACHER_RESPONSE_RECEIVED": ("followup_management", False),
    "EVIDENCE_SUBMITTED": ("followup_management", False),
    "VERIFICATION_REQUIRED": ("followup_management", False),
    "SCHEDULE_CONFLICT_DETECTED": ("schedule_intelligence", False),
    "WORKLOAD_THRESHOLD_EXCEEDED": ("workload_intelligence", False),
    "DAILY_PLANNING_TRIGGERED": ("daily_planning", True),
    "WEEKLY_PLANNING_TRIGGERED": ("weekly_planning", True),
}
