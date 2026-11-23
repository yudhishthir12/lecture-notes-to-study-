"""Unit tests for document parsers (PDF, PPTX, TXT) in LectureForge AI.

Tests verify:
- PDF parsing with minimal generated PDF bytes
- PPTX parsing with minimal generated PPTX slides
- TXT parsing with diverse structures and encoding detection
- Empty file rejection with EmptyDocumentError
- Non-existent file rejection with FileNotFoundError
- Heading detection, bullet hierarchy, and table formatting
"""

import os
from pathlib import Path

import fitz  # PyMuPDF
import pytest
from pptx import Presentation
from pptx.util import Inches, Pt

from app.services.exceptions import (
    EmptyDocumentError,
    FileCorruptedError,
)
from app.services.pdf_parser import PDFParser
from app.services.pptx_parser import PPTXParser
from app.services.txt_parser import TXTParser

# ==============================================================================
# Fixtures for Parsers and Test Files
# ==============================================================================


@pytest.fixture
def pdf_parser() -> PDFParser:
    """Fixture returning initialized PDFParser without OCR requirement."""
    return PDFParser()


@pytest.fixture
def pptx_parser() -> PPTXParser:
    """Fixture returning initialized PPTXParser."""
    return PPTXParser()


@pytest.fixture
def txt_parser() -> TXTParser:
    """Fixture returning initialized TXTParser."""
    return TXTParser()


@pytest.fixture
def minimal_pdf_file(tmp_path: Path) -> Path:
    """Generate a valid minimal PDF file with headings and body text using PyMuPDF."""
    pdf_path = tmp_path / "sample_lecture.pdf"
    doc = fitz.open()

    # Page 1: Title and paragraphs
    page1 = doc.new_page(width=612, height=792)
    page1.insert_text((50, 72), "1. Introduction to Algorithms", fontsize=18)
    page1.insert_text(
        (50, 110),
        "An algorithm is a well-defined sequence of computational steps.",
        fontsize=11,
    )
    page1.insert_text(
        (50, 130),
        "It takes input values and produces a valid output in finite steps.",
        fontsize=11,
    )

    # Page 2: Sub-heading and list
    page2 = doc.new_page(width=612, height=792)
    page2.insert_text((50, 72), "2. Asymptotic Complexity", fontsize=18)
    page2.insert_text(
        (50, 110), "Big-O notation describes the upper bound of runtime.", fontsize=11
    )
    page2.insert_text((50, 130), "• O(1): Constant time", fontsize=11)
    page2.insert_text((50, 150), "• O(n): Linear time", fontsize=11)
    page2.insert_text((50, 170), "• O(n log n): Linearithmic time", fontsize=11)

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def minimal_pptx_file(tmp_path: Path) -> Path:
    """Generate a valid minimal PPTX presentation using python-pptx."""
    pptx_path = tmp_path / "sample_slides.pptx"
    prs = Presentation()

    # Slide 1: Title slide
    title_slide_layout = prs.slide_layouts[0]
    slide1 = prs.slides.add_slide(title_slide_layout)
    slide1.shapes.title.text = "Lecture 1: Database Management Systems"
    slide1.placeholders[1].text = "Relational Model & SQL Fundamentals"

    # Slide 2: Bullet points slide
    bullet_slide_layout = prs.slide_layouts[1]
    slide2 = prs.slides.add_slide(bullet_slide_layout)
    slide2.shapes.title.text = "ACID Properties"
    tf = slide2.shapes.placeholders[1].text_frame
    tf.text = "Atomicity: All operations succeed or fail as a single unit."
    p1 = tf.add_paragraph()
    p1.text = "Consistency: Transitions between valid states only."
    p2 = tf.add_paragraph()
    p2.text = "Isolation: Concurrent transactions execute independently."
    p3 = tf.add_paragraph()
    p3.text = "Durability: Committed data is permanently preserved."

    prs.save(str(pptx_path))
    return pptx_path


