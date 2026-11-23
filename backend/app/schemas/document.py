"""Pydantic schemas for document upload, retrieval, and status tracking."""

import math
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.document import DocumentStatus


class DocumentBase(BaseModel):
    """Base schema for document attributes."""

    filename: str = Field(..., max_length=255, description="Original uploaded filename")
    file_type: str = Field(..., description="File format extension (pdf, pptx, txt)")
    file_size: int = Field(..., ge=0, description="File size in bytes")


class DocumentCreate(DocumentBase):
    """Schema used during document record creation."""

    file_path: str = Field(..., description="Filesystem storage path")


class DocumentResponse(DocumentBase):
    """Public representation of an uploaded document."""

    id: uuid.UUID = Field(..., description="Unique document UUID")
    status: DocumentStatus = Field(..., description="Current pipeline processing status")
    page_count: int | None = Field(default=None, description="Number of pages or slides parsed")
    error_message: str | None = Field(default=None, description="Error detail if processing failed")
    created_at: datetime = Field(..., description="Upload timestamp")
    updated_at: datetime = Field(..., description="Last modification timestamp")
    has_study_pack: bool = Field(
        default=False,
        description="Indicates whether a study pack exists for this document",
    )

    @computed_field
    @property
    def human_readable_size(self) -> str:
        """Return human-readable file size with units."""
        size = float(self.file_size)
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024.0 or unit == "GB":
                return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
            size /= 1024.0
        return f"{size:.1f} GB"

    model_config = ConfigDict(from_attributes=True)


class DocumentDetailResponse(DocumentResponse):
    """Extended document details including extracted text and chunk statistics."""

    extracted_text: str | None = Field(default=None, description="Raw extracted document text")
    chunks_count: int = Field(default=0, description="Total number of text chunks created")


class DocumentListResponse(BaseModel):
    """Paginated list of document responses."""

    items: list[DocumentResponse] = Field(
        default_factory=list, description="Documents on current page"
    )
    total: int = Field(..., ge=0, description="Total number of documents matching query")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, description="Number of items per page")
    total_pages: int = Field(..., ge=0, description="Total available pages")

    @classmethod
    def create(
        cls, items: list[DocumentResponse], total: int, page: int, page_size: int
    ) -> "DocumentListResponse":
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )


class DocumentStatusResponse(BaseModel):
    """Real-time processing status of a document."""

    id: uuid.UUID = Field(..., description="Unique document UUID")
    filename: str = Field(..., description="Document filename")
    status: DocumentStatus = Field(..., description="Current processing status")
    current_stage: str | None = Field(
        default=None, description="Current processing stage description"
    )
    progress_percentage: int = Field(
        ...,
        ge=0,
        le=100,
        description="Overall estimated percentage completion (0-100%)",
    )
    error_message: str | None = Field(default=None, description="Error details if pipeline failed")
    updated_at: datetime = Field(..., description="Status timestamp")

    @classmethod
    def from_document(
        cls,
        doc_id: uuid.UUID,
        filename: str,
        status: DocumentStatus,
        updated_at: datetime,
        current_stage: str | None = None,
        error_message: str | None = None,
    ) -> "DocumentStatusResponse":
        """Compute estimated completion percentage based on current pipeline status."""
        stage_progress = {
            DocumentStatus.UPLOADED: 10,
            DocumentStatus.PARSING: 25,
            DocumentStatus.CHUNKING: 40,
            DocumentStatus.EXTRACTING_CONCEPTS: 55,
            DocumentStatus.GENERATING_SUMMARY: 70,
            DocumentStatus.GENERATING_QUESTIONS: 85,
            DocumentStatus.EVALUATING: 92,
            DocumentStatus.RETRYING: 88,
            DocumentStatus.COMPLETED: 100,
            DocumentStatus.FAILED: 0,
        }
        progress = stage_progress.get(status, 0)
        stage_desc = current_stage or status.value.replace("_", " ").title()

        return cls(
            id=doc_id,
            filename=filename,
            status=status,
            current_stage=stage_desc,
            progress_percentage=progress,
            error_message=error_message,
            updated_at=updated_at,
        )
