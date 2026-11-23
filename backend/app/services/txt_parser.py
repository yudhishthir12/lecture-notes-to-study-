"""
Plain text parser with multi-encoding fallback, paragraph preservation, and heading detection.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from .exceptions import (
    EmptyDocumentError,
    FileCorruptedError,
    ParsingError,
)
from .models import BlockType, ContentBlock, ParsedDocument, ParsedPage

logger = logging.getLogger(__name__)

SUPPORTED_ENCODINGS = ["utf-8", "utf-8-sig", "cp1252", "latin-1", "iso-8859-1"]


class TXTParser:
    """Parser for plain text documents (.txt, .md, etc.) with automatic encoding detection."""

    def parse(self, file_path: str) -> ParsedDocument:
        """
        Parse a text file and return a structured ParsedDocument.

        Args:
            file_path: Absolute or relative path to the text file.

        Returns:
            ParsedDocument containing structured pages, headings, and paragraphs.

        Raises:
            FileNotFoundError: If the file does not exist.
            EmptyDocumentError: If the file is 0 bytes or only whitespace.
            FileCorruptedError: If file cannot be read or decoded.
            ParsingError: For other unexpected errors.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Text file not found at: {file_path}")

        if os.path.getsize(file_path) == 0:
            raise EmptyDocumentError(f"Text file '{file_path}' is empty (0 bytes).")

        raw_bytes = self._read_bytes(file_path)
        decoded_text, used_encoding = self._decode_bytes(raw_bytes, file_path)

        # Normalize line endings to \n
        normalized_text = decoded_text.replace("\r\n", "\n").replace("\r", "\n")

        if not normalized_text.strip():
            raise EmptyDocumentError(f"Text file '{file_path}' contains only whitespace.")

        # Check for form feed character (\x0c) indicating manual page breaks
        raw_pages = normalized_text.split("\x0c")

        parsed_pages: List[ParsedPage] = []
        for page_index, page_content in enumerate(raw_pages):
            page_num = page_index + 1
            parsed_page = self._parse_page_content(page_content, page_num)
            parsed_pages.append(parsed_page)

        metadata: Dict[str, Any] = {
            "encoding": used_encoding,
            "char_count": len(normalized_text),
            "line_count": len(normalized_text.splitlines()),
            "page_count": len(parsed_pages),
        }

        return ParsedDocument(
            filename=os.path.basename(file_path),
            file_type="txt",
            pages=parsed_pages,
            metadata=metadata,
        )

    def _read_bytes(self, file_path: str) -> bytes:
        """Read all bytes from file safely."""
        try:
            with open(file_path, "rb") as f:
                return f.read()
        except Exception as exc:
            raise FileCorruptedError(f"Failed to read file '{file_path}': {exc}") from exc

    def _decode_bytes(self, raw_bytes: bytes, file_path: str) -> Tuple[str, str]:
        """Attempt to decode bytes using ordered candidate encodings."""
        for enc in SUPPORTED_ENCODINGS:
            try:
                text = raw_bytes.decode(enc)
                return text, enc
            except UnicodeDecodeError:
                continue

        # If strict decoding fails across all candidates, fall back with replacement
        try:
            text = raw_bytes.decode("utf-8", errors="replace")
            logger.warning("Decoded '%s' with utf-8 replacement characters.", file_path)
            return text, "utf-8 (replace)"
        except Exception as exc:
            raise FileCorruptedError(f"Unable to decode text file '{file_path}': {exc}") from exc

    def _parse_page_content(self, text: str, page_number: int) -> ParsedPage:
        """Parse text of a single page/section preserving paragraph and heading structure."""
        lines = text.splitlines()
        headings: List[str] = []
        paragraphs: List[str] = []
        blocks: List[ContentBlock] = []

        # First pass: identify underlined headings (Heading\n=== or Heading\n---)
        underlined_heading_indices: Dict[int, str] = {}
        skip_line_indices: set[int] = set()

        for i in range(len(lines) - 1):
            curr_line = lines[i].strip()
            next_line = lines[i + 1].strip()
            if curr_line and len(curr_line) < 120 and len(next_line) >= 3:
                if re.match(r"^=+$", next_line) or re.match(r"^-+$", next_line):
                    underlined_heading_indices[i] = curr_line
                    skip_line_indices.add(i + 1)

        # Second pass: group text into paragraphs and blocks
        raw_paragraphs = re.split(r"\n\s*\n", text)

        for para in raw_paragraphs:
            para_clean = para.strip()
            if not para_clean:
                continue

            para_lines = [l.strip() for l in para_clean.splitlines() if l.strip()]
            if not para_lines:
                continue

            # Check if this entire block or its first line is a heading
            if len(para_lines) == 1 and self._is_heading_line(para_lines[0]):
                clean_h = self._clean_heading(para_lines[0])
                headings.append(clean_h)
                blocks.append(
                    ContentBlock(
                        text=clean_h,
                        block_type=BlockType.HEADING.value,
                        page_number=page_number,
                    )
                )
            elif len(para_lines) == 2 and re.match(r"^[=\-]+$", para_lines[1]):
                # Underlined heading in this paragraph block
                clean_h = self._clean_heading(para_lines[0])
                headings.append(clean_h)
                blocks.append(
                    ContentBlock(
                        text=clean_h,
                        block_type=BlockType.HEADING.value,
                        page_number=page_number,
                    )
                )
            else:
                # Could be a mix of heading, bullets, or standard paragraph
                # Check if first line is heading followed by paragraph text
                first_line = para_lines[0]
                if len(para_lines) > 1 and self._is_heading_line(first_line):
                    clean_h = self._clean_heading(first_line)
                    headings.append(clean_h)
                    blocks.append(
                        ContentBlock(
                            text=clean_h,
                            block_type=BlockType.HEADING.value,
                            page_number=page_number,
                        )
                    )
                    remaining_text = " ".join(para_lines[1:])
                    blocks.append(
                        ContentBlock(
                            text=remaining_text,
                            block_type=BlockType.PARAGRAPH.value,
                            page_number=page_number,
                        )
                    )
                    paragraphs.append(remaining_text)
                else:
                    # Check if items are bullet points
                    all_bullets = all(self._is_bullet(l) for l in para_lines)
                    if all_bullets:
                        for b_line in para_lines:
                            blocks.append(
                                ContentBlock(
                                    text=b_line,
                                    block_type=BlockType.BULLET.value,
                                    page_number=page_number,
                                )
                            )
                            paragraphs.append(b_line)
                    else:
                        # Standard prose paragraph - join soft-wrapped lines
                        joined_para = " ".join(para_lines)
                        # Normalize internal spacing
                        joined_para = re.sub(r"\s+", " ", joined_para)
                        blocks.append(
                            ContentBlock(
                                text=joined_para,
                                block_type=BlockType.PARAGRAPH.value,
                                page_number=page_number,
                            )
                        )
                        paragraphs.append(joined_para)

        full_text = "\n\n".join(b.text for b in blocks if b.text.strip())

        return ParsedPage(
            page_number=page_number,
            text=full_text,
            headings=headings,
            paragraphs=paragraphs,
            tables=[],
            is_scanned=False,
            blocks=blocks,
        )

    def _is_heading_line(self, line: str) -> bool:
        """Heuristic check for headings in plain text."""
        clean = line.strip()
        if not clean or len(clean) > 120:
            return False

        # Markdown headings (# Heading)
        if re.match(r"^#{1,6}\s+\S+", clean):
            return True

        # Numbered headings like "1. Introduction" or "1.1 Overview"
        if re.match(r"^(\d+\.){1,3}\s+[A-Z]", clean) and len(clean) < 80:
            return True

        # Heading ending with a colon: "Key Features:" or "Section A:"
        if clean.endswith(":") and not clean.startswith("http") and len(clean) < 80:
            if not any(
                clean.lower().startswith(skip) for skip in ["note:", "e.g.:", "i.e.:", "warning:"]
            ):
                return True

        # ALL CAPS line with between 2 and 10 words
        words = clean.split()
        if clean.isupper() and 2 <= len(words) <= 10:
            # Must contain alphabetical letters, not just symbols/digits
            if re.search(r"[A-Z]", clean) and not clean.endswith("."):
                return True

        return False

    @staticmethod
    def _is_bullet(line: str) -> bool:
        """Check if line is formatted as a bullet point or numbered item."""
        return bool(re.match(r"^(\u2022|[\*\-\u2013\u2014]|\d+[\.\)])\s+", line.strip()))

    @staticmethod
    def _clean_heading(line: str) -> str:
        """Strip markdown `#` or trailing colons/spaces from heading line."""
        clean = re.sub(r"^#{1,6}\s*", "", line.strip())
        return clean.strip()
