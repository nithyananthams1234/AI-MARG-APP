
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


AIJobType = Literal[
    "observation_analysis",
    "learning_gap_analysis",
    "recommendation_generation",
    "action_plan_suggestion",
]


class AIJobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_type: AIJobType
    entity_type: str = Field(min_length=1, max_length=100)
    entity_id: UUID
    # For observation_analysis the backend builds the input from the database;
    # any client-supplied payload is ignored for that job type.
    input_payload: dict[str, Any] = Field(default_factory=dict)


class AIFindingSuggestion(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str
    category: str = Field(min_length=1, max_length=100)
    confidence: float = Field(ge=0, le=1)
    evidence_reference: str | None = None


class AILearningGapSuggestion(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str
    subject: str | None = None
    grade: str | None = None
    severity: Literal["low", "medium", "high", "critical"]


class AIRecommendationSuggestion(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str
    rationale: str
    category: str = Field(min_length=1, max_length=100)


class AISource(BaseModel):
    document: str
    title: str | None = None
    page: int
    relevance: float | None = None
    excerpt: str | None = None


class AIStrength(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    evidence: str = Field(min_length=1)


class AIPriorityImprovement(BaseModel):
    """Private mentor analysis for one priority area (max three per analysis)."""

    area: str = Field(min_length=1, max_length=120)
    evidence: str = Field(min_length=1)
    possible_reason: str | None = None  # a hypothesis, never a fact
    recommendation: str = Field(min_length=1)
    # The only part of this item that may appear in the teacher message.
    teacher_suggestion: str = Field(min_length=1, max_length=600)


TeacherResponseType = Literal["agreement", "clarification", "support_needed", "different_perspective"]


class AITeacherResponseOption(BaseModel):
    """A *suggested* reply the teacher could send. Never an actual reply."""

    type: TeacherResponseType
    label: str = Field(min_length=1, max_length=80)
    response: str = Field(min_length=1, max_length=500)


class AITeacherCommunicationPoint(BaseModel):
    area: str
    suggestion: str


class AITeacherCommunication(BaseModel):
    """Ready-to-edit message from the mentor to the teacher.

    Built by the backend only from the teacher-facing suggestions, so the
    private analysis (evidence, possible reasons, findings) is never in it.
    """

    greeting: str
    intro: str
    improvement_points: list[AITeacherCommunicationPoint]
    closing: str
    message: str
    teacher_name_available: bool


class AIAnalysisResponse(BaseModel):
    summary: str
    findings: list[AIFindingSuggestion] = Field(default_factory=list)
    learning_gaps: list[AILearningGapSuggestion] = Field(default_factory=list)
    recommendations: list[AIRecommendationSuggestion] = Field(
        default_factory=list
    )
    # Mentor analysis sections (private to the mentor).
    strengths: list[AIStrength] = Field(default_factory=list, max_length=3)
    priority_improvements: list[AIPriorityImprovement] = Field(default_factory=list, max_length=3)
    follow_up_actions: list[str] = Field(default_factory=list, max_length=3)
    # Teacher-facing draft + suggested teacher replies (added by the backend).
    teacher_communication: AITeacherCommunication | None = None
    teacher_response_options: list[AITeacherResponseOption] = Field(default_factory=list, max_length=4)
    # Retrieved knowledge-base passages that grounded the analysis (if any).
    sources: list[AISource] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None


# ---- Teacher communication workflow (mentor-approved sharing + actual replies)

class TeacherCommunicationShareRequest(BaseModel):
    """Record that the mentor approved and shared (or copied) the message.

    The backend never sends anything itself; this is an audit record of the
    exact text the mentor approved.
    """

    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=3000)
    channel: Literal["whatsapp", "copy", "share_sheet", "other"]
    mentor_approved: bool


class TeacherResponseCreate(BaseModel):
    """An *actual* reply from the teacher, entered by the mentor."""

    model_config = ConfigDict(extra="forbid")

    response_text: str = Field(min_length=2, max_length=3000)
    response_type: Literal[
        "agreement", "clarification", "support_needed", "different_perspective", "other"
    ] = "other"
    # Explicit confirmation that this is what the teacher really said, so a
    # suggested option is never recorded as a reply by accident.
    confirmed_actual_reply: bool


class TeacherNextStepsResponse(BaseModel):
    response_id: str
    answer: str
    sources: list[AISource] = Field(default_factory=list)
    grounded: bool
    model: str | None = None


class AIRecommendationSelection(BaseModel):
    index: int = Field(ge=0)
    # Link to a learning gap created from this job (index into
    # learning_gap_indexes order) OR an existing learning gap id.
    learning_gap_index: int | None = Field(default=None, ge=0)
    learning_gap_id: UUID | None = None


class AIJobApplyRequest(BaseModel):
    """Mentor-selected suggestions to record as *ai_suggested* records.

    Nothing becomes official here: every created finding / recommendation
    keeps status ``ai_suggested`` and must still be approved by the mentor.
    """

    model_config = ConfigDict(extra="forbid")

    finding_indexes: list[int] = Field(default_factory=list, max_length=10)
    learning_gap_indexes: list[int] = Field(default_factory=list, max_length=10)
    recommendations: list[AIRecommendationSelection] = Field(default_factory=list, max_length=10)


class AIJobApplyResponse(BaseModel):
    finding_ids: list[UUID]
    learning_gap_ids: list[UUID]
    recommendation_ids: list[UUID]


class AIJobResponse(BaseModel):
    id: UUID
    job_type: str
    entity_type: str | None
    entity_id: UUID | None
    status: Literal[
        "queued",
        "processing",
        "completed",
        "failed",
        "cancelled",
    ]
    result_payload: dict[str, Any] | None
    error_message: str | None
    created_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
