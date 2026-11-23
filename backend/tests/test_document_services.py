"""
Comprehensive unit and integration test suite for LectureForge AI document parsing services.
"""

import io
import os
import tempfile

import fitz  # PyMuPDF
import pytest
from PIL import Image
from pptx import Presentation
from pptx.util import Inches, Pt

from app.schemas.pipeline import DocumentChunk
from app.services.chunker import SemanticChunker
from app.services.document_processor import DocumentProcessor
from app.services.exceptions import (
    DocumentProcessingError,
    EmptyDocumentError,
    FileCorruptedError,
    FileEncryptedError,
    OCRUnavailableError,
    UnsupportedFileTypeError,
)
from app.services.models import (
    BlockType,
    ContentBlock,
    ParsedDocument,
    ParsedPage,
    ProcessingResult,
)
from app.services.noise_filter import NoiseFilter
from app.services.ocr_service import OCRService
from app.services.pdf_parser import PDFParser
from app.services.pptx_parser import PPTXParser
from app.services.txt_parser import TXTParser

# ============================================================================
# TXTParser Tests
# ============================================================================


def test_txt_parser_standard_text(tmp_path):
    parser = TXTParser()
    sample_text = (
        "LECTURE 1: INTRODUCTION TO ALGORITHMS\n\n"
        "An algorithm is a finite sequence of well-defined computer-implementable instructions.\n\n"
        "Key Properties:\n"
        "- Finiteness\n"
        "- Definiteness\n"
        "- Input and Output\n\n"
        "ASYMPTOTIC ANALYSIS\n\n"
        "Asymptotic analysis evaluates performance based on input size n.\n"
    )
    txt_file = tmp_path / "lecture.txt"
    txt_file.write_text(sample_text, encoding="utf-8")

    doc = parser.parse(str(txt_file))
    assert doc.filename == "lecture.txt"
    assert doc.file_type == "txt"
    assert len(doc.pages) == 1
    page = doc.pages[0]
    assert page.page_number == 1
    assert "LECTURE 1: INTRODUCTION TO ALGORITHMS" in page.headings
    assert "ASYMPTOTIC ANALYSIS" in page.headings
    assert len(page.paragraphs) >= 2


def test_txt_parser_multipage_formfeed(tmp_path):
    parser = TXTParser()
    content = (
        "Page 1 Content\nSection 1:\nDetails here.\x0cPage 2 Content\nSection 2:\nMore details."
    )
    txt_file = tmp_path / "multipage.txt"
    txt_file.write_text(content, encoding="utf-8")

    doc = parser.parse(str(txt_file))
    assert len(doc.pages) == 2
    assert doc.pages[0].page_number == 1
    assert doc.pages[1].page_number == 2


def test_txt_parser_encodings(tmp_path):
    parser = TXTParser()
    text_latin1 = "Machine Learning Überblick - Café & Naïve Bayes (ä, ö, ü, é, à)"

    # Latin-1 encoded file
    latin1_file = tmp_path / "latin1.txt"
    with open(latin1_file, "wb") as f:
        f.write(text_latin1.encode("latin-1"))

    doc = parser.parse(str(latin1_file))
    assert "Machine Learning" in doc.full_text
    assert doc.metadata["encoding"] in ("latin-1", "iso-8859-1", "cp1252")

    # CP1252 encoded file (with smart quote / em-dash)
    text_cp1252 = "Data Structures — Trees, Graphs & “Quotes”"
    cp1252_file = tmp_path / "cp1252.txt"
    with open(cp1252_file, "wb") as f:
        f.write(text_cp1252.encode("cp1252"))

    doc2 = parser.parse(str(cp1252_file))
    assert "Data Structures" in doc2.full_text
    assert doc2.metadata["encoding"] in ("cp1252", "latin-1", "iso-8859-1")


def test_txt_parser_empty_and_missing_file(tmp_path):
    parser = TXTParser()
    empty_file = tmp_path / "empty.txt"
    empty_file.write_text("", encoding="utf-8")

    with pytest.raises(EmptyDocumentError):
        parser.parse(str(empty_file))

    with pytest.raises(FileNotFoundError):
        parser.parse(str(tmp_path / "non_existent.txt"))


