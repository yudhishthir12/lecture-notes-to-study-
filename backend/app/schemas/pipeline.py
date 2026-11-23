"""Pydantic schemas for the processing pipeline and intermediate stages."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import PipelineRunStatus


class DocumentChunk(BaseModel):
    """Text chunk sliced from the parsed document for model context."""

    chunk_id: str = Field(..., description="Unique chunk identifier, e.g. chunk_001")
    text: str = Field(..., min_length=1, description="Raw chunk text content")
    source_pages: list[int] = Field(
        default_factory=list,
        description="Source page or slide numbers included in this chunk",
    )
    section_title: str | None = Field(
        default=None,
        description="Associated section heading or topic title if identified",
    )


class ConceptExtraction(BaseModel):
    """Intermediate extraction output capturing academic entities from text."""

    main_topics: list[str] = Field(
        default_factory=list,
        description="Primary academic themes and subjects identified",
    )
    subtopics: list[str] = Field(
        default_factory=list,
        description="Fine-grained subtopics and component areas",
    )
    facts: list[str] = Field(
        default_factory=list,
        description="Crucial lecture facts, principles, and rules",
    )
    definitions: dict[str, str] = Field(
        default_factory=dict,
        description="Term to definition mapping",
    )
    formulas: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Discovered formulas, mathematical expressions, or algorithms",
    )
    source_references: dict[str, Any] = Field(
        default_factory=dict,
        description="Mapping of concepts/terms to original document locations",
    )


class PipelineStatus(BaseModel):
    """Real-time pipeline run status tracker."""

    run_id: uuid.UUID = Field(..., description="Pipeline run UUID")
    document_id: uuid.UUID = Field(..., description="Source document UUID")
    study_pack_id: uuid.UUID | None = Field(
        default=None,
        description="Associated study pack UUID if created",
    )
    current_stage: str = Field(..., description="Active pipeline stage")
    status: PipelineRunStatus = Field(..., description="Current status of the pipeline")
    retry_count: int = Field(default=0, ge=0, description="Number of retries triggered")
    error_message: str | None = Field(default=None, description="Error details if pipeline failed")
    started_at: datetime = Field(..., description="Pipeline execution start timestamp")
    completed_at: datetime | None = Field(default=None, description="Pipeline completion timestamp")


class PipelineRunResponse(BaseModel):
    """Public representation of a pipeline run execution log."""

    id: uuid.UUID = Field(..., description="Pipeline run UUID")
    document_id: uuid.UUID = Field(..., description="Document UUID")
    study_pack_id: uuid.UUID | None = Field(default=None, description="Study pack UUID")
    current_stage: str = Field(..., description="Stage name")
    status: PipelineRunStatus = Field(..., description="Run status")
    retry_count: int = Field(..., description="Number of retries executed")
    error_message: str | None = Field(default=None, description="Error message if run failed")
    started_at: datetime = Field(..., description="Start timestamp")
    completed_at: datetime | None = Field(default=None, description="Completion timestamp")
    metadata_json: dict[str, Any] | None = Field(
        default=None, description="Stage timing and telemetry"
    )

    model_config = ConfigDict(from_attributes=True)
