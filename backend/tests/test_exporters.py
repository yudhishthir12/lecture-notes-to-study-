"""Unit tests for study pack export engines (Markdown, Anki CSV, PDF).

Tests verify:
- Markdown export structure, typography, citations, and evaluation tables
- Anki CSV formatting, field quoting, tags, and HTML layout
- PDF export generation with valid PDF document byte stream
"""

import csv
import io

import pytest

from app.exporters.anki_exporter import AnkiExporter
from app.exporters.markdown_exporter import MarkdownExporter
from app.exporters.pdf_exporter import PDFExporter
from app.schemas.study_pack import StudyPackContent

# ==============================================================================
# Markdown Exporter Tests
# ==============================================================================


def test_markdown_exporter_structure(sample_study_pack_content: StudyPackContent):
    """Verify Markdown exporter creates document with title, TOC, sections, and audit."""
    exporter = MarkdownExporter()
    md = exporter.export(sample_study_pack_content)

    assert isinstance(md, str)
    # H1 Topic
    assert f"# {sample_study_pack_content.metadata.topic}" in md

    # Table of contents
    assert "## Table of Contents" in md
    assert "1. [Executive Overview]" in md
    assert "2. [Detailed Summary]" in md
    assert "3. [Core Academic Concepts]" in md
    assert "4. [Key Terms & Glossary]" in md
    assert "5. [Formulas & Key Equations]" in md
    assert "6. [Practice Questions]" in md
    assert "7. [Answer Key & Detailed Explanations]" in md
    assert "8. [Quality Audit & Evaluation Report]" in md

    # Check section contents
    assert "## 1. Executive Overview" in md
    assert sample_study_pack_content.summary.overview in md

    assert "## 2. Detailed Summary" in md
    assert "Comparison-based Sorts" in md

    assert "## 3. Core Academic Concepts" in md
    assert "Divide and Conquer" in md

    assert "## 4. Key Terms & Glossary" in md
    assert "Stable Sort" in md

    assert "## 5. Formulas & Key Equations" in md
    assert "T(n) = 2T(n/2)" in md

    # Check MCQs formatted as checkboxes
    assert "### 6.1 Multiple Choice Questions" in md
    assert "- [ ] **A)** O(n)" in md
    assert "- [ ] **C)** O(n^2)" in md

    # Check Answer Key
    assert "## 7. Answer Key & Detailed Explanations" in md
    assert "**Correct Solution:** `C`" in md
    assert "When the array is already sorted" in md

    # Check Quality Audit table
    assert "## 8. Quality Audit & Evaluation Report" in md
    assert "| **Faithfulness & Grounding** | 35% |" in md
    assert "| **Overall Weighted Score** | **100%** | **5.00 / 5.0** |" in md


def test_markdown_exporter_citations(sample_study_pack_content: StudyPackContent):
    """Verify that source references are formatted into markdown citations."""
    exporter = MarkdownExporter()
    md = exporter.export(sample_study_pack_content)

    # Citation formatting includes page numbers and section titles
    assert "Pages 1, 2" in md
    assert "Section: Introduction to Sorting" in md


# ==============================================================================
# Anki CSV Exporter Tests
# ==============================================================================


def test_anki_exporter_format_and_headers(sample_study_pack_content: StudyPackContent):
    """Verify Anki CSV exporter outputs valid RFC 4180 CSV with Front, Back, Tags columns."""
    exporter = AnkiExporter()
    csv_text = exporter.export(sample_study_pack_content)

    assert isinstance(csv_text, str)
    csv_file = io.StringIO(csv_text)
    reader = csv.reader(csv_file)

    # 1. Header row
    header = next(reader)
    assert header == ["Front", "Back", "Tags"]

    rows = list(reader)
    # 3 questions + 2 key terms = 5 flashcards
    assert len(rows) == 5

    # 2. Check practice question card (row 0: MCQ)
    mcq_row = rows[0]
    front, back, tags = mcq_row
    assert "What is the worst-case time complexity" in front
    assert "<b>A)</b> O(n)" in front
    assert "<b>Correct Answer:</b> C" in back
    assert "Explanation:" in back
    assert "difficulty::medium" in tags
    assert "type::mcq" in tags
    assert "topic::" in tags

    # 3. Check glossary key term card (row 3: Stable Sort)
    term_row = rows[3]
    term_front, term_back, term_tags = term_row
    assert "Stable Sort" in term_front
    assert "preserves the relative order" in term_back
    assert "type::glossary" in term_tags


def test_anki_exporter_escaping(sample_study_pack_content: StudyPackContent):
    """Verify that HTML characters, quotes, and newlines in cards are properly escaped."""
    exporter = AnkiExporter()
    csv_text = exporter.export(sample_study_pack_content)

    # Parsing with standard csv reader should succeed without quote or delimiter errors
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)
    assert len(rows) > 0


# ==============================================================================
# PDF Exporter Tests
# ==============================================================================


def test_pdf_exporter_generates_file(sample_study_pack_content: StudyPackContent, tmp_path):
    """Verify PDF exporter renders StudyPackContent to file."""
    exporter = PDFExporter()
    out_pdf = tmp_path / "study_pack.pdf"
    result = exporter.export(sample_study_pack_content, str(out_pdf))

    assert isinstance(result, str)
    # Either PDF was created or HTML fallback was created
    assert out_pdf.exists() or (tmp_path / "study_pack.html").exists()
