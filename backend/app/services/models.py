"""
Data models for document parsing, noise filtering, and semantic chunking.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..schemas.pipeline import DocumentChunk
from .exceptions import (
    DocumentProcessingError,
    EmptyDocumentError,
    FileCorruptedError,
    FileEncryptedError,
    OCRUnavailableError,
    ParsingError,
    UnsupportedFileTypeError,
)


class BlockType(str, Enum):
    """Enumeration of content block types within a page."""

    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    BULLET = "bullet"


class ContentBlock(BaseModel):
    """Fine-grained atomic content block within a page or slide."""

    text: str = Field(..., description="Text content of this block")
    block_type: str = Field(
        ...,
        description="Type of block: heading, paragraph, table, or bullet",
    )
    page_number: int = Field(
        ...,
        description="1-indexed page or slide number",
    )
    font_size: Optional[float] = Field(
        default=None,
        description="Font size in points, if available from layout parsing",
    )


class ParsedPage(BaseModel):
    """Structured representation of a single document page or slide."""

    page_number: int = Field(
        ...,
        description="1-indexed page or slide number",
    )
    text: str = Field(
        default="",
        description="Full text extracted from this page",
    )
    headings: List[str] = Field(
        default_factory=list,
        description="List of detected headings or section titles on this page",
    )
    paragraphs: List[str] = Field(
        default_factory=list,
        description="List of detected paragraphs on this page",
    )
    tables: List[List[List[str]]] = Field(
        default_factory=list,
        description="Extracted tables represented as 2D cell grids [row][col]",
    )
    is_scanned: bool = Field(
        default=False,
        description="True if this page was detected as scanned / required OCR",
    )
    blocks: List[ContentBlock] = Field(
        default_factory=list,
        description="Ordered sequence of content blocks on this page",
    )


class ParsedDocument(BaseModel):
    """Structured representation of an entire parsed document."""

    filename: str = Field(..., description="Original name of the source file")
    file_type: str = Field(..., description="File extension/type (pdf, pptx, txt)")
    pages: List[ParsedPage] = Field(
        default_factory=list,
        description="List of parsed pages in sequential order",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary document metadata (e.g. author, title, page_count)",
    )

    @property
    def page_count(self) -> int:
        """Total number of pages or slides."""
        return len(self.pages)

    @property
    def full_text(self) -> str:
        """Aggregated text across all pages joined with double newlines."""
        return "\n\n".join(p.text for p in self.pages if p.text.strip())

    @property
    def all_headings(self) -> List[str]:
        """Flattened list of all detected headings across pages."""
        result: List[str] = []
        for p in self.pages:
            result.extend(p.headings)
        return result


class ProcessingResult(BaseModel):
    """End-to-end result of parsing, filtering, and chunking a document."""

    raw_text: str = Field(..., description="Raw text extracted before noise filtering")
    cleaned_text: str = Field(..., description="Cleaned text after noise filtering")
    chunks: List[DocumentChunk] = Field(
        default_factory=list,
        description="List of semantic chunks ready for embedding/generation",
    )
    page_count: int = Field(..., description="Total pages/slides processed")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Detailed metadata, statistics, and processing diagnostics",
    )


__all__ = [
    "BlockType",
    "ContentBlock",
    "ParsedPage",
    "ParsedDocument",
    "DocumentChunk",
    "ProcessingResult",
    "DocumentProcessingError",
    "FileCorruptedError",
    "FileEncryptedError",
    "UnsupportedFileTypeError",
    "EmptyDocumentError",
    "OCRUnavailableError",
    "ParsingError",
]