# ============================================================================
# PDFParser Tests
# ============================================================================


def create_sample_pdf(file_path: str, password: str | None = None) -> None:
    doc = fitz.open()

    # Page 1: Heading, Paragraph, Bullet
    page1 = doc.new_page()
    page1.insert_text((50, 70), "CS101: Operating Systems", fontsize=18)
    page1.insert_text(
        (50, 120),
        "An operating system acts as an intermediary between the user of a computer and computer hardware.",
        fontsize=11,
    )
    page1.insert_text((50, 160), "• Process Management", fontsize=11)
    page1.insert_text((50, 180), "• Memory Management", fontsize=11)

    # Page 2: Table
    page2 = doc.new_page()
    page2.insert_text((50, 70), "Process States Comparison", fontsize=16)

    # Draw a table with rectangles and text
    table_x, table_y = 50, 100
    rows = [
        ["State", "Description", "CPU Active"],
        ["Running", "Instructions are being executed", "Yes"],
        ["Waiting", "Waiting for some event to occur", "No"],
    ]
    y_offset = table_y
    for row in rows:
        x_offset = table_x
        for cell in row:
            rect = fitz.Rect(x_offset, y_offset, x_offset + 120, y_offset + 30)
            page2.draw_rect(rect)
            page2.insert_text((x_offset + 5, y_offset + 20), cell, fontsize=10)
            x_offset += 120
        y_offset += 30

    if password:
        doc.save(
            file_path,
            encryption=fitz.PDF_ENCRYPT_AES_256,
            owner_pw="owner",
            user_pw=password,
        )
    else:
        doc.save(file_path)
    doc.close()


def test_pdf_parser_standard(tmp_path):
    pdf_path = str(tmp_path / "sample.pdf")
    create_sample_pdf(pdf_path)

    parser = PDFParser()
    doc = parser.parse(pdf_path)

    assert doc.filename == "sample.pdf"
    assert doc.file_type == "pdf"
    assert len(doc.pages) == 2
    assert doc.pages[0].page_number == 1
    assert any("CS101" in h for h in doc.pages[0].headings)
    assert doc.pages[1].page_number == 2
    assert "Operating Systems" in doc.full_text


def test_pdf_parser_encrypted_pdf(tmp_path):
    pdf_path = str(tmp_path / "secret.pdf")
    create_sample_pdf(pdf_path, password="secretpassword")

    parser = PDFParser()
    with pytest.raises(FileEncryptedError):
        parser.parse(pdf_path)


def test_pdf_parser_empty_and_corrupt(tmp_path):
    parser = PDFParser()
    empty_pdf = tmp_path / "empty.pdf"
    empty_pdf.write_bytes(b"")

    with pytest.raises(EmptyDocumentError):
        parser.parse(str(empty_pdf))

    corrupt_pdf = tmp_path / "corrupt.pdf"
    corrupt_pdf.write_bytes(b"%PDF-1.4 completely not a valid pdf stream!")
    with pytest.raises(FileCorruptedError):
        parser.parse(str(corrupt_pdf))


# ============================================================================
# PPTXParser Tests
# ============================================================================


def create_sample_pptx(file_path: str) -> None:
    prs = Presentation()

    # Slide 1: Title slide
    title_slide_layout = prs.slide_layouts[0]
    slide1 = prs.slides.add_slide(title_slide_layout)
    slide1.shapes.title.text = "Introduction to Neural Networks"
    slide1.placeholders[1].text = "Deep Learning Course 2026\nInstructor: Prof. Turing"

    # Slide 2: Bullet points with hierarchy
    bullet_slide_layout = prs.slide_layouts[1]
    slide2 = prs.slides.add_slide(bullet_slide_layout)
    slide2.shapes.title.text = "Key Components"
    tf = slide2.placeholders[1].text_frame
    tf.text = "Input Layer"
    p2 = tf.add_paragraph()
    p2.text = "Feature normalization"
    p2.level = 1
    p3 = tf.add_paragraph()
    p3.text = "Hidden Layers"
    p3.level = 0
    p4 = tf.add_paragraph()
    p4.text = "Activation functions (ReLU, GELU)"
    p4.level = 1

    # Slide 3: Slide with a Table
    blank_layout = prs.slide_layouts[6]
    slide3 = prs.slides.add_slide(blank_layout)
    # Add title
    tx_box = slide3.shapes.add_textbox(Inches(1), Inches(0.5), Inches(8), Inches(1))
    tx_box.text_frame.text = "Performance Metrics"
    # Add 2x2 table
    table_shape = slide3.shapes.add_table(2, 2, Inches(1), Inches(2), Inches(6), Inches(2))
    table = table_shape.table
    table.cell(0, 0).text = "Metric"
    table.cell(0, 1).text = "Formula"
    table.cell(1, 0).text = "Accuracy"
    table.cell(1, 1).text = "(TP + TN) / Total"

    prs.save(file_path)


