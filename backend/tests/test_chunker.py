"""Unit tests for semantic chunking service in LectureForge AI.

Tests verify:
- Chunking by headings and sections
- Strict chunk size limits and paragraph/sentence splitting
- Overlap continuity across consecutive chunks
- Accurate provenance source page tracking
- Empty document handling
- Invalid parameter validation
"""

import pytest

from app.schemas.pipeline import DocumentChunk
from app.services.chunker import SemanticChunker
from app.services.models import (
    BlockType,
    ContentBlock,
    ParsedDocument,
    ParsedPage,
)


@pytest.fixture
def chunker() -> SemanticChunker:
    """Fixture returning SemanticChunker with 500-char size and 100-char overlap."""
    return SemanticChunker(chunk_size=500, chunk_overlap=100)


def test_chunking_by_headings(chunker: SemanticChunker):
    """Verify chunker respects heading boundaries and assigns section titles."""
    blocks = [
        ContentBlock(
            text="1. Memory Hierarchy",
            block_type=BlockType.HEADING.value,
            page_number=1,
        ),
        ContentBlock(
            text="Registers and caches provide the fastest data access with smallest capacity.",
            block_type=BlockType.PARAGRAPH.value,
            page_number=1,
        ),
        ContentBlock(
            text="2. Virtual Memory",
            block_type=BlockType.HEADING.value,
            page_number=2,
        ),
        ContentBlock(
            text="Virtual memory provides an illusion of a large contiguous memory space per process.",
            block_type=BlockType.PARAGRAPH.value,
            page_number=2,
        ),
    ]

    doc = ParsedDocument(
        filename="os.pdf",
        file_type="pdf",
        pages=[
            ParsedPage(
                page_number=1,
                text="1. Memory Hierarchy\n\nRegisters and caches provide the fastest data access.",
                headings=["1. Memory Hierarchy"],
                paragraphs=["Registers and caches provide the fastest data access."],
                blocks=blocks[:2],
            ),
            ParsedPage(
                page_number=2,
                text="2. Virtual Memory\n\nVirtual memory provides an illusion.",
                headings=["2. Virtual Memory"],
                paragraphs=["Virtual memory provides an illusion."],
                blocks=blocks[2:],
            ),
        ],
        metadata={},
    )

    chunks = chunker.chunk(doc)

    assert len(chunks) >= 2
    # First chunk belongs to Memory Hierarchy section
    assert chunks[0].section_title == "1. Memory Hierarchy"
    assert "Registers and caches" in chunks[0].text
    assert 1 in chunks[0].source_pages

    # Second chunk belongs to Virtual Memory section
    assert chunks[1].section_title == "2. Virtual Memory"
    assert "Virtual memory provides" in chunks[1].text
    assert 2 in chunks[1].source_pages


def test_chunk_size_limits():
    """Verify that text exceeding chunk_size is divided into smaller chunks."""
    target_size = 300
    chunker = SemanticChunker(chunk_size=target_size, chunk_overlap=50)

    # Long text of ~1000 characters
    long_paragraph = (
        "Distributed systems consist of autonomous computing nodes that communicate over a network. "
        "Each node maintains its own local state and communicates via message passing protocols. "
        "Key challenges in distributed systems include partial failure, clock synchronization, and consensus. "
        "The CAP theorem states that a distributed data store can simultaneously provide at most two of "
        "Consistency, Availability, and Partition tolerance. Paxos and Raft are prominent consensus algorithms "
        "designed to achieve fault-tolerant state machine replication in asynchronous distributed systems."
    )

    doc = ParsedDocument(
        filename="distributed.txt",
        file_type="txt",
        pages=[
            ParsedPage(
                page_number=3,
                text=long_paragraph,
                headings=[],
                paragraphs=[long_paragraph],
                blocks=[
                    ContentBlock(
                        text=long_paragraph,
                        block_type=BlockType.PARAGRAPH.value,
                        page_number=3,
                    )
                ],
            )
        ],
        metadata={},
    )

    chunks = chunker.chunk(doc)

    assert len(chunks) > 1
    for c in chunks:
        # Every chunk should be bounded near or below target_size
        assert len(c.text) <= target_size + 150
        assert 3 in c.source_pages


