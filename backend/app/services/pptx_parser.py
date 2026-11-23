"""
PowerPoint presentation parser using python-pptx with hierarchy-preserving bullet extraction,
table parsing, and slide title detection.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, Iterator, List, Optional, Tuple

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER
from pptx.shapes.base import BaseShape

from .exceptions import (
    EmptyDocumentError,
    FileCorruptedError,
    ParsingError,
)
from .models import BlockType, ContentBlock, ParsedDocument, ParsedPage

logger = logging.getLogger(__name__)


class PPTXParser:
    """Parser for PowerPoint (.pptx) presentations into structured slides, titles, bullets, and tables."""

    def parse(self, file_path: str) -> ParsedDocument:
        """
        Parse a PPTX file and return a structured ParsedDocument.

        Args:
            file_path: Absolute or relative path to the .pptx presentation file.

        Returns:
            ParsedDocument containing slide-by-slide structured content.

        Raises:
            FileNotFoundError: If the file does not exist.
            EmptyDocumentError: If the file is 0 bytes or contains no slides.
            FileCorruptedError: If the file cannot be opened as a PowerPoint presentation.
            ParsingError: For other unexpected errors.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PPTX file not found at: {file_path}")

        if os.path.getsize(file_path) == 0:
            raise EmptyDocumentError(f"PPTX file '{file_path}' is empty (0 bytes).")

        try:
            prs = Presentation(file_path)
        except Exception as exc:
            raise FileCorruptedError(
                f"Failed to open PPTX '{file_path}': file is corrupted or not a valid PowerPoint presentation."
            ) from exc

        if not prs.slides or len(prs.slides) == 0:
            raise EmptyDocumentError(f"PPTX presentation '{file_path}' contains 0 slides.")

        parsed_pages: List[ParsedPage] = []
        presentation_title: Optional[str] = None

        for slide_index, slide in enumerate(prs.slides):
            slide_number = slide_index + 1
            try:
                page, slide_title = self._parse_slide(slide, slide_number)
                if slide_index == 0 and slide_title and not presentation_title:
                    presentation_title = slide_title
                parsed_pages.append(page)
            except Exception as exc:
                logger.error("Error parsing slide %d of '%s': %s", slide_number, file_path, exc)
                # Fallback empty or minimal slide representation
                parsed_pages.append(
                    ParsedPage(
                        page_number=slide_number,
                        text="",
                        headings=[],
                        paragraphs=[],
                        tables=[],
                        is_scanned=False,
                        blocks=[],
                    )
                )

        metadata: Dict[str, Any] = {
            "title": presentation_title or os.path.splitext(os.path.basename(file_path))[0],
            "slide_count": len(prs.slides),
        }

        # Attempt to extract core document properties if present
        try:
            core_props = prs.core_properties
            if core_props.title:
                metadata["title"] = core_props.title
            if core_props.author:
                metadata["author"] = core_props.author
            if core_props.subject:
                metadata["subject"] = core_props.subject
            if core_props.created:
                metadata["created"] = str(core_props.created)
            if core_props.modified:
                metadata["modified"] = str(core_props.modified)
        except Exception as prop_err:
            logger.debug("Could not read PPTX core properties: %s", prop_err)

        return ParsedDocument(
            filename=os.path.basename(file_path),
            file_type="pptx",
            pages=parsed_pages,
            metadata=metadata,
        )

    def _parse_slide(self, slide: Any, slide_number: int) -> Tuple[ParsedPage, Optional[str]]:
        """Parse a single slide extracting title, hierarchical text, and tables."""
        title_shape = None
        slide_title: Optional[str] = None

        # 1. Detect slide title
        try:
            if slide.shapes.title and slide.shapes.title.has_text_frame:
                title_text = slide.shapes.title.text.strip()
                if title_text:
                    slide_title = title_text
                    title_shape = slide.shapes.title
        except Exception:
            pass

        # If title not found via slide.shapes.title, check placeholders
        if not slide_title:
            for shape in self._iter_shapes(slide.shapes):
                if shape.is_placeholder:
                    try:
                        ph_type = shape.placeholder_format.type
                        if ph_type in (PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE):
                            if shape.has_text_frame and shape.text.strip():
                                slide_title = shape.text.strip()
                                title_shape = shape
                                break
                    except Exception:
                        continue

        # Fallback: check first concise single-line text shape if title still not found
        if not slide_title:
            for shape in self._iter_shapes(slide.shapes):
                if shape.has_text_frame and shape.text.strip():
                    first_text = shape.text.strip()
                    if (
                        len(first_text) < 80
                        and len(first_text.splitlines()) == 1
                        and not first_text.endswith(".")
                    ):
                        slide_title = first_text
                        title_shape = shape
                        break

        headings: List[str] = []
        paragraphs: List[str] = []
        tables: List[List[List[str]]] = []
        blocks: List[ContentBlock] = []
        text_lines: List[str] = []

        if slide_title:
            headings.append(slide_title)
            blocks.append(
                ContentBlock(
                    text=slide_title,
                    block_type=BlockType.HEADING.value,
                    page_number=slide_number,
                )
            )
            text_lines.append(slide_title)

        # 2. Iterate through all shapes on the slide (including group shapes)
        for shape in self._iter_shapes(slide.shapes):
            # Skip the title shape already processed
            if title_shape is not None and shape == title_shape:
                continue

            # Process table shape
            if shape.has_table:
                table_matrix = self._extract_table(shape.table)
                if table_matrix:
                    tables.append(table_matrix)
                    table_md = self._format_table_as_markdown(table_matrix)
                    blocks.append(
                        ContentBlock(
                            text=table_md,
                            block_type=BlockType.TABLE.value,
                            page_number=slide_number,
                        )
                    )
                    text_lines.append(table_md)
                continue

            # Process text shape
            if shape.has_text_frame:
                shape_blocks, shape_paragraphs = self._extract_text_frame(
                    shape.text_frame, slide_number
                )
                blocks.extend(shape_blocks)
                paragraphs.extend(shape_paragraphs)
                for blk in shape_blocks:
                    text_lines.append(blk.text)

        full_text = "\n\n".join(text_lines).strip()

        parsed_page = ParsedPage(
            page_number=slide_number,
            text=full_text,
            headings=headings,
            paragraphs=paragraphs,
            tables=tables,
            is_scanned=False,
            blocks=blocks,
        )

        return parsed_page, slide_title

    def _extract_text_frame(
        self, text_frame: Any, slide_number: int
    ) -> Tuple[List[ContentBlock], List[str]]:
        """
        Extract text from a text frame preserving bullet indentation hierarchy.
        """
        blocks: List[ContentBlock] = []
        paragraphs: List[str] = []

        for p in text_frame.paragraphs:
            text = p.text.strip()
            if not text:
                continue

            level = getattr(p, "level", 0) or 0
            # Clean internal excessive whitespaces
            clean_text = re.sub(r"[ \t]+", " ", text)

            # Check if this paragraph is already formatted with bullet marks
            has_bullet_char = bool(
                re.match(r"^(\u2022|[\*\-\u2013\u2014]|\d+[\.\)])\s+", clean_text)
            )

            if level > 0 or has_bullet_char:
                # Hierarchical bullet point
                bullet_prefix = "  " * level + "• " if not has_bullet_char else "  " * level
                formatted_bullet = f"{bullet_prefix}{clean_text}".strip()
                blocks.append(
                    ContentBlock(
                        text=formatted_bullet,
                        block_type=BlockType.BULLET.value,
                        page_number=slide_number,
                    )
                )
                paragraphs.append(formatted_bullet)
            else:
                # Top level paragraph or heading candidate
                if len(clean_text) < 80 and not clean_text.endswith("."):
                    # Could be sub-heading or paragraph
                    blocks.append(
                        ContentBlock(
                            text=clean_text,
                            block_type=BlockType.PARAGRAPH.value,
                            page_number=slide_number,
                        )
                    )
                    paragraphs.append(clean_text)
                else:
                    blocks.append(
                        ContentBlock(
                            text=clean_text,
                            block_type=BlockType.PARAGRAPH.value,
                            page_number=slide_number,
                        )
                    )
                    paragraphs.append(clean_text)

        return blocks, paragraphs

    def _extract_table(self, table: Any) -> List[List[str]]:
        """Extract table cells into a 2D list of strings."""
        result: List[List[str]] = []
        try:
            for row in table.rows:
                row_data: List[str] = []
                for cell in row.cells:
                    cell_text = cell.text.strip() if cell.text else ""
                    # Normalize whitespace within cells
                    cell_clean = re.sub(r"\s+", " ", cell_text)
                    row_data.append(cell_clean)
                if any(row_data):
                    result.append(row_data)
        except Exception as exc:
            logger.debug("Failed extracting table cells: %s", exc)
        return result

    def _iter_shapes(self, shapes: Any) -> Iterator[BaseShape]:
        """Recursively iterate over shapes, unfolding group shapes."""
        for shape in shapes:
            if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
                try:
                    yield from self._iter_shapes(shape.shapes)
                except Exception:
                    pass
            else:
                yield shape

    @staticmethod
    def _format_table_as_markdown(table: List[List[str]]) -> str:
        """Format 2D table grid into GitHub Flavored Markdown."""
        if not table or not table[0]:
            return ""

        col_count = max(len(row) for row in table)
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