def test_pptx_parser_standard(tmp_path):
    pptx_path = str(tmp_path / "presentation.pptx")
    create_sample_pptx(pptx_path)

    parser = PPTXParser()
    doc = parser.parse(pptx_path)

    assert doc.filename == "presentation.pptx"
    assert doc.file_type == "pptx"
    assert len(doc.pages) == 3

    # Check slide 1
    assert "Introduction to Neural Networks" in doc.pages[0].headings
    assert "Deep Learning Course 2026" in doc.pages[0].text

    # Check slide 2 bullets
    assert "Key Components" in doc.pages[1].headings
    assert any(
        "• Feature normalization" in p or "Feature normalization" in p
        for p in doc.pages[1].paragraphs
    )

    # Check slide 3 table
    assert len(doc.pages[2].tables) == 1
    assert doc.pages[2].tables[0][0] == ["Metric", "Formula"]
    assert doc.pages[2].tables[0][1] == ["Accuracy", "(TP + TN) / Total"]


def test_pptx_parser_empty_and_missing(tmp_path):
    parser = PPTXParser()
    empty_pptx = tmp_path / "empty.pptx"
    empty_pptx.write_bytes(b"")

    with pytest.raises(EmptyDocumentError):
        parser.parse(str(empty_pptx))

    with pytest.raises(FileNotFoundError):
        parser.parse(str(tmp_path / "not_there.pptx"))


# ============================================================================
# OCRService Tests
# ============================================================================


def test_ocr_service_availability_and_fallback():
    ocr = OCRService()
    # is_available should return a boolean without crashing
    avail = ocr.is_available()
    assert isinstance(avail, bool)

    status = ocr.get_status_message()
    assert isinstance(status, str)
    assert len(status) > 0

    if not avail:
        # Should raise OCRUnavailableError if called when not available
        dummy_img = Image.new("RGB", (100, 100), color="white")
        buf = io.BytesIO()
        dummy_img.save(buf, format="PNG")
        with pytest.raises(OCRUnavailableError):
            ocr.extract_text_from_image(buf.getvalue())


# ============================================================================
# NoiseFilter Tests
# ============================================================================


