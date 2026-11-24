"""FastAPI router for study packs: retrieval, regeneration, evaluations, and exports."""

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger, set_pipeline_context
from app.exporters.anki_exporter import AnkiExporter
from app.exporters.markdown_exporter import MarkdownExporter
from app.exporters.pdf_exporter import PDFExporter
from app.models.document import (
    Document,
    PipelineRun,
    PipelineRunStatus,
    StudyPack,
    StudyPackStatus,
)
from app.schemas.study_pack import (
    EvaluationResult,
    StudyPackContent,
    StudyPackListResponse,
    StudyPackRegenerateRequest,
    StudyPackResponse,
)

logger = get_logger(__name__)

router = APIRouter()


async def _find_study_pack(
    identifier: uuid.UUID,
    db: AsyncSession,
) -> StudyPack | None:
    """Find a study pack by its own UUID, or by its associated document UUID."""
    query = (
        select(StudyPack)
        .options(selectinload(StudyPack.document))
        .where(
            or_(
                StudyPack.id == identifier,
                StudyPack.document_id == identifier,
            )
        )
        .order_by(desc(StudyPack.created_at))
    )
    result = await db.execute(query)
    return result.scalars().first()


@router.get(
    "/{study_pack_id}",
    response_model=StudyPackResponse,
    summary="Get study pack by ID",
    description="Fetch complete study pack content including summary, concepts, glossary, formulas, and questions.",
)
async def get_study_pack(
    study_pack_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> StudyPackResponse:
    """Fetch complete structured study pack content."""
    pack = await _find_study_pack(study_pack_id, db)

    if pack is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Study pack with ID '{study_pack_id}' not found.",
        )

    try:
        content_model = StudyPackContent(**pack.content_json)
    except Exception as exc:
        logger.error(
            "Failed to deserialize study pack content_json",
            study_pack_id=str(study_pack_id),
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored study pack content failed schema validation.",
        ) from exc

    eval_model = None
    if pack.evaluation_json:
        try:
            eval_model = EvaluationResult(**pack.evaluation_json)
        except Exception as exc:
            logger.warning(
                "Could not deserialize evaluation_json",
                study_pack_id=str(study_pack_id),
                error=str(exc),
            )

    return StudyPackResponse(
        id=pack.id,
        document_id=pack.document_id,
        status=pack.status,
        content=content_model,
        evaluation=eval_model,
        created_at=pack.created_at,
        updated_at=pack.updated_at,
    )


