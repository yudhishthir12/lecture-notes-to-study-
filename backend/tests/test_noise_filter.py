"""Unit tests for the noise filtering service in LectureForge AI.

Tests verify:
- Running header detection and removal across multiple pages
- Running footer detection and removal across multiple pages
- Standalone page number pattern removal
- Whitespace normalization (tabs, repeated spaces, and excessive newlines)
- Preservation of meaningful concise text, list items, and headings
"""

import pytest

from app.services.models import (
    BlockType,
    ContentBlock,
    ParsedDocument,
    ParsedPage,
)
from app.services.noise_filter import NoiseFilter


@pytest.fixture
def noise_filter() -> NoiseFilter:
    """Fixture returning a standard configured NoiseFilter."""
    return NoiseFilter(repetition_threshold_ratio=0.5, min_pages_for_repetition=2)


def test_noise_filter_running_header_removal(noise_filter: NoiseFilter):
    """Verify repeated top-of-page header is stripped across multiple pages."""
    running_header = "CS 201: Data Structures and Algorithms - Fall 2024"

    pages = [
        ParsedPage(
            page_number=1,
            text=f"{running_header}\n\nBinary Search Trees\nA BST maintains sorted keys.",
            headings=["Binary Search Trees"],
            paragraphs=["A BST maintains sorted keys."],
            blocks=[
                ContentBlock(
                    text=running_header, block_type=BlockType.HEADING.value, page_number=1
                ),
                ContentBlock(
                    text="Binary Search Trees", block_type=BlockType.HEADING.value, page_number=1
                ),
                ContentBlock(
                    text="A BST maintains sorted keys.",
                    block_type=BlockType.PARAGRAPH.value,
                    page_number=1,
                ),
            ],
        ),
        ParsedPage(
            page_number=2,
            text=f"{running_header}\n\nAVL Trees\nAVL trees enforce height balance.",
            headings=["AVL Trees"],
            paragraphs=["AVL trees enforce height balance."],
            blocks=[
                ContentBlock(
                    text=running_header, block_type=BlockType.HEADING.value, page_number=2
                ),
                ContentBlock(text="AVL Trees", block_type=BlockType.HEADING.value, page_number=2),
                ContentBlock(
                    text="AVL trees enforce height balance.",
                    block_type=BlockType.PARAGRAPH.value,
                    page_number=2,
                ),
            ],
        ),
    ]

    doc = ParsedDocument(
        filename="test_lecture.pdf",
        file_type="pdf",
        pages=pages,
        metadata={},
    )

    cleaned_doc = noise_filter.filter(doc)

    assert cleaned_doc.metadata.get("noise_filtered") is True
    # Verify the running header is removed from pages
    for page in cleaned_doc.pages:
        assert running_header not in page.text
        # Legitimate headings must be preserved
        assert any("Trees" in h for h in page.headings)


def test_noise_filter_running_footer_removal(noise_filter: NoiseFilter):
    """Verify repeated bottom-of-page footer is stripped across multiple pages."""
    running_footer = "Confidential - Department of Computer Science"

    pages = [
        ParsedPage(
            page_number=1,
            text=f"Topic One Overview\nContent details.\n\n{running_footer}",
            headings=["Topic One Overview"],
            paragraphs=["Content details."],
            blocks=[
                ContentBlock(
                    text="Topic One Overview", block_type=BlockType.HEADING.value, page_number=1
                ),
                ContentBlock(
                    text="Content details.", block_type=BlockType.PARAGRAPH.value, page_number=1
                ),
                ContentBlock(
                    text=running_footer, block_type=BlockType.PARAGRAPH.value, page_number=1
                ),
            ],
        ),
        ParsedPage(
            page_number=2,
            text=f"Topic Two Overview\nMore details.\n\n{running_footer}",
            headings=["Topic Two Overview"],
            paragraphs=["More details."],
            blocks=[
                ContentBlock(
                    text="Topic Two Overview", block_type=BlockType.HEADING.value, page_number=2
                ),
                ContentBlock(
                    text="More details.", block_type=BlockType.PARAGRAPH.value, page_number=2
                ),
                ContentBlock(
                    text=running_footer, block_type=BlockType.PARAGRAPH.value, page_number=2
                ),
            ],
        ),
    ]

    doc = ParsedDocument(
        filename="lecture_notes.pdf",
        file_type="pdf",
        pages=pages,
        metadata={},
    )

    cleaned_doc = noise_filter.filter(doc)

    for page in cleaned_doc.pages:
        assert running_footer not in page.text
        assert "Overview" in page.text