# ==============================================================================
# PDF Parser Tests
# ==============================================================================


def test_pdf_parser_success(pdf_parser: PDFParser, minimal_pdf_file: Path):
    """Verify PDF parser extracts structured pages, headings, and text."""
    parsed = pdf_parser.parse(str(minimal_pdf_file))

    assert parsed.filename == "sample_lecture.pdf"
    assert parsed.file_type == "pdf"
    assert len(parsed.pages) == 2
    assert parsed.metadata["page_count"] == 2

    # Check page 1
    page1 = parsed.pages[0]
    assert page1.page_number == 1
    assert "1. Introduction to Algorithms" in page1.headings
    assert "well-defined sequence" in page1.text

    # Check page 2
    page2 = parsed.pages[1]
    assert page2.page_number == 2
    assert "2. Asymptotic Complexity" in page2.headings
    assert "Big-O notation" in page2.text


def test_pdf_parser_file_not_found(pdf_parser: PDFParser):
    """Verify FileNotFoundError is raised when target PDF does not exist."""
    with pytest.raises(FileNotFoundError, match="PDF file not found"):
        pdf_parser.parse("non_existent_file_path.pdf")


def test_pdf_parser_empty_file(pdf_parser: PDFParser, tmp_path: Path):
    """Verify EmptyDocumentError is raised on 0-byte PDF."""
    empty_file = tmp_path / "empty.pdf"
    empty_file.write_bytes(b"")

    with pytest.raises(EmptyDocumentError, match="is empty"):
        pdf_parser.parse(str(empty_file))


def test_pdf_parser_corrupted_file(pdf_parser: PDFParser, tmp_path: Path):
    """Verify FileCorruptedError is raised on invalid/corrupted PDF content."""
    corrupted_file = tmp_path / "corrupted.pdf"
    corrupted_file.write_bytes(b"Not a valid PDF header or content")

    with pytest.raises(FileCorruptedError, match="corrupted or not a valid PDF"):
        pdf_parser.parse(str(corrupted_file))


# ==============================================================================
# PPTX Parser Tests
# ==============================================================================


def test_pptx_parser_success(pptx_parser: PPTXParser, minimal_pptx_file: Path):
    """Verify PPTX parser extracts slide titles, hierarchical bullets, and metadata."""
    parsed = pptx_parser.parse(str(minimal_pptx_file))

    assert parsed.filename == "sample_slides.pptx"
    assert parsed.file_type == "pptx"
    assert len(parsed.pages) == 2
    assert parsed.metadata["slide_count"] == 2

    # Slide 1
    slide1 = parsed.pages[0]
    assert slide1.page_number == 1
    assert "Lecture 1: Database Management Systems" in slide1.headings
    assert "Relational Model & SQL Fundamentals" in slide1.text

    # Slide 2
    slide2 = parsed.pages[1]
    assert slide2.page_number == 2
    assert "ACID Properties" in slide2.headings
    assert "Atomicity" in slide2.text
    assert "Durability" in slide2.text


def test_pptx_parser_file_not_found(pptx_parser: PPTXParser):
    """Verify FileNotFoundError is raised when target PPTX does not exist."""
    with pytest.raises(FileNotFoundError, match="PPTX file not found"):
        pptx_parser.parse("missing_presentation.pptx")


def test_pptx_parser_empty_file(pptx_parser: PPTXParser, tmp_path: Path):
    """Verify EmptyDocumentError is raised on 0-byte PPTX."""
    empty_pptx = tmp_path / "empty.pptx"
    empty_pptx.write_bytes(b"")

    with pytest.raises(EmptyDocumentError, match="is empty"):
        pptx_parser.parse(str(empty_pptx))


