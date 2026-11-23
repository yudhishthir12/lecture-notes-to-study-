"""Targeted retry routing engine for LectureForge AI study packs.

Determines failure root causes from evaluation reports, builds targeted corrective
prompts for defective sections, enforces the maximum retry limit (2), and merges
regenerated sections while preserving valid components.
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from app.schemas.study_pack import (
    Concept,
    EvaluationResult,
    Formula,
    KeyTerm,
    PracticeQuestion,
    StudyPackContent,
    Summary,
)

logger = logging.getLogger(__name__)


class RetryPlan(BaseModel):
    """Execution plan detailing which sections to regenerate and specific feedback."""

    sections_to_retry: list[str] = Field(default_factory=list)
    feedback: dict[str, str] = Field(
        default_factory=dict,
        description="Targeted correction instructions keyed by section name",
    )
    retry_count: int = Field(default=0, ge=0)
    should_retry: bool = Field(default=False)
    reason: str = Field(default="")


class RetryRouter:
    """Routes quality audit failures into targeted section regeneration plans."""

    MAX_RETRIES: int = 2

    def route_retry(
        self,
        evaluation: EvaluationResult,
        study_pack: StudyPackContent,
        current_retry_count: int = 0,
    ) -> RetryPlan:
        """Analyze evaluation results and formulate a targeted section retry plan.

        Args:
            evaluation: Result of deterministic and LLM quality evaluation.
            study_pack: Current StudyPackContent under audit.
            current_retry_count: Number of retries already completed for this document.

        Returns:
            RetryPlan with sections_to_retry, feedback dictionary, and should_retry flag.
        """
        # 1. Check if study pack passed
        if evaluation.passed:
            logger.info(
                "Evaluation passed (overall score: %.2f). No retries required.",
                evaluation.overall_score,
            )
            return RetryPlan(
                sections_to_retry=[],
                feedback={},
                retry_count=current_retry_count,
                should_retry=False,
                reason="Study pack passed evaluation benchmarks with high quality.",
            )

        # 2. Enforce maximum retry threshold
        if current_retry_count >= self.MAX_RETRIES:
            logger.warning(
                "Maximum retry limit (%d) reached. Aborting retry loop; saving with warning.",
                self.MAX_RETRIES,
            )
            return RetryPlan(
                sections_to_retry=[],
                feedback={},
                retry_count=current_retry_count,
                should_retry=False,
                reason=(
                    f"Maximum retry attempts ({self.MAX_RETRIES}) reached. "
                    f"Final overall score: {evaluation.overall_score}. Saving with warning status."
                ),
            )

        # 3. Identify candidate sections that failed quality checks
        failed_sections: list[str] = []
        for sec in evaluation.failed_sections:
            normalized = sec.strip().lower()
            if normalized in ("questions", "practice_questions"):
                failed_sections.append("practice_questions")
            elif normalized in ("summary", "overview", "detailed_summary"):
                failed_sections.append("summary")
            elif normalized in ("concepts", "core_concepts"):
                failed_sections.append("concepts")
            elif normalized in ("key_terms", "glossary"):
                failed_sections.append("key_terms")
            elif normalized in ("formulas", "equations"):
                failed_sections.append("formulas")
            else:
                failed_sections.append(normalized)

        # If failed_sections wasn't populated explicitly, deduce from scores & issues
        if not failed_sections:
            if evaluation.answer_accuracy < 4 or any(
                "question" in i.lower() or "mcq" in i.lower() for i in evaluation.issues
            ):
                failed_sections.append("practice_questions")
            if evaluation.coverage < 4:
                failed_sections.append("summary")
                failed_sections.append("concepts")
            if evaluation.faithfulness < 4:
                failed_sections.append("summary")
            if evaluation.clarity < 4 and "summary" not in failed_sections:
                failed_sections.append("summary")

        # Deduplicate while preserving order
        unique_failed_sections = list(dict.fromkeys(failed_sections))

        # 4. Formulate targeted feedback per section
        feedback_map: dict[str, str] = {}
        relevant_issues = evaluation.issues

        for section in unique_failed_sections:
            if section == "practice_questions":
                q_issues = [
                    i
                    for i in relevant_issues
                    if "question" in i.lower() or "mcq" in i.lower() or "answer" in i.lower()
                ]
                feedback_lines = [
                    f"Answer Accuracy score was {evaluation.answer_accuracy}/5. Please correct the following issues:"
                ]
                if q_issues:
                    feedback_lines.extend(f"- {iss}" for iss in q_issues)
                else:
                    feedback_lines.append(
                        "- Ensure all MCQs have exactly 4 choices labeled A, B, C, D with plausible distractors."
                    )
                    feedback_lines.append(
                        "- Ensure correct_answer strictly matches 'A', 'B', 'C', or 'D'."
                    )
                    feedback_lines.append(
                        "- Ensure all explanations provide sound, step-by-step reasoning."
                    )
                feedback_map[section] = "\n".join(feedback_lines)

            elif section == "summary":
                s_issues = [
                    i for i in relevant_issues if "summary" in i.lower() or "overview" in i.lower()
                ]
                feedback_lines = [
                    f"Coverage score: {evaluation.coverage}/5, Faithfulness score: {evaluation.faithfulness}/5."
                ]
                if s_issues:
                    feedback_lines.extend(f"- {iss}" for iss in s_issues)
                else:
                    feedback_lines.append(
                        "- Expand the detailed summary to thoroughly cover all core lecture concepts."
                    )
                    feedback_lines.append(
                        "- Adhere strictly to the source material to prevent any hallucination."
                    )
                feedback_map[section] = "\n".join(feedback_lines)

            elif section == "concepts":
                c_issues = [i for i in relevant_issues if "concept" in i.lower()]
                feedback_lines = [f"Coverage was {evaluation.coverage}/5."]
                if c_issues:
                    feedback_lines.extend(f"- {iss}" for iss in c_issues)
                else:
                    feedback_lines.append(
                        "- Extract comprehensive, self-contained concepts covering all main lecture topics with valid page references."
                    )
                feedback_map[section] = "\n".join(feedback_lines)

            elif section in ("key_terms", "formulas"):
                feedback_map[section] = (
                    f"Please regenerate {section} to ensure precise definitions, valid formulas, and accurate source page citations."
                )

        new_retry_count = current_retry_count + 1
        reason_msg = (
            f"Targeted retry {new_retry_count}/{self.MAX_RETRIES} initiated for sections: "
            f"{unique_failed_sections}. Overall score: {evaluation.overall_score}"
        )
        logger.info(reason_msg)

        return RetryPlan(
            sections_to_retry=unique_failed_sections,
            feedback=feedback_map,
            retry_count=new_retry_count,
            should_retry=len(unique_failed_sections) > 0,
            reason=reason_msg,
        )

    def apply_retry(
        self,
        original: StudyPackContent,
        regenerated_sections: dict[str, Any],
    ) -> StudyPackContent:
        """Merge regenerated sections into the original study pack, preserving unchanged content.

        Args:
            original: The initial StudyPackContent instance.
            regenerated_sections: Dictionary mapping section names to newly generated objects.

        Returns:
            Updated StudyPackContent with merged sections.
        """
        updated = original.model_copy(deep=True)

        for sec_name, sec_val in regenerated_sections.items():
            normalized = sec_name.strip().lower()

            if normalized in ("questions", "practice_questions"):
                if isinstance(sec_val, list):
                    updated.practice_questions = [
                        q if isinstance(q, PracticeQuestion) else PracticeQuestion.model_validate(q)
                        for q in sec_val
                    ]
                logger.info(
                    "Applied retry update to practice_questions (%d items)",
                    len(updated.practice_questions),
                )

            elif normalized in ("summary", "overview", "detailed_summary"):
                if isinstance(sec_val, Summary):
                    updated.summary = sec_val
                elif isinstance(sec_val, dict):
                    updated.summary = Summary.model_validate(sec_val)
                logger.info("Applied retry update to summary")

            elif normalized in ("concepts", "core_concepts"):
                if isinstance(sec_val, list):
                    updated.concepts = [
                        c if isinstance(c, Concept) else Concept.model_validate(c) for c in sec_val
                    ]
                logger.info("Applied retry update to concepts (%d items)", len(updated.concepts))

            elif normalized in ("key_terms", "glossary"):
                if isinstance(sec_val, list):
                    updated.key_terms = [
                        k if isinstance(k, KeyTerm) else KeyTerm.model_validate(k) for k in sec_val
                    ]
                logger.info("Applied retry update to key_terms (%d items)", len(updated.key_terms))

            elif normalized in ("formulas", "equations"):
                if isinstance(sec_val, list):
                    updated.formulas = [
                        f if isinstance(f, Formula) else Formula.model_validate(f) for f in sec_val
                    ]
                logger.info("Applied retry update to formulas (%d items)", len(updated.formulas))

            else:
                logger.warning("Unknown section key in regenerated_sections: '%s'", sec_name)

        return updated