def test_noise_filter_headers_footers_and_page_numbers():
    pages = [
        ParsedPage(
            page_number=1,
            text="UNIVERSITY OF TECHNOLOGY - CS301\n\nLecture 1: Intro\n\nPage 1 of 3\n\nConfidential - Do Not Distribute",
            headings=["Lecture 1: Intro"],
            paragraphs=["Lecture 1: Intro"],
            tables=[],
            is_scanned=False,
            blocks=[
                ContentBlock(
                    text="UNIVERSITY OF TECHNOLOGY - CS301", block_type="paragraph", page_number=1
                ),
                ContentBlock(text="Lecture 1: Intro", block_type="heading", page_number=1),
                ContentBlock(text="Page 1 of 3", block_type="paragraph", page_number=1),
                ContentBlock(
                    text="Confidential - Do Not Distribute", block_type="paragraph", page_number=1
                ),
            ],
        ),
        ParsedPage(
            page_number=2,
            text="UNIVERSITY OF TECHNOLOGY - CS301\n\nSection 2: Architecture\n\nPage 2 of 3\n\nConfidential - Do Not Distribute",
            headings=["Section 2: Architecture"],
            paragraphs=["Section 2: Architecture"],
            tables=[],
            is_scanned=False,
            blocks=[
                ContentBlock(
                    text="UNIVERSITY OF TECHNOLOGY - CS301", block_type="paragraph", page_number=2
                ),
                ContentBlock(text="Section 2: Architecture", block_type="heading", page_number=2),
                ContentBlock(text="Page 2 of 3", block_type="paragraph", page_number=2),
                ContentBlock(
                    text="Confidential - Do Not Distribute", block_type="paragraph", page_number=2
                ),
            ],
        ),
        ParsedPage(
            page_number=3,
            text="UNIVERSITY OF TECHNOLOGY - CS301\n\nSection 3: Summary\n\nPage 3 of 3\n\nConfidential - Do Not Distribute",
            headings=["Section 3: Summary"],
            paragraphs=["Section 3: Summary"],
            tables=[],
            is_scanned=False,
            blocks=[
                ContentBlock(
                    text="UNIVERSITY OF TECHNOLOGY - CS301", block_type="paragraph", page_number=3
                ),
                ContentBlock(text="Section 3: Summary", block_type="heading", page_number=3),
                ContentBlock(text="Page 3 of 3", block_type="paragraph", page_number=3),
                ContentBlock(
                    text="Confidential - Do Not Distribute", block_type="paragraph", page_number=3
                ),
            ],
        ),
    ]

    doc = ParsedDocument(filename="test.pdf", file_type="pdf", pages=pages)
    filter_service = NoiseFilter()
    cleaned_doc = filter_service.filter(doc)

    assert len(cleaned_doc.pages) == 3
    # Check repeated header removed
    for p in cleaned_doc.pages:
        assert "UNIVERSITY OF TECHNOLOGY" not in p.text
        assert "Confidential - Do Not Distribute" not in p.text
        assert "Page 1 of 3" not in p.text
        assert "Page 2 of 3" not in p.text
        assert "Page 3 of 3" not in p.text

    # Content headings preserved
    assert "Lecture 1: Intro" in cleaned_doc.pages[0].text
    assert "Section 2: Architecture" in cleaned_doc.pages[1].text
    assert "Section 3: Summary" in cleaned_doc.pages[2].text


def test_noise_filter_preserves_numbered_lists():
    # Numbered items like "1. Step one" should NOT be removed as page numbers
    page = ParsedPage(
        page_number=1,
        text="1. Step one of the algorithm.\n2. Step two of the algorithm.",
        headings=[],
        paragraphs=["1. Step one of the algorithm.", "2. Step two of the algorithm."],
        tables=[],
        is_scanned=False,
        blocks=[
            ContentBlock(
                text="1. Step one of the algorithm.", block_type="paragraph", page_number=1
            ),
            ContentBlock(
                text="2. Step two of the algorithm.", block_type="paragraph", page_number=1
            ),
        ],
    )
    doc = ParsedDocument(filename="steps.txt", file_type="txt", pages=[page])
    filter_service = NoiseFilter()
    cleaned = filter_service.filter(doc)

    assert "1. Step one of the algorithm." in cleaned.pages[0].text
    assert "2. Step two of the algorithm." in cleaned.pages[0].text


# ============================================================================
# SemanticChunker Tests
# ============================================================================