def test_pptx_parser_corrupted_file(pptx_parser: PPTXParser, tmp_path: Path):
    """Verify FileCorruptedError is raised when file is not a valid zip/pptx."""
    bad_pptx = tmp_path / "invalid.pptx"
    bad_pptx.write_bytes(b"This is just random binary junk, not a zip or pptx")

    with pytest.raises(FileCorruptedError, match="corrupted or not a valid PowerPoint"):
        pptx_parser.parse(str(bad_pptx))


# ==============================================================================
# TXT Parser Tests & Encoding Detection
# ==============================================================================


def test_txt_parser_standard_text(txt_parser: TXTParser, tmp_path: Path):
    """Verify TXT parser extracts headings, paragraphs, and list items from standard text."""
    content = (
        "CHAPTER 1: COMPUTER NETWORKS\n\n"
        "The Open Systems Interconnection (OSI) model characterizes communication functions.\n\n"
        "Key Layers:\n"
        "- Physical Layer\n"
        "- Data Link Layer\n"
        "- Network Layer\n"
        "- Transport Layer\n\n"
        "TCP VS UDP\n\n"
        "TCP provides reliable, ordered byte-stream delivery with congestion control."
    )
    txt_file = tmp_path / "networks.txt"
    txt_file.write_text(content, encoding="utf-8")

    parsed = txt_parser.parse(str(txt_file))
    assert parsed.filename == "networks.txt"
    assert parsed.file_type == "txt"
    assert len(parsed.pages) == 1
    page = parsed.pages[0]

    assert "CHAPTER 1: COMPUTER NETWORKS" in page.headings
    assert "TCP VS UDP" in page.headings
    assert len(page.paragraphs) >= 2
    assert "Physical Layer" in page.text


def test_txt_parser_encoding_detection(txt_parser: TXTParser, tmp_path: Path):
    """Verify TXT parser detects and handles various text encodings (UTF-8, Latin-1, CP1252)."""
    # 1. Latin-1 text with special accents
    latin1_text = "Thermodynamik: Entropie, Wärme & Carnot-Wirkungsgrad (ä, ö, ü, ß)"
    latin1_file = tmp_path / "latin1.txt"
    latin1_file.write_bytes(latin1_text.encode("latin-1"))

    doc_latin1 = txt_parser.parse(str(latin1_file))
    assert "Thermodynamik" in doc_latin1.full_text
    assert doc_latin1.metadata["encoding"] in ("latin-1", "iso-8859-1", "cp1252")

    # 2. CP1252 text with typographer quotes and em-dash
    cp1252_text = "Operating Systems — Threads, Mutexes & “Semaphores”"
    cp1252_file = tmp_path / "cp1252.txt"
    cp1252_file.write_bytes(cp1252_text.encode("cp1252"))

    doc_cp1252 = txt_parser.parse(str(cp1252_file))
    assert "Operating Systems" in doc_cp1252.full_text
    assert "Semaphores" in doc_cp1252.full_text


def test_txt_parser_empty_file(txt_parser: TXTParser, tmp_path: Path):
    """Verify EmptyDocumentError is raised on 0-byte text file."""
    empty_txt = tmp_path / "empty.txt"
    empty_txt.write_bytes(b"")

    with pytest.raises(EmptyDocumentError, match="is empty"):
        txt_parser.parse(str(empty_txt))


def test_txt_parser_whitespace_only_file(txt_parser: TXTParser, tmp_path: Path):
    """Verify EmptyDocumentError is raised on text file containing only whitespace."""
    blank_txt = tmp_path / "blank.txt"
    blank_txt.write_text("   \n\t   \n\n   \t  ", encoding="utf-8")

    with pytest.raises(EmptyDocumentError, match="contains only whitespace"):
        txt_parser.parse(str(blank_txt))


def test_txt_parser_file_not_found(txt_parser: TXTParser):
    """Verify FileNotFoundError is raised when text file does not exist."""
    with pytest.raises(FileNotFoundError, match="Text file not found"):
        txt_parser.parse("nonexistent_lecture.txt")
