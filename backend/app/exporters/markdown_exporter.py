"""Markdown export engine for LectureForge AI study packs.

Renders complete StudyPackContent into clean, publication-ready Markdown with
hierarchical typography, formatted MCQ options, citations, answer keys, and quality audits.
"""

from __future__ import annotations

from typing import List, Optional

from app.schemas.study_pack import (
    Concept,
    DifficultyLevel,
    EvaluationResult,
    Formula,
    KeyTerm,
    PracticeQuestion,
    QuestionType,
    SourceReference,
    StudyPackContent,
)


class MarkdownExporter:
    """Exports structured StudyPackContent into clean, formatted Markdown."""

    def _format_ref(self, ref: SourceReference | None) -> str:
        """Format a SourceReference citation string."""
        if not ref:
            return ""
        parts = []
        if ref.page_numbers:
            p_str = ", ".join(str(p) for p in ref.page_numbers)
            parts.append(f"Page {p_str}" if len(ref.page_numbers) == 1 else f"Pages {p_str}")
        if ref.slide_numbers:
            s_str = ", ".join(str(s) for s in ref.slide_numbers)
            parts.append(f"Slide {s_str}" if len(ref.slide_numbers) == 1 else f"Slides {s_str}")
        if ref.section_title:
            parts.append(f"Section: {ref.section_title}")

        if parts:
            return f" *({', '.join(parts)})*"
        return ""

    def export(self, study_pack: StudyPackContent) -> str:
        """Generate a complete Markdown document from a study pack artifact.

        Args:
            study_pack: Complete StudyPackContent object.

        Returns:
            Formatted Markdown document string.
        """
        lines: list[str] = []

        # ---------------------------------------------------------------------
        # Document Header & Metadata
        # ---------------------------------------------------------------------
        topic = study_pack.metadata.topic or "Lecture Study Pack"
        lines.append(f"# {topic}")
        lines.append("")

        date_str = study_pack.metadata.generated_at.strftime("%B %d, %Y")
        pages_str = (
            ", ".join(str(p) for p in study_pack.metadata.source_pages)
            if study_pack.metadata.source_pages
            else "All"
        )
        lines.append(f"> **LectureForge AI Study Pack**  ")
        lines.append(
            f"> **Topic:** {topic} | **Source Pages:** {pages_str} | **Generated:** {date_str}  "
        )
        if study_pack.pipeline_metadata:
            model_info = f"Model: {study_pack.pipeline_metadata.model_name} ({study_pack.pipeline_metadata.prompt_version})"
            lines.append(f"> *{model_info}*")
        lines.append("")
        lines.append("---")
        lines.append("")

        # ---------------------------------------------------------------------
        # Table of Contents
        # ---------------------------------------------------------------------
        lines.append("## Table of Contents")
        lines.append("1. [Executive Overview](#1-executive-overview)")
        lines.append("2. [Detailed Summary](#2-detailed-summary)")
        lines.append("3. [Core Academic Concepts](#3-core-academic-concepts)")
        lines.append("4. [Key Terms & Glossary](#4-key-terms--glossary)")
        lines.append("5. [Formulas & Key Equations](#5-formulas--key-equations)")
        lines.append("6. [Practice Questions](#6-practice-questions)")
        lines.append("   - [6.1 Multiple Choice Questions](#61-multiple-choice-questions)")
        lines.append("   - [6.2 Short Answer Questions](#62-short-answer-questions)")
        lines.append(
            "   - [6.3 Conceptual & Synthesis Questions](#63-conceptual--synthesis-questions)"
        )
        lines.append(
            "7. [Answer Key & Detailed Explanations](#7-answer-key--detailed-explanations)"
        )
        if study_pack.evaluation:
            lines.append(
                "8. [Quality Audit & Evaluation Report](#8-quality-audit--evaluation-report)"
            )
        lines.append("")
        lines.append("---")
        lines.append("")

        # ---------------------------------------------------------------------
        # 1. Executive Overview
        # ---------------------------------------------------------------------
        lines.append("## 1. Executive Overview")
        lines.append("")
        lines.append(study_pack.summary.overview.strip())
        lines.append("")
        lines.append("---")
        lines.append("")

        # ---------------------------------------------------------------------
        # 2. Detailed Summary
        # ---------------------------------------------------------------------
        lines.append("## 2. Detailed Summary")
        lines.append("")
        lines.append(study_pack.summary.detailed_summary.strip())
        lines.append("")
        lines.append("---")
        lines.append("")

        # ---------------------------------------------------------------------
        # 3. Core Academic Concepts
        # ---------------------------------------------------------------------
        lines.append("## 3. Core Academic Concepts")
        lines.append("")
        if study_pack.concepts:
            for idx, concept in enumerate(study_pack.concepts, 1):
                citation = self._format_ref(concept.source_ref)
                lines.append(f"### 3.{idx} {concept.name}{citation}")
                lines.append(f"{concept.description.strip()}")
                lines.append("")
        else:
            lines.append("*No concepts extracted.*")
            lines.append("")
        lines.append("---")
        lines.append("")

        # ---------------------------------------------------------------------
        # 4. Key Terms & Glossary
        # ---------------------------------------------------------------------
        lines.append("## 4. Key Terms & Glossary")
        lines.append("")
        if study_pack.key_terms:
            for term in study_pack.key_terms:
                citation = self._format_ref(term.source_ref)
                lines.append(f"- **{term.term}**{citation}: {term.definition.strip()}")
            lines.append("")
        else:
            lines.append("*No glossary items provided.*")
            lines.append("")
        lines.append("---")
        lines.append("")

        # ---------------------------------------------------------------------
        # 5. Formulas & Key Equations
        # ---------------------------------------------------------------------
        lines.append("## 5. Formulas & Key Equations")
        lines.append("")
        if study_pack.formulas:
            for idx, formula in enumerate(study_pack.formulas, 1):
                citation = self._format_ref(formula.source_ref)
                lines.append(f"#### Formula {idx}: {formula.description}{citation}")
                lines.append("```latex")
                lines.append(formula.expression.strip())
                lines.append("```")
                lines.append("")
        else:
            lines.append("*No mathematical formulas or algorithms documented.*")
            lines.append("")
        lines.append("---")
        lines.append("")

        # ---------------------------------------------------------------------
        # 6. Practice Questions (Grouped by QuestionType)
        # ---------------------------------------------------------------------
        lines.append("## 6. Practice Questions")
        lines.append("")

        mcqs = [q for q in study_pack.practice_questions if q.question_type == QuestionType.MCQ]
        short_answers = [
            q for q in study_pack.practice_questions if q.question_type == QuestionType.SHORT_ANSWER
        ]
        conceptual = [
            q for q in study_pack.practice_questions if q.question_type == QuestionType.CONCEPTUAL
        ]

        # 6.1 MCQs
        lines.append("### 6.1 Multiple Choice Questions")
        lines.append("")
        if mcqs:
            for idx, q in enumerate(mcqs, 1):
                citation = self._format_ref(q.source_ref)
                diff_tag = f"*(Difficulty: {q.difficulty.value.capitalize()})*"
                lines.append(f"**Question {idx}** {diff_tag}{citation}  ")
                lines.append(f"{q.question_text.strip()}")
                lines.append("")
                if q.options:
                    for opt in q.options:
                        lines.append(f"- [ ] **{opt.label})** {opt.text}")
                lines.append("")
        else:
            lines.append("*No multiple choice questions.*")
            lines.append("")

        # 6.2 Short Answer
        lines.append("### 6.2 Short Answer Questions")
        lines.append("")
        if short_answers:
            for idx, q in enumerate(short_answers, 1):
                citation = self._format_ref(q.source_ref)
                diff_tag = f"*(Difficulty: {q.difficulty.value.capitalize()})*"
                lines.append(f"**Question {idx}** {diff_tag}{citation}  ")
                lines.append(f"{q.question_text.strip()}")
                lines.append("")
        else:
            lines.append("*No short answer questions.*")
            lines.append("")

        # 6.3 Conceptual
        lines.append("### 6.3 Conceptual & Synthesis Questions")
        lines.append("")
        if conceptual:
            for idx, q in enumerate(conceptual, 1):
                citation = self._format_ref(q.source_ref)
                diff_tag = f"*(Difficulty: {q.difficulty.value.capitalize()})*"
                lines.append(f"**Question {idx}** {diff_tag}{citation}  ")
                lines.append(f"{q.question_text.strip()}")
                lines.append("")
        else:
            lines.append("*No conceptual questions.*")
            lines.append("")
        lines.append("---")
        lines.append("")

        # ---------------------------------------------------------------------
        # 7. Answer Key & Comprehensive Explanations
        # ---------------------------------------------------------------------
        lines.append("## 7. Answer Key & Detailed Explanations")
        lines.append("")

        if study_pack.practice_questions:
            for idx, q in enumerate(study_pack.practice_questions, 1):
                citation = self._format_ref(q.source_ref)
                type_label = q.question_type.value.replace("_", " ").title()
                lines.append(f"### Item {idx} ({type_label})")
                lines.append(f"**Prompt:** {q.question_text.strip()}")
                lines.append("")
                lines.append(f"**Correct Solution:** `{q.correct_answer}`{citation}")
                lines.append("")
                lines.append(f"**Step-by-Step Reasoning:**  ")
                lines.append(f"{q.explanation.strip()}")
                lines.append("")
        else:
            lines.append("*No answer key available.*")
            lines.append("")
        lines.append("---")
        lines.append("")

        # ---------------------------------------------------------------------
        # 8. Quality Audit & Evaluation Report
        # ---------------------------------------------------------------------
        if study_pack.evaluation:
            ev = study_pack.evaluation
            lines.append("## 8. Quality Audit & Evaluation Report")
            lines.append("")
            lines.append("| Quality Metric | Weight | Rating | Benchmark |")
            lines.append("| :--- | :---: | :---: | :---: |")
            lines.append(
                f"| **Faithfulness & Grounding** | 35% | {ev.faithfulness} / 5 | {'Passed' if ev.faithfulness >= 4 else 'Needs Work'} |"
            )
            lines.append(
                f"| **Topic Coverage** | 25% | {ev.coverage} / 5 | {'Passed' if ev.coverage >= 4 else 'Needs Work'} |"
            )
            lines.append(
                f"| **Answer Accuracy** | 25% | {ev.answer_accuracy} / 5 | {'Passed' if ev.answer_accuracy >= 4 else 'Needs Work'} |"
            )
            lines.append(
                f"| **Pedagogical Clarity** | 15% | {ev.clarity} / 5 | {'Passed' if ev.clarity >= 4 else 'Needs Work'} |"
            )
            lines.append(
                f"| **Overall Weighted Score** | **100%** | **{ev.overall_score:.2f} / 5.0** | **{'PASSED' if ev.passed else 'WARNING'}** |"
            )
            lines.append("")

            if ev.issues:
                lines.append("**Audit Notes & Findings:**")
                for iss in ev.issues:
                    lines.append(f"- {iss}")
                lines.append("")
            else:
                lines.append("*All automated quality and integrity benchmarks passed.*")
                lines.append("")

        return "\n".join(lines)
