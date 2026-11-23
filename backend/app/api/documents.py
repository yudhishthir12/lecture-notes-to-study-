"""FastAPI router for document management, uploads, listing, and generation triggers."""

import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger, set_pipeline_context
from app.models.document import (
    Document,
    DocumentStatus,
    FileType,
    PipelineRun,
    PipelineRunStatus,
)
from app.schemas.document import (
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentStatusResponse,
)

logger = get_logger(__name__)

router = APIRouter()

# Supported file extensions and their corresponding MIME types
ALLOWED_EXTENSIONS = {".pdf", ".pptx", ".txt"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.ms-powerpoint",
    "text/plain",
    "application/octet-stream",  # Permitted if the extension is valid
}


def sanitize_filename(filename: str) -> str:
    """Sanitize original filename to prevent directory traversal or invalid characters."""
    base_name = Path(filename).name
    # Replace non-alphanumeric (except dots, underscores, dashes) with underscores
    cleaned = re.sub(r"[^\w\.-]", "_", base_name)
    return cleaned or "document.bin"


async def save_uploaded_file(file: UploadFile, destination: Path) -> int:
    """Stream uploaded file contents to disk in chunks while enforcing size limits."""
    max_bytes = settings.max_upload_size_bytes
    total_bytes = 0
    chunk_size = 1024 * 1024  # 1MB buffer

    try:
        with destination.open("wb") as out_file:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=(
                            f"File size exceeds maximum allowed limit of "
                            f"{settings.MAX_UPLOAD_SIZE_MB}MB."
                        ),
                    )
                out_file.write(chunk)
    except HTTPException:
        # Clean up partial file on size violation
        if destination.exists():
            destination.unlink(missing_ok=True)
        raise
    except Exception as exc:
        if destination.exists():
            destination.unlink(missing_ok=True)
        logger.error("Failed to save uploaded file to disk", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save file to server storage.",
        ) from exc

    return total_bytes


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a lecture document",
    description="Accepts PDF, PPTX, or TXT lecture files up to MAX_UPLOAD_SIZE_MB.",
)
@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def upload_document(
    file: UploadFile = File(..., description="Lecture notes file (.pdf, .pptx, or .txt)"),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Upload and register a new document."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided in upload payload.",
        )

    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file format '{file_ext}'. "
                f"Supported formats are: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
            ),
        )

    # Validate MIME type if provided
    content_type = (file.content_type or "").lower().split(";")[0].strip()
    if content_type and content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid MIME type '{file.content_type}'. Must be PDF, PPTX, or TXT.",
        )

    clean_name = sanitize_filename(file.filename)
    doc_id = uuid.uuid4()
    stored_filename = f"{doc_id}_{clean_name}"
    storage_path = settings.resolved_upload_dir / stored_filename

    # Stream file to disk and record byte size
    total_size = await save_uploaded_file(file, storage_path)

    # Determine file type string
    type_str = file_ext.lstrip(".")
    if type_str not in {e.value for e in FileType}:
        type_str = FileType.TXT.value

    # Create Document record
    document = Document(
        id=doc_id,
        filename=clean_name,
        file_type=type_str,
        file_path=str(storage_path),
        file_size=total_size,
        status=DocumentStatus.UPLOADED,
    )
    db.add(document)
    await db.flush()
    await db.refresh(document)

    logger.info(
        "Document uploaded successfully",
        document_id=str(doc_id),
        filename=clean_name,
        size_bytes=total_size,
    )

    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        file_type=document.file_type,
        file_size=document.file_size,
        status=document.status,
        page_count=document.page_count,
        error_message=document.error_message,
        created_at=document.created_at,
        updated_at=document.updated_at,
        has_study_pack=False,
    )


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List uploaded documents",
    description="Retrieve paginated list of uploaded documents with optional status filtering.",
)
async def list_documents(
    page: int = Query(1, ge=1, description="Page number starting from 1"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page (max 100)"),
    status_filter: DocumentStatus | None = Query(
        None,
        alias="status",
        description="Filter by document status",
    ),
    db: AsyncSession = Depends(get_db),
) -> DocumentListResponse:
    """List documents with pagination and study pack availability."""
    # Build filter conditions
    conditions = []
    if status_filter is not None:
        conditions.append(Document.status == status_filter)

    # Count total matching
    count_stmt = select(func.count(Document.id))
    if conditions:
        count_stmt = count_stmt.where(*conditions)
    total_result = await db.execute(count_stmt)
    total_count = total_result.scalar_one()

    # Query items with eager loaded study_packs for has_study_pack flag
    query = (
        select(Document)
        .options(selectinload(Document.study_packs))
        .order_by(Document.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    if conditions:
        query = query.where(*conditions)

    result = await db.execute(query)
    docs = result.scalars().all()

    items = [
        DocumentResponse(
            id=d.id,
            filename=d.filename,
            file_type=d.file_type,
            file_size=d.file_size,
            status=d.status,
            page_count=d.page_count,
            error_message=d.error_message,
            created_at=d.created_at,
            updated_at=d.updated_at,
            has_study_pack=len(d.study_packs) > 0,
        )
        for d in docs
    ]

    return DocumentListResponse.create(
        items=items,
        total=total_count,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    summary="Get document details",
    description="Fetch full details for an individual document including text preview and chunk counts.",
)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> DocumentDetailResponse:
    """Retrieve detailed information about a specific document."""
    query = (
        select(Document)
        .options(selectinload(Document.study_packs))
        .where(Document.id == document_id)
    )
    result = await db.execute(query)
    doc = result.scalar_one_or_none()

    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found.",
        )

    chunks_count = len(doc.chunks_json) if doc.chunks_json else 0

    return DocumentDetailResponse(
        id=doc.id,
        filename=doc.filename,
        file_type=doc.file_type,
        file_size=doc.file_size,
        status=doc.status,
        page_count=doc.page_count,
        error_message=doc.error_message,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        has_study_pack=len(doc.study_packs) > 0,
        extracted_text=doc.extracted_text,
        chunks_count=chunks_count,
    )


@router.get(
    "/{document_id}/status",
    response_model=DocumentStatusResponse,
    summary="Get document processing status",
    description="Poll current pipeline stage and completion percentage for a document.",
)
async def get_document_status(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> DocumentStatusResponse:
    """Retrieve real-time processing status and stage progress."""
    query = (
        select(Document)
        .options(selectinload(Document.pipeline_runs))
        .where(Document.id == document_id)
    )
    result = await db.execute(query)
    doc = result.scalar_one_or_none()

    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found.",
        )

    current_stage = None
    if doc.pipeline_runs:
        current_stage = doc.pipeline_runs[0].current_stage

    return DocumentStatusResponse.from_document(
        doc_id=doc.id,
        filename=doc.filename,
        status=doc.status,
        updated_at=doc.updated_at,
        current_stage=current_stage,
        error_message=doc.error_message,
    )


@router.post(
    "/{document_id}/generate",
    response_model=DocumentStatusResponse,
    summary="Trigger study pack generation",
    description="Initiates the AI study pack generation pipeline for this document.",
)
async def generate_study_pack(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> DocumentStatusResponse:
    """Validate API key and trigger the study pack generation pipeline."""
    # Enforce Gemini API Key requirement
    if not settings.GEMINI_API_KEY or not settings.GEMINI_API_KEY.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gemini API key not configured. Set GEMINI_API_KEY environment variable.",
        )

    query = (
        select(Document)
        .options(selectinload(Document.pipeline_runs))
        .where(Document.id == document_id)
    )
    result = await db.execute(query)
    doc = result.scalar_one_or_none()

    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found.",
        )

    # Initialize a new pipeline run audit record
    pipeline_run = PipelineRun(
        document_id=doc.id,
        current_stage="parsing",
        status=PipelineRunStatus.PENDING,
        metadata_json={
            "prompt_version": settings.PROMPT_VERSION,
            "model_name": settings.GEMINI_MODEL,
            "started_by": "api_request",
        },
    )
    db.add(pipeline_run)

    # Update document status to parsing
    doc.status = DocumentStatus.PARSING
    doc.error_message = None
    await db.flush()
    await db.refresh(doc)

    set_pipeline_context(
        document_id=doc.id,
        pipeline_run_id=pipeline_run.id,
        stage="parsing",
    )
    logger.info(
        "Study pack generation triggered",
        document_id=str(doc.id),
        pipeline_run_id=str(pipeline_run.id),
    )

    # Dispatch Celery background task
    try:
        from app.workers.tasks import generate_study_pack as celery_generate

        celery_generate.delay(str(doc.id))
    except Exception as exc:
        logger.warning("Could not dispatch celery task: %s", exc)

    return DocumentStatusResponse.from_document(
        doc_id=doc.id,
        filename=doc.filename,
        status=doc.status,
        updated_at=doc.updated_at,
        current_stage="Parsing Document",
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete document and associated resources",
    description="Permanently deletes the document record, disk file, and associated study packs.",
)
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a document and clean up filesystem storage."""
    query = select(Document).where(Document.id == document_id)
    result = await db.execute(query)
    doc = result.scalar_one_or_none()

    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found.",
        )

    # Remove file from disk
    file_path = Path(doc.file_path)
    try:
        if file_path.exists():
            file_path.unlink()
            logger.info("Deleted document file from disk", file_path=str(file_path))
    except Exception as exc:
        logger.warning(
            "Could not delete document file from disk", file_path=str(file_path), error=str(exc)
        )

    # Delete from database (cascade deletes StudyPacks & PipelineRuns)
    await db.delete(doc)
    await db.flush()

    logger.info("Document deleted from database", document_id=str(document_id))
    return None
