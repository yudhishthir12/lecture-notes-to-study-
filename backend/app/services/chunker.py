"""
Semantic chunking service for structured documents.
Splits by headings, paragraphs, and sentences with overlap and provenance tracking.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import List, Optional, Tuple

from ..schemas.pipeline import DocumentChunk
from .models import BlockType, ContentBlock, ParsedDocument

logger = logging.getLogger(__name__)

# Sentence boundary regular expression
SENTENCE_SPLIT_REGEX = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'‘“])")


class _TextElement:
    """Internal helper representing a piece of text and its source page."""

    __slots__ = ("text", "page_number", "is_heading")

    def __init__(self, text: str, page_number: int, is_heading: bool = False) -> None:
        self.text = text
        self.page_number = page_number
        self.is_heading = is_heading


class _Section:
    """Internal helper representing a heading and its associated content elements."""

    def __init__(self, title: Optional[str] = None) -> None:
        self.title: Optional[str] = title
        self.elements: List[_TextElement] = []

    def add_element(self, text: str, page_number: int, is_heading: bool = False) -> None:
        clean_text = text.strip()
        if clean_text:
            self.elements.append(_TextElement(clean_text, page_number, is_heading))


class SemanticChunker:
    """
    Splits ParsedDocuments into semantically coherent DocumentChunks using a
    hierarchical strategy (Headings -> Paragraphs -> Sentences -> Words)
    while maintaining overlap and tracking source pages.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> None:
        """
        Initialize the SemanticChunker.

        Args:
            chunk_size: Target maximum character length for each chunk (default 1000).
            chunk_overlap: Target character overlap between consecutive chunks (default 200).
        """
        if chunk_size <= 0:
            raise ValueError("chunk_size must be a positive integer.")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative.")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be strictly less than chunk_size.")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, parsed_doc: ParsedDocument) -> List[DocumentChunk]:
        """
        Convert a ParsedDocument into a list of DocumentChunks.

        Args:
            parsed_doc: Filtered and structured document.

        Returns:
            List of DocumentChunk instances with unique IDs, text, source pages, and section title.
        """
        if not parsed_doc.pages:
            return []

        # Step 1: Divide document blocks into sections based on headings
        sections = self._build_sections(parsed_doc)

        chunks: List[DocumentChunk] = []

        # Step 2: Process each section independently to keep sections semantically distinct
        for section in sections:
            section_chunks = self._chunk_section(section)
            chunks.extend(section_chunks)

        # Fallback if document had text but no chunks produced
        if not chunks and parsed_doc.full_text.strip():
            chunks.append(
                DocumentChunk(
                    chunk_id=str(uuid.uuid4()),
                    text=parsed_doc.full_text.strip(),
                    source_pages=[p.page_number for p in parsed_doc.pages if p.text.strip()],
                    section_title=None,
                )
            )

        return chunks

    def _build_sections(self, parsed_doc: ParsedDocument) -> List[_Section]:
        """Group document content blocks into logical sections rooted at headings."""
        sections: List[_Section] = []
        current_section = _Section(title=None)

        for page in parsed_doc.pages:
            for block in page.blocks:
                text = block.text.strip()
                if not text:
                    continue

                if block.block_type == BlockType.HEADING.value:
                    # If current section already has elements or a title, start a new section
                    if current_section.elements or current_section.title is not None:
                        sections.append(current_section)
                    current_section = _Section(title=text)
                    current_section.add_element(text, page.page_number, is_heading=True)
                else:
                    current_section.add_element(text, page.page_number, is_heading=False)

        if current_section.elements or current_section.title:
            sections.append(current_section)

        # Filter out empty sections
        return [s for s in sections if s.elements]

    def _chunk_section(self, section: _Section) -> List[DocumentChunk]:
        """Chunk a single section respecting chunk_size, chunk_overlap, and sub-splitting."""
        # Calculate total text length
        total_len = sum(len(e.text) for e in section.elements)

        # Fast path: section fits entirely within one chunk
        if total_len <= self.chunk_size:
            chunk_text = "\n\n".join(e.text for e in section.elements)
            source_pages = sorted(list({e.page_number for e in section.elements}))
            return [
                DocumentChunk(
                    chunk_id=str(uuid.uuid4()),
                    text=chunk_text,
                    source_pages=source_pages,
                    section_title=section.title,
                )
            ]

        # Step 2: Deconstruct elements into atomic fragments (paragraphs or sentences)
        atomic_units: List[_TextElement] = []
        for elem in section.elements:
            if len(elem.text) <= self.chunk_size:
                atomic_units.append(elem)
            else:
                # Split large element by sentences
                sentence_units = self._split_into_sentences(elem.text, elem.page_number)
                atomic_units.extend(sentence_units)

        # Step 3: Greedily aggregate atomic units with overlap window
        chunks: List[DocumentChunk] = []
        i = 0
        n = len(atomic_units)

        while i < n:
            current_units: List[_TextElement] = []
            current_len = 0
            start_idx = i

            while i < n:
                unit = atomic_units[i]
                unit_len = len(unit.text) + (
                    2 if current_units else 0
                )  # account for \n\n separator

                if current_units and (current_len + unit_len > self.chunk_size):
                    break

                current_units.append(unit)
                current_len += unit_len
                i += 1

            if not current_units:
                # Single unit exceeds chunk_size, force add it
                unit = atomic_units[i]
                current_units.append(unit)
                i += 1

            chunk_text = "\n\n".join(u.text for u in current_units)
            source_pages = sorted(list({u.page_number for u in current_units}))

            chunks.append(
                DocumentChunk(
                    chunk_id=str(uuid.uuid4()),
                    text=chunk_text,
                    source_pages=source_pages,
                    section_title=section.title,
                )
            )

            # Determine next start position based on chunk_overlap
            if i < n:
                # Calculate overlap backwards from current position
                overlap_len = 0
                overlap_count = 0
                for back_idx in range(len(current_units) - 1, -1, -1):
                    unit_len = len(current_units[back_idx].text)
                    if overlap_len + unit_len <= self.chunk_overlap or overlap_count == 0:
                        overlap_len += unit_len
                        overlap_count += 1
                    else:
                        break

                # Advance pointer so we don't get stuck in an infinite loop
                next_start = start_idx + len(current_units) - overlap_count
                if next_start <= start_idx:
                    next_start = start_idx + 1
                i = next_start

        return chunks

    def _split_into_sentences(self, text: str, page_number: int) -> List[_TextElement]:
        """Split a long paragraph into sentences or words if an individual sentence is too long."""
        raw_sentences = SENTENCE_SPLIT_REGEX.split(text)
        units: List[_TextElement] = []

        for sent in raw_sentences:
            sent_clean = sent.strip()
            if not sent_clean:
                continue

            if len(sent_clean) <= self.chunk_size:
                units.append(_TextElement(sent_clean, page_number))
            else:
                # Sentence itself exceeds chunk_size, split by words
                word_units = self._split_by_words(sent_clean, page_number)
                units.extend(word_units)

        return units

    def _split_by_words(self, text: str, page_number: int) -> List[_TextElement]:
        """Split text by space-delimited words up to chunk_size."""
        words = text.split()
        units: List[_TextElement] = []
        current_words: List[str] = []
        current_len = 0

        for word in words:
            word_len = len(word) + (1 if current_words else 0)
            if current_words and (current_len + word_len > self.chunk_size):
                units.append(_TextElement(" ".join(current_words), page_number))
                current_words = [word]
                current_len = len(word)
            else:
                current_words.append(word)
                current_len += word_len

        if current_words:
            units.append(_TextElement(" ".join(current_words), page_number))

        return units
