"""Initial database schema migration for LectureForge AI.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-24 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create documents table
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=20), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default="uploaded",
            nullable=False,
        ),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("chunks_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_documents_id", "documents", ["id"], unique=False)
    op.create_index("ix_documents_filename", "documents", ["filename"], unique=False)
    op.create_index("ix_documents_status", "documents", ["status"], unique=False)
    op.create_index("ix_documents_created_at", "documents", ["created_at"], unique=False)
    op.create_index(
        "ix_documents_status_created_at",
        "documents",
        ["status", "created_at"],
        unique=False,
    )

    # 2. Create study_packs table
    op.create_table(
        "study_packs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "document_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("evaluation_json", sa.JSON(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default="generating",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_study_packs_id", "study_packs", ["id"], unique=False)
    op.create_index("ix_study_packs_document_id", "study_packs", ["document_id"], unique=False)
    op.create_index("ix_study_packs_status", "study_packs", ["status"], unique=False)
    op.create_index("ix_study_packs_created_at", "study_packs", ["created_at"], unique=False)
    op.create_index(
        "ix_study_packs_document_id_created_at",
        "study_packs",
        ["document_id", "created_at"],
        unique=False,
    )

    # 3. Create pipeline_runs table
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "document_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "study_pack_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("study_packs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("current_stage", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
    )
    op.create_index("ix_pipeline_runs_id", "pipeline_runs", ["id"], unique=False)
    op.create_index("ix_pipeline_runs_document_id", "pipeline_runs", ["document_id"], unique=False)
    op.create_index(
        "ix_pipeline_runs_study_pack_id", "pipeline_runs", ["study_pack_id"], unique=False
    )
    op.create_index("ix_pipeline_runs_status", "pipeline_runs", ["status"], unique=False)
    op.create_index("ix_pipeline_runs_started_at", "pipeline_runs", ["started_at"], unique=False)
    op.create_index(
        "ix_pipeline_runs_document_stage",
        "pipeline_runs",
        ["document_id", "current_stage"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("pipeline_runs")
    op.drop_table("study_packs")
    op.drop_table("documents")
