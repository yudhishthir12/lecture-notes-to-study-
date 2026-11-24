"""Celery background tasks for document parsing, AI study pack generation, and section regeneration.

Provides idempotent, robust worker tasks using synchronous database access via SQLAlchemy,
integrating DocumentProcessor, StudyPackPipeline, StudyPackEvaluator, and RetryRouter.
"""

from __future__ import annotations

import logging
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator, List, Optional

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.evaluation.evaluator import StudyPackEvaluator
from app.evaluation.retry_router import RetryRouter
from app.models.document import (
    Document,
    DocumentStatus,
    PipelineRun,
    PipelineRunStatus,
    StudyPack,
    StudyPackStatus,
)
from app.pipelines.study_pack_pipeline import StudyPackPipeline
from app.schemas.pipeline import DocumentChunk
from app.schemas.study_pack import EvaluationResult, StudyPackContent
from app.services.document_processor import DocumentProcessor
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Synchronous Database Engine and Session Factory for Celery Workers
# -----------------------------------------------------------------------------
_sync_engine = None
_SyncSessionLocal = None


def get_sync_engine():
    """Create or return the synchronous SQLAlchemy database engine."""
    global _sync_engine
    if _sync_engine is None:
        sync_url = settings.DATABASE_URL_SYNC
        if not sync_url or "aiomysql" in sync_url:
            # Fall back to rewriting the async MySQL URL to PyMySQL
            sync_url = settings.DATABASE_URL.replace("mysql+aiomysql://", "mysql+pymysql://")
        if "sqlite+aiosqlite:" in sync_url:
            sync_url = sync_url.replace("sqlite+aiosqlite:", "sqlite:")

        _sync_engine = create_engine(
            sync_url,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
    return _sync_engine


def get_sync_sessionmaker() -> sessionmaker[Session]:
    """Return the sessionmaker bound to the sync engine."""
    global _SyncSessionLocal
    if _SyncSessionLocal is None:
        engine = get_sync_engine()
        _SyncSessionLocal = sessionmaker(
            bind=engine,
            class_=Session,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _SyncSessionLocal


@contextmanager
def sync_db_session() -> Generator[Session, None, None]:
    """Context manager yielding a synchronous database session with auto commit/rollback."""
    session_factory = get_sync_sessionmaker()
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# Alias for compatibility with core database naming
get_sync_db = sync_db_session


# -----------------------------------------------------------------------------
# Celery Tasks
# -----------------------------------------------------------------------------


@celery_app.task(name="app.workers.tasks.process_document", bind=True, max_retries=3)
def process_document(self, document_id: str) -> dict[str, Any]:
    """Ingest, parse, clean noise, and chunk an uploaded document.

    Idempotent task that updates Document status across PARSING and CHUNKING stages.

    Args:
        document_id: String UUID of the document.

    Returns:
        Dictionary with processing statistics and chunk count.
    """
    logger.info("Celery task process_document started for doc: %s", document_id)
    doc_uuid = uuid.UUID(str(document_id))

    with sync_db_session() as db:
        doc = db.query(Document).filter(Document.id == doc_uuid).first()
        if not doc:
            logger.error("Document %s not found in DB", document_id)
            return {"status": "error", "message": f"Document {document_id} not found"}

        # Idempotency check: if chunks already exist, skip parsing
        if doc.chunks_json and doc.status == DocumentStatus.COMPLETED:
            logger.info(
                "Document %s already processed with %d chunks", document_id, len(doc.chunks_json)
            )
            return {
                "status": "success",
                "document_id": str(doc.id),
                "chunks_count": len(doc.chunks_json),
                "already_processed": True,
            }

        # Update status to PARSING
        doc.status = DocumentStatus.PARSING
        doc.error_message = None
        db.commit()

    try:
        # Step 1: Run DocumentProcessor (parse, noise filter, semantic chunk)
        processor = DocumentProcessor()

        with sync_db_session() as db:
            doc = db.query(Document).filter(Document.id == doc_uuid).first()
            if not doc:
                return {"status": "error", "message": "Document removed during processing"}

            doc.status = DocumentStatus.CHUNKING
            db.commit()

            result = processor.process(file_path=doc.file_path, file_type=doc.file_type)

            # Step 2: Persist extracted text and chunks
            doc.extracted_text = result.cleaned_text or result.raw_text
            doc.page_count = result.page_count
            doc.chunks_json = [c.model_dump() for c in result.chunks]
            doc.status = DocumentStatus.COMPLETED
            doc.error_message = None
            db.commit()

            logger.info(
                "Document %s parsed and chunked successfully: %d chunks, %d pages",
                document_id,
                len(result.chunks),
                result.page_count,
            )

            return {
                "status": "success",
                "document_id": str(doc.id),
                "page_count": result.page_count,
                "chunks_count": len(result.chunks),
            }

    except Exception as exc:
        logger.error("Failed to process document %s: %s", document_id, exc, exc_info=True)
        with sync_db_session() as db:
            doc = db.query(Document).filter(Document.id == doc_uuid).first()
            if doc:
                doc.status = DocumentStatus.FAILED
                doc.error_message = f"Processing error: {str(exc)}"
                db.commit()
        raise


@celery_app.task(name="app.workers.tasks.generate_study_pack", bind=True, max_retries=1)
def generate_study_pack(self, document_id: str) -> dict[str, Any]:
    """Execute AI study pack generation, quality evaluation, and automated retry loop.

    Args:
        document_id: String UUID of the document.

    Returns:
        Dictionary containing study_pack_id, status, and evaluation metrics.
    """
    logger.info("Celery task generate_study_pack started for doc: %s", document_id)
    doc_uuid = uuid.UUID(str(document_id))

    # 1. Load document and verify chunks exist
    with sync_db_session() as db:
        doc = db.query(Document).filter(Document.id == doc_uuid).first()
        if not doc:
            logger.error("Document %s not found in DB", document_id)
            return {"status": "error", "message": f"Document {document_id} not found"}

        # If document is not parsed yet, parse it first
        if not doc.chunks_json:
            logger.info("Document %s has no chunks; invoking parsing first", document_id)
            doc.status = DocumentStatus.PARSING
            db.commit()

            processor = DocumentProcessor()
            proc_result = processor.process(doc.file_path, doc.file_type)
            doc.extracted_text = proc_result.cleaned_text or proc_result.raw_text
            doc.page_count = proc_result.page_count
            doc.chunks_json = [c.model_dump() for c in proc_result.chunks]
            db.commit()

        # Parse chunks into DocumentChunk models
        chunks = [DocumentChunk.model_validate(c) for c in doc.chunks_json]
        source_text = doc.extracted_text or ""

        # Create or update PipelineRun record
        pipeline_run = PipelineRun(
            id=uuid.uuid4(),
            document_id=doc.id,
            current_stage="initialization",
            status=PipelineRunStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            metadata_json={
                "prompt_version": settings.PROMPT_VERSION,
                "model_name": settings.GEMINI_MODEL,
            },
        )
        db.add(pipeline_run)
        doc.status = DocumentStatus.EXTRACTING_CONCEPTS
        db.commit()
        pipeline_run_id = pipeline_run.id

    try:
        # 2. Instantiate pipeline and callbacks for status persistence
        def status_callback(stage_name: str, doc_status: DocumentStatus) -> None:
            with sync_db_session() as session:
                d = session.query(Document).filter(Document.id == doc_uuid).first()
                pr = session.query(PipelineRun).filter(PipelineRun.id == pipeline_run_id).first()
                if d:
                    d.status = doc_status
                if pr:
                    pr.current_stage = stage_name
                session.commit()

        pipeline = StudyPackPipeline()
        evaluator = StudyPackEvaluator()
        router = RetryRouter()

        # 3. Generate complete StudyPackContent
        study_pack_content: StudyPackContent = pipeline.run(
            chunks=chunks,
            document_id=str(doc_uuid),
            status_callback=status_callback,
        )

        # 4. Run automated Quality Evaluation
        with sync_db_session() as session:
            d = session.query(Document).filter(Document.id == doc_uuid).first()
            if d:
                d.status = DocumentStatus.EVALUATING
            session.commit()

        eval_result: EvaluationResult = evaluator.evaluate(
            study_pack=study_pack_content,
            source_text=source_text,
            chunks=chunks,
        )

        # 5. Targeted Self-Correction Retry Loop (up to 2 retries)
        retry_count = 0
        while not eval_result.passed and retry_count < router.MAX_RETRIES:
            retry_plan = router.route_retry(
                evaluation=eval_result,
                study_pack=study_pack_content,
                current_retry_count=retry_count,
            )

            if not retry_plan.should_retry:
                break

            retry_count = retry_plan.retry_count
            logger.info(
                "Executing targeted retry %d/%d for sections: %s",
                retry_count,
                router.MAX_RETRIES,
                retry_plan.sections_to_retry,
            )

            with sync_db_session() as session:
                d = session.query(Document).filter(Document.id == doc_uuid).first()
                pr = session.query(PipelineRun).filter(PipelineRun.id == pipeline_run_id).first()
                if d:
                    d.status = DocumentStatus.RETRYING
                if pr:
                    pr.retry_count = retry_count
                    pr.current_stage = f"retry_{retry_count}"
                session.commit()

            # Regenerate defective sections
            for section in retry_plan.sections_to_retry:
                feedback = retry_plan.feedback.get(section)
                study_pack_content = pipeline.regenerate_section(
                    study_pack=study_pack_content,
                    section=section,
                    chunks=chunks,
                    feedback=feedback,
                )

            # Re-evaluate
            eval_result = evaluator.evaluate(
                study_pack=study_pack_content,
                source_text=source_text,
                chunks=chunks,
            )

        # Attach final evaluation to the study pack artifact
        study_pack_content.evaluation = eval_result
        if study_pack_content.pipeline_metadata:
            study_pack_content.pipeline_metadata.retry_count = retry_count

        # 6. Persist StudyPack record to database (Idempotent update or insert)
        with sync_db_session() as session:
            existing_pack = (
                session.query(StudyPack).filter(StudyPack.document_id == doc_uuid).first()
            )
            pack_status = (
                StudyPackStatus.COMPLETED if eval_result.passed else StudyPackStatus.WARNING
            )

            if existing_pack is None:
                new_pack = StudyPack(
                    id=uuid.uuid4(),
                    document_id=doc_uuid,
                    content_json=study_pack_content.model_dump(mode="json"),
                    evaluation_json=eval_result.model_dump(mode="json"),
                    status=pack_status,
                )
                session.add(new_pack)
                session.flush()
                pack_id = new_pack.id
            else:
                existing_pack.content_json = study_pack_content.model_dump(mode="json")
                existing_pack.evaluation_json = eval_result.model_dump(mode="json")
                existing_pack.status = pack_status
                session.flush()
                pack_id = existing_pack.id

            # Update Document and PipelineRun statuses
            d = session.query(Document).filter(Document.id == doc_uuid).first()
            if d:
                d.status = DocumentStatus.COMPLETED
                d.error_message = None

            pr = session.query(PipelineRun).filter(PipelineRun.id == pipeline_run_id).first()
            if pr:
                pr.study_pack_id = pack_id
                pr.status = PipelineRunStatus.COMPLETED
                pr.current_stage = "completed"
                pr.completed_at = datetime.now(timezone.utc)
                pr.retry_count = retry_count

            session.commit()

        logger.info(
            "Study pack generation successfully finished for doc %s (pack_id=%s, passed=%s, score=%.2f)",
            document_id,
            pack_id,
            eval_result.passed,
            eval_result.overall_score,
        )

        return {
            "status": "success",
            "study_pack_id": str(pack_id),
            "document_id": str(doc_uuid),
            "passed": eval_result.passed,
            "overall_score": eval_result.overall_score,
            "retry_count": retry_count,
        }

    except Exception as exc:
        logger.error("Study pack generation failed for doc %s: %s", document_id, exc, exc_info=True)
        with sync_db_session() as session:
            d = session.query(Document).filter(Document.id == doc_uuid).first()
            if d:
                d.status = DocumentStatus.FAILED
                d.error_message = f"Generation failed: {str(exc)}"

            pr = session.query(PipelineRun).filter(PipelineRun.id == pipeline_run_id).first()
            if pr:
                pr.status = PipelineRunStatus.FAILED
                pr.current_stage = "failed"
                pr.error_message = str(exc)
                pr.completed_at = datetime.now(timezone.utc)
            session.commit()
        raise


@celery_app.task(name="app.workers.tasks.regenerate_section", bind=True)
def regenerate_section(self, study_pack_id: str, sections: list[str]) -> dict[str, Any]:
    """Regenerate designated sections of an existing study pack and re-evaluate.

    Args:
        study_pack_id: String UUID of the study pack to update.
        sections: List of section names to regenerate (e.g. ['practice_questions']).

    Returns:
        Dictionary with status and updated score.
    """
    logger.info("Celery task regenerate_section started for pack %s: %s", study_pack_id, sections)
    pack_uuid = uuid.UUID(str(study_pack_id))

    with sync_db_session() as db:
        pack = db.query(StudyPack).filter(StudyPack.id == pack_uuid).first()
        if not pack:
            return {"status": "error", "message": f"StudyPack {study_pack_id} not found"}

        doc = db.query(Document).filter(Document.id == pack.document_id).first()
        if not doc or not doc.chunks_json:
            return {"status": "error", "message": "Associated document chunks not found"}

        pack.status = StudyPackStatus.GENERATING
        db.commit()

        chunks = [DocumentChunk.model_validate(c) for c in doc.chunks_json]
        source_text = doc.extracted_text or ""
        study_pack_content = StudyPackContent.model_validate(pack.content_json)

    pipeline = StudyPackPipeline()
    evaluator = StudyPackEvaluator()

    for sec in sections:
        study_pack_content = pipeline.regenerate_section(
            study_pack=study_pack_content,
            section=sec,
            chunks=chunks,
        )

    # Re-evaluate
    eval_result = evaluator.evaluate(
        study_pack=study_pack_content,
        source_text=source_text,
        chunks=chunks,
    )
    study_pack_content.evaluation = eval_result

    with sync_db_session() as db:
        pack = db.query(StudyPack).filter(StudyPack.id == pack_uuid).first()
        if pack:
            pack.content_json = study_pack_content.model_dump(mode="json")
            pack.evaluation_json = eval_result.model_dump(mode="json")
            pack.status = (
                StudyPackStatus.COMPLETED if eval_result.passed else StudyPackStatus.WARNING
            )
            db.commit()

    return {
        "status": "success",
        "study_pack_id": str(pack_uuid),
        "passed": eval_result.passed,
        "overall_score": eval_result.overall_score,
    }