def test_chunk_overlap():
    """Verify consecutive chunks from a split section share overlapping content."""
    chunker = SemanticChunker(chunk_size=200, chunk_overlap=80)

    sentences = [
        "First sentence discussing introductory concept in algorithm design.",
        "Second sentence discussing asymptotic time bounds and Big-O notation.",
        "Third sentence analyzing worst-case performance on large input sets.",
        "Fourth sentence examining auxiliary space requirements and memory caches.",
    ]
    full_text = " ".join(sentences)

    doc = ParsedDocument(
        filename="overlap.txt",
        file_type="txt",
        pages=[
            ParsedPage(
                page_number=1,
                text=full_text,
                headings=[],
                paragraphs=[full_text],
                blocks=[
                    ContentBlock(
                        text=full_text,
                        block_type=BlockType.PARAGRAPH.value,
                        page_number=1,
                    )
                ],
            )
        ],
        metadata={},
    )

    chunks = chunker.chunk(doc)
    assert len(chunks) >= 2

    # Check for text continuity between chunk 0 and chunk 1
    words_chunk0 = set(chunks[0].text.split())
    words_chunk1 = set(chunks[1].text.split())
    overlap_words = words_chunk0.intersection(words_chunk1)

    # There should be shared words indicating overlap window
    assert len(overlap_words) >= 3


def test_chunk_source_page_tracking():
    """Verify chunks accurately record the source page numbers of their constituent blocks."""
    chunker = SemanticChunker(chunk_size=1000, chunk_overlap=100)

    blocks_page1 = [
        ContentBlock(
            text="Page 1 Content on Cryptography.",
            block_type=BlockType.PARAGRAPH.value,
            page_number=1,
        ),
    ]
    blocks_page2 = [
        ContentBlock(
            text="Page 2 Content on Public-Key Infrastructure.",
            block_type=BlockType.PARAGRAPH.value,
            page_number=2,
        ),
    ]

    doc = ParsedDocument(
        filename="crypto.pdf",
        file_type="pdf",
        pages=[
            ParsedPage(
                page_number=1,
                text="Page 1 Content",
                headings=[],
                paragraphs=[],
                blocks=blocks_page1,
            ),
            ParsedPage(
                page_number=2,
                text="Page 2 Content",
                headings=[],
                paragraphs=[],
                blocks=blocks_page2,
            ),
        ],
        metadata={},
    )

    chunks = chunker.chunk(doc)
    assert len(chunks) == 1
    # Both pages should be represented in the single combined chunk
    assert chunks[0].source_pages == [1, 2]


def test_chunker_empty_input(chunker: SemanticChunker):
    """Verify chunker returns an empty list for empty documents."""
    doc = ParsedDocument(
        filename="empty.txt",
        file_type="txt",
        pages=[],
        metadata={},
    )

    chunks = chunker.chunk(doc)
    assert chunks == []


def test_chunker_parameter_validation():
    """Verify SemanticChunker validates chunk_size and chunk_overlap invariants."""
    # chunk_size must be positive
    with pytest.raises(ValueError, match="chunk_size must be a positive integer"):
        SemanticChunker(chunk_size=0, chunk_overlap=0)

    with pytest.raises(ValueError, match="chunk_size must be a positive integer"):
        SemanticChunker(chunk_size=-100, chunk_overlap=0)

    # chunk_overlap must be non-negative
    with pytest.raises(ValueError, match="chunk_overlap must be non-negative"):
        SemanticChunker(chunk_size=500, chunk_overlap=-10)

    # chunk_overlap must be strictly less than chunk_size
    with pytest.raises(ValueError, match="chunk_overlap must be strictly less than chunk_size"):
        SemanticChunker(chunk_size=500, chunk_overlap=500)

    with pytest.raises(ValueError, match="chunk_overlap must be strictly less than chunk_size"):
        SemanticChunker(chunk_size=500, chunk_overlap=600)