def test_noise_filter_page_number_removal(noise_filter: NoiseFilter):
    """Verify various standalone page number formats are cleanly removed."""
    page_number_variants = [
        "1",
        "Page 2",
        "3 of 20",
        "- 4 -",
        "[ 5 ]",
        "( 6 )",
        "7 / 20",
        "p. 8",
    ]

    blocks = []
    for idx, num_str in enumerate(page_number_variants, start=1):
        blocks.append(
            ContentBlock(
                text=num_str,
                block_type=BlockType.PARAGRAPH.value,
                page_number=idx,
            )
        )
    # Add one meaningful sentence
    blocks.append(
        ContentBlock(
            text="Essential lecture content that must remain untouched.",
            block_type=BlockType.PARAGRAPH.value,
            page_number=1,
        )
    )

    doc = ParsedDocument(
        filename="notes.pdf",
        file_type="pdf",
        pages=[
            ParsedPage(
                page_number=1,
                text="Some text",
                headings=[],
                paragraphs=[],
                blocks=blocks,
            )
        ],
        metadata={},
    )

    cleaned = noise_filter.filter(doc)
    page_text = cleaned.pages[0].text

    for num_str in page_number_variants:
        assert num_str not in page_text

    assert "Essential lecture content that must remain untouched." in page_text


def test_noise_filter_whitespace_normalization(noise_filter: NoiseFilter):
    """Verify excessive internal whitespace and consecutive newlines are normalized."""
    messy_text = (
        "Line   with    irregular   spacing\t\tand\ttabs.\n\n\n\n\nNext line after big gap."
    )
    block = ContentBlock(text=messy_text, block_type=BlockType.PARAGRAPH.value, page_number=1)

    doc = ParsedDocument(
        filename="messy.txt",
        file_type="txt",
        pages=[
            ParsedPage(
                page_number=1,
                text=messy_text,
                headings=[],
                paragraphs=[messy_text],
                blocks=[block],
            )
        ],
        metadata={},
    )

    cleaned = noise_filter.filter(doc)
    cleaned_text = cleaned.pages[0].text

    # Multiple horizontal spaces collapsed
    assert "Line with irregular spacing and tabs." in cleaned_text
    # 5 consecutive newlines collapsed to 2 (\n\n)
    assert "\n\n\n" not in cleaned_text
    assert "\n\nNext line" in cleaned_text


def test_noise_filter_preserves_meaningful_short_text(noise_filter: NoiseFilter):
    """Verify that short list items, section prefixes, and brief formulas are preserved."""
    short_items = [
        "1. Introduction",
        "2. Architecture",
        "• Item A",
        "F = ma",
        "E = mc^2",
        "Note: Crucial theorem",
    ]

    blocks = [
        ContentBlock(text=item, block_type=BlockType.PARAGRAPH.value, page_number=1)
        for item in short_items
    ]

    doc = ParsedDocument(
        filename="short.pdf",
        file_type="pdf",
        pages=[
            ParsedPage(
                page_number=1,
                text="\n\n".join(short_items),
                headings=[],
                paragraphs=short_items,
                blocks=blocks,
            )
        ],
        metadata={},
    )

    cleaned = noise_filter.filter(doc)
    cleaned_text = cleaned.pages[0].text

    for item in short_items:
        assert item in cleaned_text
