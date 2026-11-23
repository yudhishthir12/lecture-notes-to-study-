"""Quality evaluation engine for LectureForge AI study packs.

Performs deterministic integrity checks (MCQ schema, answer presence, duplicate detection,
valid citations) and subjective LLM evaluation across Faithfulness (35%), Coverage (25%),
Answer Accuracy (25%), and Clarity (15%).
"""

from __future__ import annotations

import logging
from typing import List, Optional

from pydantic import BaseModel, Field

from app.core.config import settings
from app.schemas.pipeline import DocumentChunk
from app.schemas.study_pack import (
    EvaluationResult,
    QuestionType,
    StudyPackContent,
)
from app.services.llm_service import LLMService, get_llm_service
from app.services.prompt_registry import get_prompt

logger = logging.getLogger(__name__)


class LLMEvaluationSchema(BaseModel):
    """Schema for LLM subjective evaluation output."""

    faithfulness: int = Field(..., ge=1, le=5)
    coverage: int = Field(..., ge=1, le=5)
    answer_accuracy: int = Field(..., ge=1, le=5)
    clarity: int = Field(..., ge=1, le=5)
    issues: list[str] = Field(default_factory=list)
    failed_sections: list[str] = Field(default_factory=list)


class StudyPackEvaluator:
    """Evaluates study packs using deterministic validation and LLM self-reflection."""

    def __init__(
        self,
        llm_service: LLMService | None = None,
        prompt_version: str | None = None,
    ) -> None:
        """Initialize the evaluator."""
        self.llm = llm_service or get_llm_service()
        self.prompt_version = prompt_version or settings.PROMPT_VERSION

    def deterministic_checks(self, study_pack: StudyPackContent) -> list[str]:
        """Perform strict deterministic static analysis on generated study pack content.

        Checks:
        1. No empty answers, question texts, or explanations.
        2. MCQs have exactly 4 options with distinct labels A, B, C, D and valid correct_answer.
        3. No duplicate questions.
        4. Valid source references (no zero or negative page/slide numbers).
        5. Required fields present and non-empty.

        Returns:
            List of detected issues. Empty list means passed with zero anomalies.
        """
        issues: list[str] = []

        # 1. Required fields presence checks
        if not study_pack.summary.overview or len(study_pack.summary.overview.strip()) < 20:
            issues.append("Summary overview is missing or excessively brief.")

        if (
            not study_pack.summary.detailed_summary
            or len(study_pack.summary.detailed_summary.strip()) < 50
        ):
            issues.append("Detailed summary is missing or insufficiently detailed.")

        if not study_pack.concepts:
            issues.append("No academic concepts were extracted.")

        if not study_pack.practice_questions:
            issues.append("No practice questions were generated.")

        # 2. Duplicate question detection
        seen_questions: set[str] = set()
        for i, q in enumerate(study_pack.practice_questions):
            q_norm = " ".join(q.question_text.lower().split())
            if q_norm in seen_questions:
                issues.append(f"Duplicate question detected: '{q.question_text[:60]}...'")
            else:
                seen_questions.add(q_norm)

            # 3. Question completeness and answer presence
            if not q.question_text or not q.question_text.strip():
                issues.append(f"Question #{i + 1} (id: {q.id}) has empty question text.")

            if not q.correct_answer or not q.correct_answer.strip():
                issues.append(f"Question #{i + 1} (id: {q.id}) has empty correct_answer.")

            if not q.explanation or not q.explanation.strip():
                issues.append(f"Question #{i + 1} (id: {q.id}) has empty explanation.")

            # 4. MCQ structural constraints
            if q.question_type == QuestionType.MCQ:
                if not q.options:
                    issues.append(f"MCQ question '{q.id}' has no options provided.")
                elif len(q.options) != 4:
                    issues.append(
                        f"MCQ question '{q.id}' must have exactly 4 options, found {len(q.options)}."
                    )
                else:
                    labels = [opt.label.strip().upper() for opt in q.options]
                    if sorted(labels) != ["A", "B", "C", "D"]:
                        issues.append(
                            f"MCQ question '{q.id}' option labels must be A, B, C, D. Found: {labels}."
                        )
                    for opt in q.options:
                        if not opt.text or not opt.text.strip():
                            issues.append(
                                f"MCQ question '{q.id}' option '{opt.label}' has empty text."
                            )

                clean_ans = q.correct_answer.strip().upper()
                if clean_ans not in {"A", "B", "C", "D"}:
                    issues.append(
                        f"MCQ question '{q.id}' correct_answer must be 'A', 'B', 'C', or 'D'. Found: {q.correct_answer!r}."
                    )

            # 5. Question Source Reference validation
            if q.source_ref:
                for p in q.source_ref.page_numbers:
                    if p <= 0:
                        issues.append(
                            f"Question '{q.id}' references invalid page number {p} (must be > 0)."
                        )
                if q.source_ref.slide_numbers:
                    for s in q.source_ref.slide_numbers:
                        if s < 0:
                            issues.append(f"Question '{q.id}' references invalid slide number {s}.")

        # 6. Concept Source Reference validation
        for c in study_pack.concepts:
            if c.source_ref:
                for p in c.source_ref.page_numbers:
                    if p <= 0:
                        issues.append(
                            f"Concept '{c.name}' references invalid page number {p} (must be > 0)."
                        )
                if c.source_ref.slide_numbers:
                    for s in c.source_ref.slide_numbers:
                        if s < 0:
                            issues.append(
                                f"Concept '{c.name}' references invalid slide number {s}."
                            )

        # 7. Formula Source Reference validation
        for f in study_pack.formulas:
            if f.source_ref:
                for p in f.source_ref.page_numbers:
                    if p <= 0:
                        issues.append(
                            f"Formula '{f.expression[:20]}' references invalid page number {p}."
                        )

        return issues

    def evaluate(
        self,
        study_pack: StudyPackContent,
        source_text: str = "",
        chunks: Optional[list[DocumentChunk]] = None,
    ) -> EvaluationResult:
        """Evaluate a study pack using deterministic checks and subjective LLM scoring.

        Weights:
        - Faithfulness: 35%
        - Coverage: 25%
        - Answer Accuracy: 25%
        - Clarity: 15%

        Benchmark pass requires:
        - Each criterion >= 4
        - overall_score >= 4.0
        - Zero critical deterministic flaws.

        Args:
            study_pack: Target StudyPackContent to evaluate.
            source_text: Optional plain text of source lecture notes.
            chunks: Optional list of DocumentChunk objects.

        Returns:
            EvaluationResult detailing scores, issues, failed sections, and pass status.
        """
        # 1. Run deterministic checks first
        det_issues = self.deterministic_checks(study_pack)

        # Build source context representation
        context_str = source_text
        if not context_str and chunks:
            context_str = "\n".join(f"[{c.chunk_id}] {c.text}" for c in chunks[:15])

        # Truncate source context if excessively large (keep first 8,000 chars for eval)
        truncated_context = context_str[:8000] if len(context_str) > 8000 else context_str

        # 2. Subjective evaluation via LLM (or fallback if unconfigured)
        faithfulness = 5
        coverage = 5
        answer_accuracy = 5
        clarity = 5
        llm_issues: list[str] = []
        failed_sections: list[str] = []

        if self.llm.is_configured():
            try:
                system_prompt = get_prompt("evaluation", self.prompt_version)
                eval_input = {
                    "topic": study_pack.metadata.topic,
                    "overview": study_pack.summary.overview,
                    "concept_names": [c.name for c in study_pack.concepts],
                    "sample_questions": [
                        {
                            "type": q.question_type.value,
                            "question": q.question_text,
                            "answer": q.correct_answer,
                            "explanation": q.explanation,
                        }
                        for q in study_pack.practice_questions[:8]
                    ],
                }

                user_prompt = (
                    f"Evaluate this Study Pack against the source lecture excerpts:\n\n"
                    f"SOURCE EXCERPTS:\n{truncated_context}\n\n"
                    f"STUDY PACK ARTIFACTS:\n{eval_input}\n\n"
                    "Provide integer ratings (1-5) for faithfulness, coverage, answer_accuracy, and clarity."
                )

                raw_eval = self.llm.generate(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    response_schema=LLMEvaluationSchema,
                )

                if isinstance(raw_eval, dict):
                    eval_obj = LLMEvaluationSchema.model_validate(raw_eval)
                else:
                    eval_obj = LLMEvaluationSchema.model_validate_json(raw_eval)

                faithfulness = int(eval_obj.faithfulness)
                coverage = int(eval_obj.coverage)
                answer_accuracy = int(eval_obj.answer_accuracy)
                clarity = int(eval_obj.clarity)
                llm_issues = eval_obj.issues or []
                failed_sections = eval_obj.failed_sections or []

            except Exception as exc:
                logger.warning(
                    "LLM subjective evaluation failed, using deterministic scoring: %s", exc
                )
                # LLM failed, fallback to deterministic scoring below
                faithfulness, coverage, answer_accuracy, clarity = (
                    self._estimate_deterministic_scores(study_pack, det_issues)
                )
        else:
            logger.info("LLM not configured; generating deterministic evaluation scores.")
            faithfulness, coverage, answer_accuracy, clarity = self._estimate_deterministic_scores(
                study_pack, det_issues
            )

        # Normalize failed sections names to canonical section names
        normalized_failed = []
        for s in failed_sections:
            if s == "questions":
                normalized_failed.append("practice_questions")
            else:
                normalized_failed.append(s)
        failed_sections = list(dict.fromkeys(normalized_failed))

        # 3. Penalize scores if deterministic issues were detected
        question_issues = [
            iss for iss in det_issues if "question" in iss.lower() or "mcq" in iss.lower()
        ]
        content_issues = [
            iss for iss in det_issues if "summary" in iss.lower() or "concept" in iss.lower()
        ]
        ref_issues = [
            iss for iss in det_issues if "page number" in iss.lower() or "slide" in iss.lower()
        ]

        if question_issues:
            answer_accuracy = min(answer_accuracy, 3)
            if "practice_questions" not in failed_sections:
                failed_sections.append("practice_questions")

        if content_issues:
            coverage = min(coverage, 3)
            if "summary" not in failed_sections:
                failed_sections.append("summary")

        if ref_issues:
            faithfulness = min(faithfulness, 3)

        # Calculate weighted overall score
        # Faithfulness (35%), Coverage (25%), Answer Accuracy (25%), Clarity (15%)
        overall_score = round(
            (0.35 * faithfulness) + (0.25 * coverage) + (0.25 * answer_accuracy) + (0.15 * clarity),
            2,
        )
        # Ensure clamped between 1.0 and 5.0
        overall_score = max(1.0, min(5.0, overall_score))

        all_issues = det_issues + [iss for iss in llm_issues if iss not in det_issues]

        # Pass criteria: each criterion >= 4 AND overall >= 4.0 AND no deterministic flaws
        passed = (
            faithfulness >= 4
            and coverage >= 4
            and answer_accuracy >= 4
            and clarity >= 4
            and overall_score >= 4.0
            and len(det_issues) == 0
        )

        # Deduce failed sections if scores are below threshold
        if faithfulness < 4:
            if "summary" not in failed_sections:
                failed_sections.append("summary")
            if "concepts" not in failed_sections:
                failed_sections.append("concepts")

        if coverage < 4:
            if "concepts" not in failed_sections:
                failed_sections.append("concepts")
            if "summary" not in failed_sections:
                failed_sections.append("summary")

        if answer_accuracy < 4:
            if "practice_questions" not in failed_sections and "questions" not in failed_sections:
                failed_sections.append("practice_questions")

        if clarity < 4:
            if "summary" not in failed_sections:
                failed_sections.append("summary")

        return EvaluationResult(
            faithfulness=faithfulness,
            coverage=coverage,
            answer_accuracy=answer_accuracy,
            clarity=clarity,
            overall_score=overall_score,
            passed=passed,
            issues=all_issues,
            failed_sections=failed_sections,
        )

    def _estimate_deterministic_scores(
        self,
        study_pack: StudyPackContent,
        issues: list[str],
    ) -> tuple[int, int, int, int]:
        """Estimate criterion scores in offline or fallback mode using deterministic heuristics."""
        faithfulness = 5
        coverage = 5
        answer_accuracy = 5
        clarity = 5

        for issue in issues:
            iss_lower = issue.lower()
            if "mcq" in iss_lower or "question" in iss_lower or "answer" in iss_lower:
                answer_accuracy = max(1, answer_accuracy - 1)
            if "summary" in iss_lower or "concept" in iss_lower:
                coverage = max(1, coverage - 1)
            if "page" in iss_lower or "slide" in iss_lower or "reference" in iss_lower:
                faithfulness = max(1, faithfulness - 1)

        # Baseline checks on content richness
        if len(study_pack.concepts) < 3 or len(study_pack.practice_questions) < 3:
            coverage = min(coverage, 4)

        return (faithfulness, coverage, answer_accuracy, clarity)