def test_semantic_chunker_basic():
    doc = ParsedDocument(
        filename="test.txt",
        file_type="txt",
        pages=[
            ParsedPage(
                page_number=1,
                text="Introduction\n\nHere is paragraph one about computer science.",
                headings=["Introduction"],
                paragraphs=["Here is paragraph one about computer science."],
                tables=[],
                is_scanned=False,
                blocks=[
                    ContentBlock(text="Introduction", block_type="heading", page_number=1),
                    ContentBlock(
                        text="Here is paragraph one about computer science.",
                        block_type="paragraph",
                        page_number=1,
                    ),
                ],
            ),
            ParsedPage(
                page_number=2,
                text="Data Structures\n\nHere is paragraph two about linked lists and arrays.",
                headings=["Data Structures"],
                paragraphs=["Here is paragraph two about linked lists and arrays."],
                tables=[],
                is_scanned=False,
                blocks=[
                    ContentBlock(text="Data Structures", block_type="heading", page_number=2),
                    ContentBlock(
                        text="Here is paragraph two about linked lists and arrays.",
                        block_type="paragraph",
                        page_number=2,
                    ),
                ],
            ),
        ],
    )

    chunker = SemanticChunker(chunk_size=500, chunk_overlap=100)
    chunks = chunker.chunk(doc)

    assert len(chunks) == 2
    assert isinstance(chunks[0], DocumentChunk)
    assert chunks[0].section_title == "Introduction"
    assert chunks[0].source_pages == [1]
    assert "computer science" in chunks[0].text

    assert chunks[1].section_title == "Data Structures"
    assert chunks[1].source_pages == [2]
    assert "linked lists" in chunks[1].text


def test_semantic_chunker_large_paragraph_sentence_splitting():
    # Long text exceeding chunk size
    long_para = (
        "Artificial intelligence is transforming every modern industry today. "
        "From autonomous driving to healthcare diagnosis, neural networks are everywhere. "
        "Large language models can process vast amounts of unstructured text in seconds. "
        "These models are trained using billions of tokens on high performance clusters. "
        "Researchers continue to explore alignment, efficiency, and reasoning capabilities."
    )
    doc = ParsedDocument(
        filename="ai.txt",
        file_type="txt",
        pages=[
            ParsedPage(
                page_number=1,
                text=f"AI Overview\n\n{long_para}",
                headings=["AI Overview"],
                paragraphs=[long_para],
                tables=[],
                is_scanned=False,
                blocks=[
                    ContentBlock(text="AI Overview", block_type="heading", page_number=1),
                    ContentBlock(text=long_para, block_type="paragraph", page_number=1),
                ],
            )
        ],
    )

    chunker = SemanticChunker(chunk_size=120, chunk_overlap=30)
    chunks = chunker.chunk(doc)

    assert len(chunks) > 1
    for chunk in chunks:
        assert isinstance(chunk.chunk_id, str)
        assert len(chunk.chunk_id) > 0
        assert chunk.source_pages == [1]
        assert chunk.section_title == "AI Overview"


# ============================================================================
# DocumentProcessor Orchestrator Tests
# ============================================================================


def test_document_processor_end_to_end(tmp_path):
    processor = DocumentProcessor()

    # Test with TXT
    sample_txt = tmp_path / "study_guide.txt"
    sample_txt.write_text(
        "Module 1: Cloud Architecture\n\n"
        "Cloud computing provides on-demand availability of system resources.\n\n"
        "Core Services:\n"
        "- Compute (EC2, Cloud Run)\n"
        "- Storage (S3, Cloud Storage)\n"
        "- Networking (VPC, Cloud CDN)\n\n"
        "Module 2: Serverless Computing\n\n"
        "Serverless offloads server management to the cloud provider.",
        encoding="utf-8",
    )

    result = processor.process(str(sample_txt))
    assert isinstance(result, ProcessingResult)
    assert result.page_count == 1
    assert len(result.chunks) >= 2
    assert "Cloud Architecture" in result.cleaned_text
    assert result.metadata["file_type"] == "txt"
    assert result.metadata["filename"] == "study_guide.txt"

    # Test unsupported type
    invalid_file = tmp_path / "image.png"
    invalid_file.write_bytes(b"\x89PNG\r\n\x1a\n")
    with pytest.raises(UnsupportedFileTypeError):
        processor.process(str(invalid_file))


# ============================================================================
# Additional Comprehensive Tests
# ============================================================================


def test_chunker_invalid_arguments():
    with pytest.raises(ValueError, match="chunk_size must be a positive integer"):
        SemanticChunker(chunk_size=0)
    with pytest.raises(ValueError, match="chunk_overlap must be non-negative"):
        SemanticChunker(chunk_size=100, chunk_overlap=-1)
    with pytest.raises(ValueError, match="chunk_overlap must be strictly less than chunk_size"):
        SemanticChunker(chunk_size=100, chunk_overlap=100)


