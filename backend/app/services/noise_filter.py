"""
Noise filtering service to remove running headers, footers, standalone page numbers,
and normalize whitespace while conservatively preserving headings and list items.
"""

from __future__ import annotations

import copy
import logging
import re
from collections import Counter
from typing import List, Optional, Set

from .models import BlockType, ContentBlock, ParsedDocument, ParsedPage

logger = logging.getLogger(__name__)

# Standalone page number regex patterns
PAGE_NUMBER_PATTERNS = [
    re.compile(r"^\s*(?:page\s*)?\d+\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:page\s*)?\d+\s*(?:of|/|-)\s*\d+\s*$", re.IGNORECASE),
    re.compile(r"^\s*[-–—]\s*\d+\s*[-–—]\s*$"),
    re.compile(r"^\s*\[\s*\d+\s*\]\s*$"),
    re.compile(r"^\s*\(\s*\d+\s*\)\s*$"),
    re.compile(r"^\s*\d+\s*/\s*\d+\s*$"),
    re.compile(r"^\s*p\.\s*\d+\s*$", re.IGNORECASE),
]


class NoiseFilter:
    """Filter to clean noise (repeated headers, footers, page numbers) from parsed documents."""

    def __init__(
        self,
        repetition_threshold_ratio: float = 0.5,
        min_pages_for_repetition: int = 2,
    ) -> None:
        """
        Initialize the NoiseFilter.

        Args:
            repetition_threshold_ratio: Minimum fraction of pages where a top/bottom line
                                        must appear to be considered a repeated header/footer.
            min_pages_for_repetition: Minimum total pages in document to enable repetition detection.
        """
        self.repetition_threshold_ratio = repetition_threshold_ratio
        self.min_pages_for_repetition = min_pages_for_repetition

    def filter(self, parsed_doc: ParsedDocument) -> ParsedDocument:
        """
        Apply conservative noise filtering to the ParsedDocument.

        Args:
            parsed_doc: Input ParsedDocument with raw parsed pages and blocks.

        Returns:
            A cleaned copy of ParsedDocument with noise removed and whitespace normalized.
        """
        if not parsed_doc.pages:
            return parsed_doc.model_copy(deep=True)

        total_pages = len(parsed_doc.pages)

        # Step 1: Detect recurring running headers and footers across pages
        repeated_headers, repeated_footers = self._detect_repeated_headers_and_footers(
            parsed_doc.pages, total_pages
        )

        filtered_pages: List[ParsedPage] = []

        for page in parsed_doc.pages:
            cleaned_page = self._filter_page(page, repeated_headers, repeated_footers)
            filtered_pages.append(cleaned_page)

        # Create cleaned document copy
        cleaned_doc = parsed_doc.model_copy(
            update={
                "pages": filtered_pages,
                "metadata": {
                    **parsed_doc.metadata,
                    "noise_filtered": True,
                    "removed_headers": list(repeated_headers),
                    "removed_footers": list(repeated_footers),
                },
            },
            deep=True,
        )

        return cleaned_doc

    def _detect_repeated_headers_and_footers(
        self, pages: List[ParsedPage], total_pages: int
    ) -> tuple[Set[str], Set[str]]:
        """Identify strings that appear identically at the top or bottom across multiple pages."""
        repeated_headers: Set[str] = set()
        repeated_footers: Set[str] = set()

        if total_pages < self.min_pages_for_repetition:
            return repeated_headers, repeated_footers

        top_lines: List[str] = []
        bottom_lines: List[str] = []

        for page in pages:
            lines = [l.strip() for l in page.text.splitlines() if l.strip()]
            if lines:
                top_candidate = self._normalize_for_matching(lines[0])
                # Ensure top line is relatively short (< 120 chars) and not a full paragraph
                if top_candidate and len(top_candidate) < 120:
                    top_lines.append(top_candidate)

                bottom_candidate = self._normalize_for_matching(lines[-1])
                if bottom_candidate and len(bottom_candidate) < 120:
                    bottom_lines.append(bottom_candidate)

        min_occurrences = max(2, int(total_pages * self.repetition_threshold_ratio))

        top_counts = Counter(top_lines)
        for cand, count in top_counts.items():
            if count >= min_occurrences:
                # Do not treat as header if it's purely a single letter or number
                if len(cand) > 3:
                    repeated_headers.add(cand)

        bottom_counts = Counter(bottom_lines)
        for cand, count in bottom_counts.items():
            if count >= min_occurrences:
                if len(cand) > 3:
                    repeated_footers.add(cand)

        return repeated_headers, repeated_footers

    def _filter_page(
        self,
        page: ParsedPage,
        repeated_headers: Set[str],
        repeated_footers: Set[str],
    ) -> ParsedPage:
        """Filter a single page's blocks, text, headings, and paragraphs."""
        cleaned_blocks: List[ContentBlock] = []
        cleaned_headings: List[str] = []
        cleaned_paragraphs: List[str] = []

        total_blocks = len(page.blocks)

        for idx, block in enumerate(page.blocks):
            block_text = block.text.strip()
            if not block_text:
                continue

            normalized_match = self._normalize_for_matching(block_text)

            # Check for standalone page numbers
            if self._is_standalone_page_number(block_text):
                continue

            # Check for repeated header (typically near the top of the page)
            if idx <= 2 and normalized_match in repeated_headers:
                continue

            # Check for repeated footer (typically near the bottom of the page)
            if idx >= (total_blocks - 3) and normalized_match in repeated_footers:
                continue

            # Whitespace normalization
            cleaned_text = self._normalize_whitespace(block_text)
            if not cleaned_text:
                continue

            # Build cleaned block
            cleaned_block = block.model_copy(update={"text": cleaned_text})
            cleaned_blocks.append(cleaned_block)

            # Route to headings or paragraphs
            if block.block_type == BlockType.HEADING.value:
                # Keep heading unless it was part of repeated noise
                if normalized_match not in repeated_headers:
                    cleaned_headings.append(cleaned_text)
            elif block.block_type in (BlockType.PARAGRAPH.value, BlockType.BULLET.value):
                cleaned_paragraphs.append(cleaned_text)

        # Rebuild full page text from cleaned blocks
        new_page_text = "\n\n".join(b.text for b in cleaned_blocks if b.text.strip())

        return ParsedPage(
            page_number=page.page_number,
            text=new_page_text,
            headings=cleaned_headings,
            paragraphs=cleaned_paragraphs,
            tables=page.tables,
            is_scanned=page.is_scanned,
            blocks=cleaned_blocks,
        )

    def _is_standalone_page_number(self, text: str) -> bool:
        """Check if a line/block represents solely a page number."""
        clean = text.strip()
        if not clean or len(clean) > 30:
            return False

        # If it's a list item (e.g., "1. Introduction" or "1. Apples"), DO NOT remove
        if re.match(r"^\d+[\.\)]\s+[A-Za-z]", clean):
            return False

        for pattern in PAGE_NUMBER_PATTERNS:
            if pattern.match(clean):
                return True

        return False

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        """Collapse multiple horizontal spaces and normalize newlines."""
        if not text:
            return ""

        # Normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        lines = text.split("\n")
        cleaned_lines = []
        for line in lines:
            # Collapse multiple spaces and tabs within the line
            cleaned_line = re.sub(r"[ \t]+", " ", line).strip()
            cleaned_lines.append(cleaned_line)

        # Join and collapse 3 or more consecutive newlines into 2
        joined = "\n".join(cleaned_lines)
        return re.sub(r"\n{3,}", "\n\n", joined).strip()

    @staticmethod
    def _normalize_for_matching(text: str) -> str:
        """Normalize text for header/footer comparison (case-insensitive, whitespace collapsed)."""
        clean = re.sub(r"\s+", " ", text.strip().lower())
        # Remove trailing/leading page numbers if embedded
        clean = re.sub(r"\bpage\s*\d+\b", "", clean).strip()
        return clean
