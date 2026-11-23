"""
PDF document parser using PyMuPDF (fitz) with heading detection, table extraction,
and OCR fallback for scanned pages.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF

from .exceptions import (
    EmptyDocumentError,
    FileCorruptedError,
    FileEncryptedError,
    ParsingError,
)
from .models import BlockType, ContentBlock, ParsedDocument, ParsedPage
from .ocr_service import OCRService

logger = logging.getLogger(__name__)


class PDFParser:
    """Parser for extracting structured text, headings, tables, and blocks from PDF files."""

    def __init__(
        self,
        ocr_service: Optional[OCRService] = None,
        min_scanned_char_threshold: int = 50,
    ) -> None:
        """
        Initialize the PDFParser.

        Args:
            ocr_service: OCR fallback service for scanned pages.
            min_scanned_char_threshold: If page text length is below this and has images,
                                        attempt OCR.
        """
        self.ocr_service = ocr_service or OCRService()
        self.min_scanned_char_threshold = min_scanned_char_threshold

    def parse(self, file_path: str) -> ParsedDocument:
        """
        Parse a PDF file and return a structured ParsedDocument.

        Args:
            file_path: Absolute or relative path to the PDF file.

        Returns:
            ParsedDocument containing page-by-page structured content.

        Raises:
            FileNotFoundError: If the file does not exist.
            EmptyDocumentError: If the file is 0 bytes or has 0 pages.
            FileEncryptedError: If the PDF is password-protected and cannot be opened.
            FileCorruptedError: If PyMuPDF cannot parse the file.
            ParsingError: For other unexpected parsing errors.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found at: {file_path}")

        if os.path.getsize(file_path) == 0:
            raise EmptyDocumentError(f"PDF file '{file_path}' is empty (0 bytes).")

        try:
            doc = fitz.open(file_path)
        except Exception as exc:
            raise FileCorruptedError(
                f"Failed to open PDF '{file_path}': file is corrupted or not a valid PDF."
            ) from exc

        try:
            # Check encryption
            if doc.is_encrypted:
                # Attempt empty password authentication
                if not doc.authenticate(""):
                    raise FileEncryptedError(
                        f"PDF file '{os.path.basename(file_path)}' is password-protected "
                        "and cannot be parsed without credentials."
                    )

            if len(doc) == 0:
                raise EmptyDocumentError(f"PDF file '{file_path}' contains no pages.")

            # Extract document-level metadata
            pdf_meta = doc.metadata or {}
            metadata: Dict[str, Any] = {
                "title": pdf_meta.get("title", ""),
                "author": pdf_meta.get("author", ""),
                "subject": pdf_meta.get("subject", ""),
                "creator": pdf_meta.get("creator", ""),
                "producer": pdf_meta.get("producer", ""),
                "creationDate": pdf_meta.get("creationDate", ""),
                "modDate": pdf_meta.get("modDate", ""),
                "page_count": len(doc),
            }

            parsed_pages: List[ParsedPage] = []

            for page_index, page in enumerate(doc):
                page_number = page_index + 1
                try:
                    parsed_page = self._parse_page(page, page_number)
                    parsed_pages.append(parsed_page)
                except Exception as exc:
                    logger.error("Error parsing page %d of '%s': %s", page_number, file_path, exc)
                    # Create a minimal fallback page so content isn't dropped entirely
                    fallback_text = ""
                    try:
                        fallback_text = page.get_text()
                    except Exception:
                        pass
                    parsed_pages.append(
                        ParsedPage(
                            page_number=page_number,
                            text=fallback_text.strip(),
                            headings=[],
                            paragraphs=[fallback_text.strip()] if fallback_text.strip() else [],
                            tables=[],
                            is_scanned=False,
                            blocks=(
                                [
                                    ContentBlock(
                                        text=fallback_text.strip(),
                                        block_type=BlockType.PARAGRAPH.value,
                                        page_number=page_number,
                                    )
                                ]
                                if fallback_text.strip()
                                else []
                            ),
                        )
                    )

            return ParsedDocument(
                filename=os.path.basename(file_path),
                file_type="pdf",
                pages=parsed_pages,
                metadata=metadata,
            )

        finally:
            doc.close()

    def _parse_page(self, page: fitz.Page, page_number: int) -> ParsedPage:
        """Parse an individual PDF page into structured blocks, text, headings, and tables."""
        # 1. Extract tables first using PyMuPDF's find_tables()
        tables, table_bboxes = self._extract_tables(page)

        # 2. Extract text blocks and spans with font information
        blocks, headings, paragraphs, raw_text_parts = self._extract_text_and_headings(
            page, page_number, table_bboxes
        )

        # 3. Check for scanned page (low text count + images present)
        is_scanned = False
        full_page_text = "\n\n".join(raw_text_parts).strip()

        if len(full_page_text) < self.min_scanned_char_threshold:
            images = page.get_images()
            if images:
                is_scanned = True
                # Attempt OCR fallback if available
                if self.ocr_service.is_available():
                    try:
                        pix = page.get_pixmap(dpi=150)
                        img_bytes = pix.tobytes("png")
                        ocr_text = self.ocr_service.extract_text_from_image(img_bytes)
                        if len(ocr_text.strip()) > len(full_page_text):
                            full_page_text = ocr_text.strip()
                            # Rebuild paragraphs from OCR text
                            ocr_paragraphs = [
                                p.strip() for p in re.split(r"\n\s*\n", full_page_text) if p.strip()
                            ]
                            paragraphs = ocr_paragraphs
                            blocks = [
                                ContentBlock(
                                    text=p,
                                    block_type=BlockType.PARAGRAPH.value,
                                    page_number=page_number,
                                )
                                for p in ocr_paragraphs
                            ]
                    except Exception as ocr_err:
                        logger.warning("OCR fallback failed on page %d: %s", page_number, ocr_err)

        # 4. Integrate tables into blocks if present
        for table in tables:
            table_markdown = self._format_table_as_markdown(table)
            blocks.append(
                ContentBlock(
                    text=table_markdown,
                    block_type=BlockType.TABLE.value,
                    page_number=page_number,
                )
            )
            if table_markdown:
                full_page_text += f"\n\n{table_markdown}"

        return ParsedPage(
            page_number=page_number,
            text=full_page_text.strip(),
            headings=headings,
            paragraphs=paragraphs,
            tables=tables,
            is_scanned=is_scanned,
            blocks=blocks,
        )

    def _extract_tables(self, page: fitz.Page) -> Tuple[List[List[List[str]]], List[fitz.Rect]]:
        """
        Attempt table extraction using PyMuPDF's find_tables().
        Returns extracted tables and their bounding boxes.
        """
        tables: List[List[List[str]]] = []
        table_bboxes: List[fitz.Rect] = []

        try:
            tabs = page.find_tables()
            for tab in tabs:
                extracted = tab.extract()
                if not extracted:
                    continue

                cleaned_table: List[List[str]] = []
                for row in extracted:
                    cleaned_row = [str(cell).strip() if cell is not None else "" for cell in row]
                    # Filter out entirely empty rows
                    if any(cleaned_row):
                        cleaned_table.append(cleaned_row)

                if cleaned_table:
                    tables.append(cleaned_table)
                    table_bboxes.append(fitz.Rect(tab.bbox))
        except Exception as exc:
            logger.debug("PyMuPDF find_tables not supported or failed on page: %s", exc)

        return tables, table_bboxes

    def _extract_text_and_headings(
        self,
        page: fitz.Page,
        page_number: int,
        table_bboxes: List[fitz.Rect],
    ) -> Tuple[List[ContentBlock], List[str], List[str], List[str]]:
        """
        Extract text using layout dictionary to detect headings by font size/weight
        and assemble paragraphs.
        """
        blocks: List[ContentBlock] = []
        headings: List[str] = []
        paragraphs: List[str] = []
        raw_text_parts: List[str] = []

        page_dict = page.get_text("dict")
        raw_blocks = page_dict.get("blocks", [])

        # Step 1: Collect font sizes to determine body font size
        font_sizes: List[float] = []
        for b in raw_blocks:
            if b.get("type") == 0:  # text block
                for line in b.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if text:
                            font_sizes.append(float(span.get("size", 10.0)))

        body_font_size = 11.0
        if font_sizes:
            font_sizes.sort()
            # Median font size represents body text
            body_font_size = font_sizes[len(font_sizes) // 2]

        # Step 2: Iterate blocks and lines
        for b in raw_blocks:
            if b.get("type") != 0:
                continue

            # Check if block falls inside an extracted table bounding box
            b_rect = fitz.Rect(b.get("bbox", (0, 0, 0, 0)))
            if any(b_rect in t_rect or t_rect.contains(b_rect) for t_rect in table_bboxes):
                continue

            block_text_lines: List[str] = []
            block_spans: List[Dict[str, Any]] = []

            for line in b.get("lines", []):
                line_text_parts: List[str] = []
                for span in line.get("spans", []):
                    span_text = span.get("text", "")
                    if span_text:
                        line_text_parts.append(span_text)
                        block_spans.append(span)
                line_str = "".join(line_text_parts).strip()
                if line_str:
                    block_text_lines.append(line_str)

            if not block_text_lines:
                continue

            full_block_text = " ".join(block_text_lines).strip()
            if not full_block_text:
                continue

            # Determine dominant font size and bold flag for block
            avg_size = (
                sum(s.get("size", body_font_size) for s in block_spans) / len(block_spans)
                if block_spans
                else body_font_size
            )
            is_bold = any(
                (s.get("flags", 0) & 2 != 0)
                or ("bold" in s.get("font", "").lower())
                or ("black" in s.get("font", "").lower())
                for s in block_spans
            )

            # Heuristics for heading detection:
            # 1. Significantly larger font size OR bold font with slightly larger/equal size
            # 2. Block is relatively concise (< 140 chars)
            # 3. Does not end with typical sentence-ending punctuation like period (unless numbered header)
            is_heading = self._is_heading_candidate(
                full_block_text, avg_size, body_font_size, is_bold
            )

            is_bullet = self._is_bullet_candidate(full_block_text)

            if is_heading:
                clean_heading = self._clean_heading_text(full_block_text)
                headings.append(clean_heading)
                blocks.append(
                    ContentBlock(
                        text=clean_heading,
                        block_type=BlockType.HEADING.value,
                        page_number=page_number,
                        font_size=avg_size,
                    )
                )
                raw_text_parts.append(clean_heading)
            elif is_bullet:
                blocks.append(
                    ContentBlock(
                        text=full_block_text,
                        block_type=BlockType.BULLET.value,
                        page_number=page_number,
                        font_size=avg_size,
                    )
                )
                paragraphs.append(full_block_text)
                raw_text_parts.append(full_block_text)
            else:
                blocks.append(
                    ContentBlock(
                        text=full_block_text,
                        block_type=BlockType.PARAGRAPH.value,
                        page_number=page_number,
                        font_size=avg_size,
                    )
                )
                paragraphs.append(full_block_text)
                raw_text_parts.append(full_block_text)

        return blocks, headings, paragraphs, raw_text_parts

    @staticmethod
    def _is_heading_candidate(
        text: str, font_size: float, body_font_size: float, is_bold: bool
    ) -> bool:
        """Determine if a text block meets heading criteria based on layout and text characteristics."""
        clean = text.strip()
        if not clean or len(clean) > 160:
            return False

        # Markdown-style heading
        if clean.startswith("#"):
            return True

        # Numbered headings like "1. Introduction" or "2.3 Database Systems"
        if re.match(r"^(\d+\.){1,3}\s+[A-Z]", clean) and len(clean) < 100:
            return True

        # Significantly larger font (e.g. 15% larger than median body size)
        is_large = font_size >= (body_font_size * 1.15)

        # Bold with at least body font size
        is_bold_heading = is_bold and (font_size >= body_font_size * 0.98)

        # Headings typically don't end with a period unless it's an abbreviation or number
        ends_with_period = clean.endswith(".") and not re.search(
            r"\b(Inc|Corp|Ltd|e\.g|i\.e)\.$", clean
        )

        if (is_large or is_bold_heading) and not (ends_with_period and len(clean.split()) > 8):
            return True

        # All uppercase short title line
        if clean.isupper() and 3 <= len(clean.split()) <= 10 and not ends_with_period:
            return True

        return False

    @staticmethod
    def _is_bullet_candidate(text: str) -> bool:
        """Check if block begins with a bullet character or numbered list prefix."""
        bullet_pattern = r"^(\u2022|[\*\-\u2013\u2014]|\d+[\.\)])\s+"
        return bool(re.match(bullet_pattern, text.strip()))

    @staticmethod
    def _clean_heading_text(text: str) -> str:
        """Normalize heading string by stripping leading markdown marks or excessive spaces."""
        text = re.sub(r"^#+\s*", "", text.strip())
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _format_table_as_markdown(table: List[List[str]]) -> str:
        """Format 2D table grid into a clean GitHub Flavored Markdown table string."""
        if not table or not table[0]:
            return ""

        col_count = max(len(row) for row in table)
        # Normalize row lengths
        normalized_rows = [row + [""] * (col_count - len(row)) for row in table]

        header = normalized_rows[0]
        divider = ["---"] * col_count

        lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(divider) + " |",
        ]
        for row in normalized_rows[1:]:
            lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)
