"""Request/response contracts of the Classroom Coach API."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ClassroomContext(BaseModel):
    """Optional, non-identifying classroom context supplied by MARG."""

    model_config = ConfigDict(extra="forbid")

    subject: str | None = Field(default=None, max_length=100)
    grade: str | None = Field(default=None, max_length=30)
    topic: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=4000)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=3, max_length=2000, description="Mentor's or teacher's question")
    context: ClassroomContext | None = None


class Source(BaseModel):
    document: str = Field(description="Knowledge-base file id, e.g. '23.pdf'")
    title: str | None = Field(default=None, description="Original document title from the ingestion mapping")
    page: int
    relevance: float = Field(description="1 - cosine distance (higher is more relevant)")
    excerpt: str = Field(description="Beginning of the retrieved passage")


class ChatResponse(BaseModel):
    question: str
    answer: str
    sources: list[Source]
    grounded: bool = Field(description="False when no sufficiently relevant knowledge was retrieved")
    model: str


# ---- Observation analysis (matches the MARG backend AIAnalysisResponse) ----

class FindingSuggestion(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    category: str = Field(min_length=1, max_length=100)
    confidence: float = Field(ge=0, le=1)
    evidence_reference: str | None = Field(
        default=None, description="Quote or paraphrase from the observation notes that supports this finding"
    )


class LearningGapSuggestion(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    subject: str | None = None
    grade: str | None = None
    severity: Literal["low", "medium", "high", "critical"]


class RecommendationSuggestion(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    category: str = Field(min_length=1, max_length=100)


class StrengthSuggestion(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    evidence: str = Field(min_length=1, description="What in the observation notes shows this strength")


class PriorityImprovement(BaseModel):
    """One of at most three priority improvement areas (private mentor analysis
    plus one simple, teacher-facing suggestion)."""

    area: str = Field(min_length=1, max_length=120, description="Short name, e.g. 'Student participation'")
    evidence: str = Field(min_length=1, description="What in the notes shows this need")
    possible_reason: str | None = Field(default=None, description="Hypothesis only; may be null")
    recommendation: str = Field(min_length=1, description="Practical recommendation for the mentor")
    teacher_suggestion: str = Field(
        min_length=1, max_length=600,
        description="1-2 simple, encouraging sentences addressed to the teacher as 'you'. No names, no evidence.",
    )


TeacherResponseType = Literal["agreement", "clarification", "support_needed", "different_perspective"]


class TeacherResponseOption(BaseModel):
    """A *suggested* reply the teacher could choose. Never an actual reply."""

    type: TeacherResponseType
    label: str = Field(min_length=1, max_length=80)
    response: str = Field(min_length=1, max_length=500)


def _all_required(schema: dict, _cls) -> None:
    # Ask the model (constrained decoding) to emit every section; validation
    # still uses the defaults below so a missing section is recoverable.
    schema["required"] = list(schema.get("properties", {}))


class AnalysisContent(BaseModel):
    """Exactly what the LLM must produce (validated)."""

    model_config = ConfigDict(json_schema_extra=_all_required)

    summary: str = Field(min_length=1)
    findings: list[FindingSuggestion] = Field(default_factory=list, max_length=5)
    learning_gaps: list[LearningGapSuggestion] = Field(default_factory=list, max_length=5)
    recommendations: list[RecommendationSuggestion] = Field(default_factory=list, max_length=5)
    # Mentor analysis + material for the teacher message (added in v1.2).
    strengths: list[StrengthSuggestion] = Field(default_factory=list, max_length=3)
    priority_improvements: list[PriorityImprovement] = Field(default_factory=list, max_length=3)
    follow_up_actions: list[str] = Field(default_factory=list, max_length=3)
    teacher_response_options: list[TeacherResponseOption] = Field(default_factory=list, max_length=4)

    @field_validator("strengths", "priority_improvements", "follow_up_actions", mode="before")
    @classmethod
    def _cap_three(cls, v):
        # Small models sometimes return extra items; keep the first three
        # (the most important) instead of rejecting the whole analysis.
        return v[:3] if isinstance(v, list) else v

    @field_validator("teacher_response_options", mode="before")
    @classmethod
    def _cap_four(cls, v):
        return v[:4] if isinstance(v, list) else v


class ObservationAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str = Field(min_length=1, max_length=100)
    grade: str | None = Field(default=None, max_length=30)
    topic: str | None = Field(default=None, max_length=200)
    observation_notes: str = Field(min_length=20, max_length=8000)
    existing_findings: list[str] = Field(default_factory=list, max_length=20)


class ObservationAnalysisResponse(AnalysisContent):
    sources: list[Source]
    model: str
    status: Literal["ai_suggested"] = Field(
        default="ai_suggested",
        description="Suggestions only. They become official MARG records only after mentor approval.",
    )
