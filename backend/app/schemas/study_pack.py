"""Pydantic schemas for study packs, including concepts, questions, and evaluation."""

import enum
import uuid
from datetime import datetime
from typing import Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.models.document import StudyPackStatus


class QuestionType(str, enum.Enum):
    """Categories of study questions."""

    MCQ = "mcq"
    SHORT_ANSWER = "short_answer"
    CONCEPTUAL = "conceptual"


class DifficultyLevel(str, enum.Enum):
    """Question difficulty levels."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class SourceReference(BaseModel):
    """Traceable citation to original lecture notes or slides."""

    page_numbers: list[int] = Field(
        default_factory=list,
        description="Page numbers where the material was found",
    )
    section_title: str | None = Field(
        default=None,
        description="Section heading or slide title in the original document",
    )
    slide_numbers: list[int] | None = Field(
        default=None,
        description="Slide numbers if the source was a presentation",
    )


class Concept(BaseModel):
    """Core academic concept extracted from lecture notes."""

    name: str = Field(..., min_length=1, description="Concept name or title")
    description: str = Field(..., min_length=1, description="Concise explanation of the concept")
    source_ref: SourceReference = Field(
        default_factory=SourceReference,
        description="Citation back to source material",
    )


class KeyTerm(BaseModel):
    """Important domain vocabulary and glossary definition."""

    term: str = Field(..., min_length=1, description="Key term or keyword")
    definition: str = Field(..., min_length=1, description="Accurate definition")
    source_ref: SourceReference = Field(
        default_factory=SourceReference,
        description="Citation back to source material",
    )


class Formula(BaseModel):
    """Mathematical equation, scientific formula, or code algorithm."""

    expression: str = Field(..., min_length=1, description="Formula representation (LaTeX or text)")
    description: str = Field(
        ..., min_length=1, description="What the formula calculates or represents"
    )
    source_ref: SourceReference = Field(
        default_factory=SourceReference,
        description="Citation back to source material",
    )


class MCQOption(BaseModel):
    """Multiple-choice option choice."""

    label: str = Field(..., description="Option letter label: A, B, C, or D")
    text: str = Field(..., min_length=1, description="Option text content")

    @field_validator("label")
    @classmethod
    def validate_option_label(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if cleaned not in {"A", "B", "C", "D"}:
            raise ValueError(f"MCQ option label must be 'A', 'B', 'C', or 'D', got: {v!r}")
        return cleaned


class PracticeQuestion(BaseModel):
    """Generated test or revision question with rubric and citation."""

    id: str = Field(..., description="Unique question identifier")
    question_text: str = Field(..., min_length=1, description="The test question prompt")
    question_type: QuestionType = Field(
        ..., description="Type of question (mcq, short_answer, conceptual)"
    )
    difficulty: DifficultyLevel = Field(..., description="Difficulty level (easy, medium, hard)")
    options: list[MCQOption] | None = Field(
        default=None,
        description="Options for MCQ questions. Must contain exactly 4 options for MCQ.",
    )
    correct_answer: str = Field(..., min_length=1, description="The correct answer or solution key")
    explanation: str = Field(..., min_length=1, description="Step-by-step reasoning or explanation")
    source_ref: SourceReference = Field(
        default_factory=SourceReference,
        description="Citation back to source material",
    )

    @model_validator(mode="after")
    def validate_mcq_requirements(self) -> Self:
        """Validate MCQ constraints: exactly 4 options labeled A-D, correct_answer must be A/B/C/D."""
        if self.question_type == QuestionType.MCQ:
            if not self.options:
                raise ValueError("MCQ questions must include options.")
            if len(self.options) != 4:
                raise ValueError(
                    f"MCQ questions must have exactly 4 options, found {len(self.options)}."
                )

            labels = [opt.label.upper() for opt in self.options]
            expected_labels = ["A", "B", "C", "D"]
            if sorted(labels) != expected_labels:
                raise ValueError(
                    f"MCQ options must have distinct labels A, B, C, and D. Found: {labels}."
                )

            cleaned_correct = self.correct_answer.strip().upper()
            if cleaned_correct not in {"A", "B", "C", "D"}:
                raise ValueError(
                    f"MCQ correct_answer must be one of 'A', 'B', 'C', or 'D', got {self.correct_answer!r}."
                )
            self.correct_answer = cleaned_correct

        return self


class Summary(BaseModel):
    """Executive summary and comprehensive lecture notes digest."""

    overview: str = Field(..., min_length=1, description="High-level introductory synthesis")
    detailed_summary: str = Field(
        ..., min_length=1, description="Comprehensive structural breakdown"
    )


class EvaluationResult(BaseModel):
    """Self-reflection and quality audit evaluation results."""

    faithfulness: int = Field(
        ...,
        ge=1,
        le=5,
        description="Score (1-5) evaluating adherence to source material without hallucination",
    )
    coverage: int = Field(
        ...,
        ge=1,
        le=5,
        description="Score (1-5) evaluating whether all key topics were captured",
    )
    answer_accuracy: int = Field(
        ...,
        ge=1,
        le=5,
        description="Score (1-5) evaluating correctness of practice questions and solutions",
    )
    clarity: int = Field(
        ...,
        ge=1,
        le=5,
        description="Score (1-5) evaluating clarity, pedagogical value, and formatting",
    )
    overall_score: float = Field(
        ...,
        ge=1.0,
        le=5.0,
        description="Weighted overall quality score (1.0 - 5.0)",
    )
    passed: bool = Field(
        ...,
        description="True if quality exceeds benchmark thresholds and requires no retry",
    )
    issues: list[str] = Field(
        default_factory=list,
        description="List of detected anomalies or shortcomings",
    )
    failed_sections: list[str] = Field(
        default_factory=list,
        description="List of sections that failed quality check and triggered retries",
    )


class PipelineMetadata(BaseModel):
    """Telemetry captured during study pack generation."""

    prompt_version: str = Field(..., description="Prompt template version tag")
    model_name: str = Field(..., description="Gemini model employed")
    retry_count: int = Field(default=0, ge=0, description="Number of automated correction retries")
    processing_time_seconds: float = Field(
        default=0.0,
        ge=0.0,
        description="End-to-end processing duration in seconds",
    )
    token_usage: dict[str, Any] | None = Field(
        default=None,
        description="Breakdown of input, output, and cached tokens consumed",
    )


class StudyPackMetadata(BaseModel):
    """Descriptive metadata for the study pack."""

    topic: str = Field(..., description="Primary topic or subject identified from lecture")
    document_id: uuid.UUID = Field(..., description="Source document UUID")
    source_pages: list[int] = Field(default_factory=list, description="Pages covered")
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Generation timestamp (UTC)",
    )


class StudyPackContent(BaseModel):
    """Full structured content of a LectureForge AI study pack."""

    metadata: StudyPackMetadata = Field(..., description="Pack metadata and topic")
    summary: Summary = Field(..., description="High-level and detailed summary sections")
    concepts: list[Concept] = Field(default_factory=list, description="Extracted core concepts")
    key_terms: list[KeyTerm] = Field(
        default_factory=list, description="Glossary of key terminology"
    )
    formulas: list[Formula] = Field(
        default_factory=list, description="Equations, theorems, and formulas"
    )
    practice_questions: list[PracticeQuestion] = Field(
        default_factory=list,
        description="Curated practice questions (MCQ, short answer, conceptual)",
    )
    evaluation: EvaluationResult | None = Field(
        default=None,
        description="Automated quality evaluation and audit metrics",
    )
    pipeline_metadata: PipelineMetadata | None = Field(
        default=None,
        description="Telemetry, model version, and timing statistics",
    )


class StudyPackResponse(BaseModel):
    """API response model for a study pack."""

    id: uuid.UUID = Field(..., description="Unique study pack UUID")
    document_id: uuid.UUID = Field(..., description="Associated document UUID")
    status: StudyPackStatus = Field(..., description="Study pack creation status")
    content: StudyPackContent = Field(..., description="Full structured study pack content")
    evaluation: EvaluationResult | None = Field(
        default=None,
        description="Quality evaluation report",
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last modification timestamp")

    model_config = ConfigDict(from_attributes=True)


class StudyPackListResponse(BaseModel):
    """List response for study packs."""

    items: list[StudyPackResponse] = Field(
        default_factory=list, description="Study packs in collection"
    )
    total: int = Field(..., ge=0, description="Total count")


class StudyPackRegenerateRequest(BaseModel):
    """Payload to trigger partial or complete regeneration of a study pack."""

    sections: list[str] = Field(
        default_factory=lambda: ["questions"],
        description="Sections to regenerate (e.g. ['summary', 'concepts', 'key_terms', 'formulas', 'questions'])",
    )
