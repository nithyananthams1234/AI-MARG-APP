"""Registry of consequential actions agents may *propose*.

The autonomy level comes from this registry, never from agent or model output. Agents cannot
execute these actions; the approval engine executes them only after a human approval.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.common import AutonomyLevel


@dataclass(frozen=True)
class ActionSpec:
    name: str
    description: str
    level: AutonomyLevel
    external: bool  # True = must be executed by the MARG application, not by the engine


ACTIONS: dict[str, ActionSpec] = {
    "reschedule_visit": ActionSpec(
        "reschedule_visit",
        "Move a planned school visit to a new time",
        AutonomyLevel.proposed,
        external=False,
    ),
    "schedule_visit": ActionSpec(
        "schedule_visit", "Create a planned school visit", AutonomyLevel.proposed, external=False
    ),
    "update_task_due_date": ActionSpec(
        "update_task_due_date", "Change a task's due date", AutonomyLevel.proposed, external=False
    ),
    "send_teacher_message": ActionSpec(
        "send_teacher_message",
        "Send an approved message draft to a teacher (delivered by the MARG application, never by the engine)",
        AutonomyLevel.explicit,
        external=True,
    ),
}
