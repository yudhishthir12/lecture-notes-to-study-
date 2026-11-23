"""SQLAlchemy models for documents, generated study packs, and pipeline runs.

Implements database schema with PostgreSQL UUID primary keys, foreign key constraints,
cascading deletes, composite indexes, and structured JSON storage.
"""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DocumentStatus(str, enum.Enum):
    """Lifecycle status of a document during parsing, extraction, and generation."""

    UPLOADED = "uploaded"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EXTRACTING_CONCEPTS = "extracting_concepts"
    GENERATING_SUMMARY = "generating_summary"
    GENERATING_QUESTIONS = "generating_questions"
    EVALUATING = "evaluating"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"


class StudyPackStatus(str, enum.Enum):
    """Status of the generated study pack artifact."""

    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    WARNING = "warning"


class PipelineRunStatus(str, enum.Enum):
    """Execution status of an individual pipeline workflow run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FileType(str, enum.Enum):
    """Supported document upload file extensions."""

    PDF = "pdf"
    PPTX = "pptx"
    TXT = "txt"


class Document(Base):
    """Uploaded lecture note, textbook, or slide deck document."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    file_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )
    file_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(
            DocumentStatus,
            name="document_status_enum",
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=False,
        ),
        default=DocumentStatus.UPLOADED,
        nullable=False,
        index=True,
    )
    extracted_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    chunks_json: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    page_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    study_packs: Mapped[list["StudyPack"]] = relationship(
        "StudyPack",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="desc(StudyPack.created_at)",
    )
    pipeline_runs: Mapped[list["PipelineRun"]] = relationship(
        "PipelineRun",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="desc(PipelineRun.started_at)",
    )

    __table_args__ = (Index("ix_documents_status_created_at", "status", "created_at"),)

    def __repr__(self) -> str:
        return f"<Document id={self.id} filename={self.filename!r} status={self.status.value}>"


class StudyPack(Base):
    """Complete generated study material pack derived from a document."""

    __tablename__ = "study_packs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    evaluation_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    status: Mapped[StudyPackStatus] = mapped_column(
        SAEnum(
            StudyPackStatus,
            name="study_pack_status_enum",
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=False,
        ),
        default=StudyPackStatus.GENERATING,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="study_packs",
    )
    pipeline_runs: Mapped[list["PipelineRun"]] = relationship(
        "PipelineRun",
        back_populates="study_pack",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (Index("ix_study_packs_document_id_created_at", "document_id", "created_at"),)

    def __repr__(self) -> str:
        return f"<StudyPack id={self.id} document_id={self.document_id} status={self.status.value}>"


class PipelineRun(Base):
    """Audit and telemetry record for a single pipeline execution or regeneration."""

    __tablename__ = "pipeline_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    study_pack_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("study_packs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    current_stage: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="initialization",
    )
    status: Mapped[PipelineRunStatus] = mapped_column(
        SAEnum(
            PipelineRunStatus,
            name="pipeline_run_status_enum",
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=False,
        ),
        default=PipelineRunStatus.PENDING,
        nullable=False,
        index=True,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # Relationships
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="pipeline_runs",
    )
    study_pack: Mapped["StudyPack | None"] = relationship(
        "StudyPack",
        back_populates="pipeline_runs",
    )

    __table_args__ = (Index("ix_pipeline_runs_document_stage", "document_id", "current_stage"),)

    def __repr__(self) -> str:
        return (
            f"<PipelineRun id={self.id} doc={self.document_id} "
            f"stage={self.current_stage!r} status={self.status.value}>"
        )
