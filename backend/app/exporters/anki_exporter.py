"""Anki CSV flashcard export engine for LectureForge AI study packs.

Transforms practice questions (MCQ, short answer, conceptual) and glossary key terms
into standard Anki-importable CSV format (Front, Back, Tags) with HTML formatting,
appropriate escaping, and hierarchical tags.
"""

from __future__ import annotations

import csv
import io
import re
from typing import List

from app.schemas.study_pack import (
    KeyTerm,
    PracticeQuestion,
    QuestionType,
    SourceReference,
    StudyPackContent,
)


class AnkiExporter:
    """Exports StudyPackContent into Anki-compatible CSV flashcards."""

    def _sanitize_tag(self, text: str) -> str:
        """Sanitize a string into a valid Anki tag (no spaces or illegal punctuation)."""
        if not text:
            return "general"
        clean = re.sub(r"[^\w-]", "_", text.strip())
        clean = re.sub(r"_{2,}", "_", clean).strip("_")
        return clean or "general"

    def _format_citation_html(self, ref: SourceReference | None) -> str:
        """Format an HTML footnote for citations."""
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
            parts.append(ref.section_title)

        if parts:
            return f"<br><small style='color: #718096;'>Source: {', '.join(parts)}</small>"
        return ""

    def export(self, study_pack: StudyPackContent) -> str:
        """Export questions and glossary terms into Anki CSV format: Front, Back, Tags.

        Args:
            study_pack: The StudyPackContent artifact.

        Returns:
            CSV formatted string ready for direct file saving and Anki import.
        """
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_ALL, lineterminator="\n")

        # Anki CSV Header
        writer.writerow(["Front", "Back", "Tags"])

        topic_tag = self._sanitize_tag(study_pack.metadata.topic)

        # ---------------------------------------------------------------------
        # 1. Practice Questions Flashcards
        # ---------------------------------------------------------------------
        for q in study_pack.practice_questions:
            citation_html = self._format_citation_html(q.source_ref)

            # Build Front of card
            front_parts = [q.question_text.strip().replace("\n", "<br>")]

            if q.question_type == QuestionType.MCQ and q.options:
                front_parts.append("<br><br><div style='text-align: left;'>")
                for opt in q.options:
                    front_parts.append(f"<b>{opt.label})</b> {opt.text}<br>")
                front_parts.append("</div>")

            if citation_html:
                front_parts.append(citation_html)

            front = "".join(front_parts)

            # Build Back of card
            back_parts = []
            if q.question_type == QuestionType.MCQ:
                back_parts.append(
                    f"<div style='font-size: 1.1em;'><b>Correct Answer:</b> {q.correct_answer}</div>"
                )
            else:
                back_parts.append(
                    f"<div style='font-size: 1.1em;'><b>Model Solution:</b><br>{q.correct_answer}</div>"
                )

            if q.explanation and q.explanation.strip():
                clean_exp = q.explanation.strip().replace("\n", "<br>")
                back_parts.append(
                    f"<br><div style='border-top: 1px solid #cbd5e0; padding-top: 6px; font-size: 0.9em;'><b>Explanation:</b><br>{clean_exp}</div>"
                )

            back = "".join(back_parts)

            # Build Tags: topic, difficulty, question_type
            diff_tag = f"difficulty::{q.difficulty.value}"
            type_tag = f"type::{q.question_type.value}"
            tags = f"lectureforge topic::{topic_tag} {diff_tag} {type_tag}"

            writer.writerow([front, back, tags])

        # ---------------------------------------------------------------------
        # 2. Key Terms / Glossary Flashcards
        # ---------------------------------------------------------------------
        for term in study_pack.key_terms:
            citation_html = self._format_citation_html(term.source_ref)
            front = f"<div style='font-size: 1.2em; font-weight: bold;'>{term.term}</div>{citation_html}"
            back = f"<div>{term.definition.strip().replace(chr(10), '<br>')}</div>"
            tags = f"lectureforge topic::{topic_tag} type::glossary"

            writer.writerow([front, back, tags])

        return output.getvalue()
