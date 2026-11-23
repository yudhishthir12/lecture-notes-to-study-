"""End-to-end AI study pack generation pipeline for LectureForge AI.

Coordinates multi-stage processing:
Stage 1: Concept Extraction
Stage 2: Summary, Glossary & Formula Generation
Stage 3: Question Generation (MCQ, Short Answer, Conceptual)
Stage 4: Schema Validation & Telemetry Tracking with Self-Correction Retry.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, List, Optional

from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.models.document import DocumentStatus
from app.schemas.pipeline import ConceptExtraction, DocumentChunk
from app.schemas.study_pack import (
    Concept,
    Formula,
    KeyTerm,
    MCQOption,
    PipelineMetadata,
    PracticeQuestion,
    QuestionType,
    SourceReference,
    StudyPackContent,
    StudyPackMetadata,
    Summary,
)
from app.services.llm_service import LLMService, get_llm_service
from app.services.prompt_registry import get_prompt

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """Raised when pipeline processing encounters an unrecoverable failure."""

    pass


class SummaryStageOutput(BaseModel):
    """Pydantic schema for Stage 2 summary generation output."""

    overview: str
    detailed_summary: str
    concepts: list[Concept] = []
    key_terms: list[KeyTerm] = []
    formulas: list[Formula] = []


class QuestionStageOutput(BaseModel):
    """Pydantic schema for Stage 3 question generation output."""

    practice_questions: list[PracticeQuestion] = []


class StudyPackPipeline:
    """Orchestrates multi-stage AI study pack generation and section regeneration."""

    def __init__(
        self,
        llm_service: LLMService | None = None,
        prompt_version: str | None = None,
    ) -> None:
        """Initialize the pipeline with LLM service and prompt version."""
        self.llm = llm_service or get_llm_service()
        self.prompt_version = prompt_version or settings.PROMPT_VERSION

    def _format_chunks_context(self, chunks: list[DocumentChunk]) -> str:
        """Combine document chunks while limiting total LLM context size."""
        max_context_chars = 6000
        parts = []
        total_chars = 0

        for c in chunks:
            pages_str = ", ".join(str(p) for p in c.source_pages) if c.source_pages else "N/A"
            title_str = f" | Section: {c.section_title}" if c.section_title else ""
            header = f"--- [Chunk: {c.chunk_id} | Pages: {pages_str}{title_str}] ---"
            part = f"{header}\n{c.text.strip()}\n"

            remaining = max_context_chars - total_chars
            if remaining <= 0:
                break

            if len(part) > remaining:
                parts.append(part[:remaining])
                break

            parts.append(part)
            total_chars += len(part)

        return "\n".join(parts)

    def _merge_concept_extractions(self, results: list[ConceptExtraction]) -> ConceptExtraction:
        """Merge concept extraction results from multiple batches."""
        merged = ConceptExtraction()

        for result in results:
            merged.main_topics.extend(result.main_topics)
            merged.subtopics.extend(result.subtopics)
            merged.facts.extend(result.facts)
            merged.definitions.update(result.definitions)
            merged.formulas.extend(result.formulas)
            merged.source_references.update(result.source_references)

        merged.main_topics = list(dict.fromkeys(merged.main_topics))
        merged.subtopics = list(dict.fromkeys(merged.subtopics))
        merged.facts = list(dict.fromkeys(merged.facts))

        return merged

    def _extract_all_pages(self, chunks: list[DocumentChunk]) -> list[int]:
        """Collect and sort all unique source page numbers across chunks."""
        pages = set()
        for c in chunks:
            for p in c.source_pages:
                if isinstance(p, int) and p > 0:
                    pages.add(p)
        return sorted(list(pages))

    def run(
        self,
        chunks: list[DocumentChunk],
        document_id: str | uuid.UUID,
        status_callback: Optional[Callable[[str, DocumentStatus], None]] = None,
        topic_hint: Optional[str] = None,
    ) -> StudyPackContent:
        """Execute end-to-end study pack generation across all 4 stages.

        Args:
            chunks: Preprocessed semantic text chunks.
            document_id: Source document UUID.
            status_callback: Optional callback(stage_name, document_status) for live DB status updates.
            topic_hint: Optional topic title if known in advance.

        Returns:
            Validated StudyPackContent ready for persistence and export.

        Raises:
            PipelineError: If LLM is unconfigured, or generation fails irrevocably.
        """
        if not self.llm.is_configured():
            raise PipelineError(
                "LLM service is not configured. Please supply a valid GEMINI_API_KEY."
            )

        if not chunks:
            raise PipelineError("Cannot run pipeline on empty document chunks.")

        start_time = time.time()
        self.llm.reset_token_usage()

        doc_uuid = uuid.UUID(str(document_id))
        all_pages = self._extract_all_pages(chunks)
        source_context = self._format_chunks_context(chunks)

        logger.info(
            "Starting StudyPackPipeline for document %s (%d chunks, %d pages)",
            document_id,
            len(chunks),
            len(all_pages),
        )

        # ---------------------------------------------------------------------
        # STAGE 1: Concept Extraction
        # ---------------------------------------------------------------------
        if status_callback:
            status_callback("extracting_concepts", DocumentStatus.EXTRACTING_CONCEPTS)

        logger.info("Stage 1: Extracting concepts from source chunks...")
        stage1_prompt = (
            f"Here are the lecture document chunks:\n\n{source_context}\n\n"
            "Extract all main topics, subtopics, key facts, definitions, and formulas with source citations."
        )
        stage1_system = get_prompt("concept_extraction", self.prompt_version)

        try:
            concept_raw = self.llm.generate(
                prompt=stage1_prompt,
                system_prompt=stage1_system,
                response_schema=ConceptExtraction,
            )
            if isinstance(concept_raw, dict):
                extracted_concepts = ConceptExtraction.model_validate(concept_raw)
            else:
                extracted_concepts = ConceptExtraction.model_validate_json(concept_raw)
        except Exception as exc:
            logger.error("Stage 1 Concept Extraction failed: %s", exc)
            raise PipelineError(f"Stage 1 Concept Extraction failed: {exc}") from exc

        # Identify primary topic name
        identified_topic = topic_hint
        if not identified_topic and extracted_concepts.main_topics:
            identified_topic = extracted_concepts.main_topics[0]
        if not identified_topic:
            identified_topic = "Lecture Study Pack"

        logger.info(
            "Stage 1 complete: extracted %d topics, %d definitions, %d formulas",
            len(extracted_concepts.main_topics),
            len(extracted_concepts.definitions),
            len(extracted_concepts.formulas),
        )

        # ---------------------------------------------------------------------
        # STAGE 2: Summary Generation
        # ---------------------------------------------------------------------
        if status_callback:
            status_callback("generating_summary", DocumentStatus.GENERATING_SUMMARY)

        logger.info("Stage 2: Generating summary, glossary, and formulas...")
        stage2_prompt = (
            f"Topic: {identified_topic}\n\n"
            f"Extracted Knowledge Entities:\n{extracted_concepts.model_dump_json(indent=2)}\n\n"
            f"Source Lecture Chunks:\n{source_context}\n\n"
            "Synthesize a comprehensive pedagogical overview, detailed summary, concepts, glossary, and formulas."
        )
        stage2_system = get_prompt("summary_generation", self.prompt_version)

        try:
            summary_raw = self.llm.generate(
                prompt=stage2_prompt,
                system_prompt=stage2_system,
                response_schema=SummaryStageOutput,
            )
            if isinstance(summary_raw, dict):
                stage2_output = SummaryStageOutput.model_validate(summary_raw)
            else:
                stage2_output = SummaryStageOutput.model_validate_json(summary_raw)
        except Exception as exc:
            logger.error("Stage 2 Summary Generation failed: %s", exc)
            raise PipelineError(f"Stage 2 Summary Generation failed: {exc}") from exc

        logger.info(
            "Stage 2 complete: overview (%d chars), %d concepts, %d terms, %d formulas",
            len(stage2_output.overview),
            len(stage2_output.concepts),
            len(stage2_output.key_terms),
            len(stage2_output.formulas),
        )

        # ---------------------------------------------------------------------
        # STAGE 3: Question Generation (with Stage 4 Schema Validation & Retries)
        # ---------------------------------------------------------------------
        if status_callback:
            status_callback("generating_questions", DocumentStatus.GENERATING_QUESTIONS)

        logger.info("Stage 3: Generating balanced practice questions...")
        stage3_system = get_prompt("question_generation", self.prompt_version)

        stage3_prompt_base = (
            f"Primary Topic: {identified_topic}\n\n"
            f"Overview:\n{stage2_output.overview}\n\n"
            f"Concepts:\n{[c.model_dump() for c in stage2_output.concepts]}\n\n"
            f"Source Document Reference Material:\n{source_context}\n\n"
            "Generate a balanced set of practice questions (MCQs with exactly 4 options labeled A-D, "
            "short-answer, and conceptual questions) with detailed explanations and source citations."
        )

        # Stage 4 Retry loop for question generation / schema validation
        max_retries = settings.MAX_RETRY_ATTEMPTS
        attempt = 0
        questions_output: QuestionStageOutput | None = None
        last_error = None
        feedback_addon = ""

        while attempt <= max_retries:
            prompt_to_send = stage3_prompt_base + feedback_addon
            try:
                raw_q = self.llm.generate(
                    prompt=prompt_to_send,
                    system_prompt=stage3_system,
                    response_schema=QuestionStageOutput,
                )
                if isinstance(raw_q, dict):
                    questions_output = QuestionStageOutput.model_validate(raw_q)
                else:
                    questions_output = QuestionStageOutput.model_validate_json(raw_q)

                if questions_output and questions_output.practice_questions:
                    logger.info(
                        "Stage 3 success on attempt %d: generated %d questions",
                        attempt + 1,
                        len(questions_output.practice_questions),
                    )
                    break
            except (ValidationError, Exception) as exc:
                last_error = exc
                attempt += 1
                logger.warning(
                    "Stage 3 attempt %d failed schema validation: %s. Retrying with error feedback...",
                    attempt,
                    exc,
                )
                feedback_addon = (
                    f"\n\nPREVIOUS GENERATION ATTEMPT FAILED WITH VALIDATION ERROR:\n{exc}\n"
                    "CRITICAL FIXES REQUIRED:\n"
                    "- Every MCQ must have exactly 4 options with labels 'A', 'B', 'C', 'D'.\n"
                    "- The correct_answer must be strictly one of 'A', 'B', 'C', or 'D'.\n"
                    "- Non-MCQ questions must have options: null.\n"
                    "Please regenerate the questions strictly adhering to the schema."
                )

        if not questions_output or not questions_output.practice_questions:
            if last_error:
                logger.error("Stage 3 Question Generation exhausted all retries: %s", last_error)
                raise PipelineError(
                    f"Question Generation failed after {max_retries} retries: {last_error}"
                )
            questions_output = QuestionStageOutput(practice_questions=[])

        # ---------------------------------------------------------------------
        # STAGE 4: Final Assembly & Schema Validation
        # ---------------------------------------------------------------------
        elapsed_seconds = round(time.time() - start_time, 2)
        token_usage = self.llm.get_token_usage()

        pipeline_meta = PipelineMetadata(
            prompt_version=self.prompt_version,
            model_name=getattr(self.llm, "model_name", settings.GEMINI_MODEL),
            retry_count=attempt,
            processing_time_seconds=elapsed_seconds,
            token_usage=token_usage,
        )

        study_metadata = StudyPackMetadata(
            topic=identified_topic,
            document_id=doc_uuid,
            source_pages=all_pages,
            generated_at=datetime.now(timezone.utc),
        )

        summary_model = Summary(
            overview=stage2_output.overview,
            detailed_summary=stage2_output.detailed_summary,
        )

        try:
            complete_pack = StudyPackContent(
                metadata=study_metadata,
                summary=summary_model,
                concepts=stage2_output.concepts,
                key_terms=stage2_output.key_terms,
                formulas=stage2_output.formulas,
                practice_questions=questions_output.practice_questions,
                evaluation=None,
                pipeline_metadata=pipeline_meta,
            )
            logger.info(
                "StudyPackPipeline completed successfully for doc %s in %.2fs",
                document_id,
                elapsed_seconds,
            )
            return complete_pack
        except ValidationError as val_err:
            logger.error("Final StudyPackContent schema validation failed: %s", val_err)
            raise PipelineError(
                f"Final StudyPackContent schema validation failed: {val_err}"
            ) from val_err

    def regenerate_section(
        self,
        study_pack: StudyPackContent,
        section: str,
        chunks: list[DocumentChunk],
        feedback: Optional[str] = None,
    ) -> StudyPackContent:
        """Regenerate a specific section of an existing study pack with optional targeted feedback.

        Supported sections: 'summary', 'concepts', 'key_terms', 'formulas', 'questions', 'practice_questions'.

        Args:
            study_pack: Existing complete StudyPackContent.
            section: Name of section to regenerate.
            chunks: Document text chunks for source context.
            feedback: Optional audit feedback or instructions explaining why regeneration is needed.

        Returns:
            Updated StudyPackContent with the refreshed section.
        """
        source_context = self._format_chunks_context(chunks)
        feedback_str = f"\nSpecific improvement feedback:\n{feedback}" if feedback else ""
        normalized_section = section.strip().lower()

        logger.info(
            "Regenerating section '%s' for study pack '%s'...",
            normalized_section,
            study_pack.metadata.topic,
        )

        if normalized_section in ("questions", "practice_questions"):
            stage3_system = get_prompt("question_generation", self.prompt_version)
            prompt = (
                f"Primary Topic: {study_pack.metadata.topic}\n\n"
                f"Summary Overview:\n{study_pack.summary.overview}\n\n"
                f"Source Lecture Chunks:\n{source_context}\n\n"
                f"{feedback_str}\n\n"
                "Regenerate a balanced, rigorous set of practice questions (MCQs, short answer, conceptual)."
            )
            raw = self.llm.generate(
                prompt=prompt, system_prompt=stage3_system, response_schema=QuestionStageOutput
            )
            parsed = (
                QuestionStageOutput.model_validate(raw)
                if isinstance(raw, dict)
                else QuestionStageOutput.model_validate_json(raw)
            )
            if parsed.practice_questions:
                study_pack.practice_questions = parsed.practice_questions

        elif normalized_section in ("summary", "overview", "detailed_summary"):
            stage2_system = get_prompt("summary_generation", self.prompt_version)
            prompt = (
                f"Primary Topic: {study_pack.metadata.topic}\n\n"
                f"Existing Concepts:\n{[c.model_dump() for c in study_pack.concepts]}\n\n"
                f"Source Lecture Chunks:\n{source_context}\n\n"
                f"{feedback_str}\n\n"
                "Regenerate the overview and detailed summary grounded strictly in the source material."
            )
            raw = self.llm.generate(
                prompt=prompt, system_prompt=stage2_system, response_schema=SummaryStageOutput
            )
            parsed = (
                SummaryStageOutput.model_validate(raw)
                if isinstance(raw, dict)
                else SummaryStageOutput.model_validate_json(raw)
            )
            study_pack.summary = Summary(
                overview=parsed.overview,
                detailed_summary=parsed.detailed_summary,
            )

        elif normalized_section in ("concepts", "core_concepts"):
            stage2_system = get_prompt("summary_generation", self.prompt_version)
            prompt = (
                f"Primary Topic: {study_pack.metadata.topic}\n\n"
                f"Source Lecture Chunks:\n{source_context}\n\n"
                f"{feedback_str}\n\n"
                "Regenerate the core concepts with clear descriptions and source references."
            )
            raw = self.llm.generate(
                prompt=prompt, system_prompt=stage2_system, response_schema=SummaryStageOutput
            )
            parsed = (
                SummaryStageOutput.model_validate(raw)
                if isinstance(raw, dict)
                else SummaryStageOutput.model_validate_json(raw)
            )
            if parsed.concepts:
                study_pack.concepts = parsed.concepts

        elif normalized_section in ("key_terms", "glossary"):
            stage2_system = get_prompt("summary_generation", self.prompt_version)
            prompt = (
                f"Primary Topic: {study_pack.metadata.topic}\n\n"
                f"Source Lecture Chunks:\n{source_context}\n\n"
                f"{feedback_str}\n\n"
                "Regenerate the key terms glossary with precise definitions and source citations."
            )
            raw = self.llm.generate(
                prompt=prompt, system_prompt=stage2_system, response_schema=SummaryStageOutput
            )
            parsed = (
                SummaryStageOutput.model_validate(raw)
                if isinstance(raw, dict)
                else SummaryStageOutput.model_validate_json(raw)
            )
            if parsed.key_terms:
                study_pack.key_terms = parsed.key_terms

        elif normalized_section in ("formulas", "equations"):
            stage2_system = get_prompt("summary_generation", self.prompt_version)
            prompt = (
                f"Primary Topic: {study_pack.metadata.topic}\n\n"
                f"Source Lecture Chunks:\n{source_context}\n\n"
                f"{feedback_str}\n\n"
                "Regenerate the formula list with expressions, descriptions, and citations."
            )
            raw = self.llm.generate(
                prompt=prompt, system_prompt=stage2_system, response_schema=SummaryStageOutput
            )
            parsed = (
                SummaryStageOutput.model_validate(raw)
                if isinstance(raw, dict)
                else SummaryStageOutput.model_validate_json(raw)
            )
            if parsed.formulas:
                study_pack.formulas = parsed.formulas

        else:
            logger.warning("Unrecognized section to regenerate: '%s'", section)

        return study_pack