def test_chunker_document_without_headings():
    doc = ParsedDocument(
        filename="no_heading.txt",
        file_type="txt",
        pages=[
            ParsedPage(
                page_number=1,
                text="Just a plain paragraph without any title or section header. It gives introductory information.",
                headings=[],
                paragraphs=[
                    "Just a plain paragraph without any title or section header. It gives introductory information."
                ],
                tables=[],
                is_scanned=False,
                blocks=[
                    ContentBlock(
                        text="Just a plain paragraph without any title or section header. It gives introductory information.",
                        block_type="paragraph",
                        page_number=1,
                    )
                ],
            )
        ],
    )
    chunker = SemanticChunker(chunk_size=500, chunk_overlap=100)
    chunks = chunker.chunk(doc)

    assert len(chunks) == 1
    assert chunks[0].section_title is None
    assert chunks[0].source_pages == [1]
    assert "introductory information" in chunks[0].text


def test_noise_filter_single_page_preservation():
    # In a 1-page document, top and bottom lines should not be stripped as repeated
    page = ParsedPage(
        page_number=1,
        text="Unique Top Title\n\nMain content here.\n\nUnique Bottom Note",
        headings=["Unique Top Title"],
        paragraphs=["Main content here."],
        tables=[],
        is_scanned=False,
        blocks=[
            ContentBlock(text="Unique Top Title", block_type="heading", page_number=1),
            ContentBlock(text="Main content here.", block_type="paragraph", page_number=1),
            ContentBlock(text="Unique Bottom Note", block_type="paragraph", page_number=1),
        ],
    )
    doc = ParsedDocument(filename="single.pdf", file_type="pdf", pages=[page])
    filter_service = NoiseFilter()
    cleaned = filter_service.filter(doc)

    assert "Unique Top Title" in cleaned.pages[0].text
    assert "Main content here." in cleaned.pages[0].text
    assert "Unique Bottom Note" in cleaned.pages[0].text


def test_pdf_scanned_page_ocr_integration(tmp_path, monkeypatch):
    # Create a PDF page that contains an image and very little text
    pdf_path = str(tmp_path / "scanned_mock.pdf")
    doc = fitz.open()
    page = doc.new_page()

    # Insert a dummy image
    img = Image.new("RGB", (200, 200), color="blue")
    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")
    page.insert_image(fitz.Rect(50, 50, 250, 250), stream=img_buf.getvalue())
    doc.save(pdf_path)
    doc.close()

    # Mock OCRService to simulate OCR extraction
    mock_ocr = OCRService()
    monkeypatch.setattr(mock_ocr, "is_available", lambda: True)
    monkeypatch.setattr(
        mock_ocr,
        "extract_text_from_image",
        lambda img_bytes, lang="eng": "Extracted OCR text from scanned slide",
    )

    parser = PDFParser(ocr_service=mock_ocr, min_scanned_char_threshold=50)
    parsed_doc = parser.parse(pdf_path)

    assert len(parsed_doc.pages) == 1
    assert parsed_doc.pages[0].is_scanned is True
    assert "Extracted OCR text" in parsed_doc.pages[0].text


def test_document_processor_with_pdf_and_pptx(tmp_path):
    processor = DocumentProcessor()

    # Process PDF end to end
    pdf_file = str(tmp_path / "lecture.pdf")
    create_sample_pdf(pdf_file)
    pdf_res = processor.process(pdf_file)

    assert pdf_res.page_count == 2
    assert len(pdf_res.chunks) >= 2
    assert pdf_res.metadata["file_type"] == "pdf"
    assert any("CS101" in c.text or "Operating Systems" in c.text for c in pdf_res.chunks)

    # Process PPTX end to end
    pptx_file = str(tmp_path / "lecture.pptx")
    create_sample_pptx(pptx_file)
    pptx_res = processor.process(pptx_file)

    assert pptx_res.page_count == 3
    assert len(pptx_res.chunks) >= 3
    assert pptx_res.metadata["file_type"] == "pptx"
    assert any("Neural Networks" in c.text for c in pptx_res.chunks)