@router.post(
    "/{study_pack_id}/regenerate",
    response_model=dict[str, Any],
    summary="Regenerate study pack sections",
    description="Trigger regeneration for specific sections (e.g. questions, summary) with optional feedback.",
)
async def regenerate_study_pack(
    study_pack_id: uuid.UUID,
    payload: StudyPackRegenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Trigger partial or full study pack regeneration."""
    if not settings.GEMINI_API_KEY or not settings.GEMINI_API_KEY.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gemini API key not configured. Set GEMINI_API_KEY environment variable.",
        )

    pack = await _find_study_pack(study_pack_id, db)

    if pack is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Study pack with ID '{study_pack_id}' not found.",
        )

    # Create a pipeline run record for the regeneration task
    pipeline_run = PipelineRun(
        document_id=pack.document_id,
        study_pack_id=pack.id,
        current_stage="regeneration",
        status=PipelineRunStatus.PENDING,
        metadata_json={
            "sections": payload.sections,
            "prompt_version": settings.PROMPT_VERSION,
            "model_name": settings.GEMINI_MODEL,
        },
    )
    db.add(pipeline_run)

    pack.status = StudyPackStatus.GENERATING
    await db.flush()

    set_pipeline_context(
        document_id=pack.document_id,
        pipeline_run_id=pipeline_run.id,
        stage="regeneration",
    )
    logger.info(
        "Study pack regeneration requested",
        study_pack_id=str(pack.id),
        sections=payload.sections,
    )

    # Dispatch Celery background task for section regeneration
    try:
        from app.workers.tasks import regenerate_section as celery_regenerate

        celery_regenerate.delay(str(pack.id), payload.sections)
    except Exception as exc:
        logger.warning("Could not dispatch celery regenerate task: %s", exc)

    return {
        "message": f"Regeneration scheduled for sections: {payload.sections}",
        "study_pack_id": str(pack.id),
        "pipeline_run_id": str(pipeline_run.id),
        "status": pack.status.value,
    }


@router.get(
    "/{study_pack_id}/evaluation",
    response_model=EvaluationResult,
    summary="Get study pack evaluation results",
    description="Retrieve quality rubric scores, detected issues, and pass/fail status.",
)
async def get_study_pack_evaluation(
    study_pack_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> EvaluationResult:
    """Retrieve automated quality evaluation results for a study pack."""
    pack = await _find_study_pack(study_pack_id, db)

    if pack is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Study pack with ID '{study_pack_id}' not found.",
        )

    if not pack.evaluation_json:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No evaluation results found for this study pack.",
        )

    try:
        return EvaluationResult(**pack.evaluation_json)
    except Exception as exc:
        logger.error(
            "Evaluation payload failed schema validation",
            study_pack_id=str(study_pack_id),
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid evaluation data format.",
        ) from exc


@router.get(
    "/{study_pack_id}/export/markdown",
    summary="Export study pack as Markdown",
    description="Download complete study pack formatted as a clean Markdown (.md) document.",
)
async def export_study_pack_markdown(
    study_pack_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Export study pack as a Markdown file."""
    pack = await _find_study_pack(study_pack_id, db)

    if pack is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Study pack with ID '{study_pack_id}' not found.",
        )

    try:
        content = StudyPackContent.model_validate(pack.content_json)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deserialize study pack: {exc}",
        ) from exc

    exporter = MarkdownExporter()
    md_content = exporter.export(content)

    filename = f"{study_pack_id}_studypack.md"
    export_path = settings.resolved_export_dir / filename
    export_path.write_text(md_content, encoding="utf-8")

    return FileResponse(
        path=str(export_path),
        filename=filename,
        media_type="text/markdown",
    )


@router.get(
    "/{study_pack_id}/export/pdf",
    summary="Export study pack as PDF",
    description="Download professionally styled PDF study booklet with typography and page numbering.",
)
async def export_study_pack_pdf(
    study_pack_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Export study pack as a PDF document."""
    pack = await _find_study_pack(study_pack_id, db)

    if pack is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Study pack with ID '{study_pack_id}' not found.",
        )

    try:
        content = StudyPackContent.model_validate(pack.content_json)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deserialize study pack: {exc}",
        ) from exc

    filename = f"{study_pack_id}_studypack.pdf"
    export_path = settings.resolved_export_dir / filename
    exporter = PDFExporter()
    export_result = exporter.export(content, str(export_path))

    # Return PDF if successfully generated
    if Path(export_result).exists() and export_result.endswith(".pdf"):
        return FileResponse(
            path=export_result,
            filename=filename,
            media_type="application/pdf",
        )

    # Return HTML fallback if PDF generation couldn't run
    html_fallback = export_path.with_suffix(".html")
    if html_fallback.exists():
        return FileResponse(
            path=str(html_fallback),
            filename=f"{study_pack_id}_studypack.html",
            media_type="text/html",
        )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=export_result,
    )


@router.get(
    "/{study_pack_id}/export/anki",
    summary="Export study pack as Anki flashcards CSV",
    description="Download Anki-compatible CSV file containing Q&A and definition cards.",
)
async def export_study_pack_anki(
    study_pack_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Export study pack flashcards as an Anki-compatible CSV."""
    pack = await _find_study_pack(study_pack_id, db)

    if pack is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Study pack with ID '{study_pack_id}' not found.",
        )

    try:
        content = StudyPackContent.model_validate(pack.content_json)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deserialize study pack: {exc}",
        ) from exc

    exporter = AnkiExporter()
    csv_content = exporter.export(content)

    filename = f"{study_pack_id}_anki.csv"
    export_path = settings.resolved_export_dir / filename
    export_path.write_text(csv_content, encoding="utf-8")

    return FileResponse(
        path=str(export_path),
        filename=filename,
        media_type="text/csv",
    )
