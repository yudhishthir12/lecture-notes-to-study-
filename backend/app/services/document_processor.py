"""
DocumentProcessor orchestrator: coordinates parsing, noise filtering,
and semantic chunking across supported document formats (PDF, PPTX, TXT).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from ..schemas.pipeline import DocumentChunk
from .chunker import SemanticChunker
from .exceptions import (
    DocumentProcessingError,
    EmptyDocumentError,
    FileCorruptedError,
    FileEncryptedError,
    OCRUnavailableError,
    ParsingError,
    UnsupportedFileTypeError,
)
from .models import ParsedDocument, ProcessingResult
from .noise_filter import NoiseFilter
from .ocr_service import OCRService
from .pdf_parser import PDFParser
from .pptx_parser import PPTXParser
from .txt_parser import TXTParser

logger = logging.getLogger(__name__)

SUPPORTED_TYPES = {"pdf", "pptx", "txt", "md"}


class DocumentProcessor:
    """
    Main orchestrator for LectureForge AI document ingestion.
    Parses documents, filters noise, and chunks content into semantic units.
    """

    def __init__(
        self,
        pdf_parser: Optional[PDFParser] = None,
        pptx_parser: Optional[PPTXParser] = None,
        txt_parser: Optional[TXTParser] = None,
        noise_filter: Optional[NoiseFilter] = None,
        chunker: Optional[SemanticChunker] = None,
        ocr_service: Optional[OCRService] = None,
    ) -> None:
        """
        Initialize the DocumentProcessor with configurable sub-services.
        """
        self.ocr_service = ocr_service or OCRService()
        self.pdf_parser = pdf_parser or PDFParser(ocr_service=self.ocr_service)
        self.pptx_parser = pptx_parser or PPTXParser()
        self.txt_parser = txt_parser or TXTParser()
        self.noise_filter = noise_filter or NoiseFilter()
        self.chunker = chunker or SemanticChunker()

    def process(self, file_path: str, file_type: Optional[str] = None) -> ProcessingResult:
        """
        Process a document end-to-end: parse, clean noise, and chunk.

        Args:
            file_path: Path to the target document.
            file_type: Optional explicit file type override ('pdf', 'pptx', 'txt').
                       If omitted, detected from file extension.

        Returns:
            ProcessingResult containing raw_text, cleaned_text, chunks, page_count, and metadata.

        Raises:
            FileNotFoundError: If the input file does not exist.
            UnsupportedFileTypeError: If the file type is not supported.
            EmptyDocumentError: If the file has no content or pages.
            FileEncryptedError: If a PDF is password protected.
            FileCorruptedError: If the file is damaged and cannot be parsed.
            DocumentProcessingError: Base error for unexpected processing failures.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found at: {file_path}")

        # Resolve and normalize file type
        resolved_type = self._resolve_file_type(file_path, file_type)

        logger.info("Starting processing of '%s' (type: %s)", file_path, resolved_type)

        # 1. Parse document using appropriate parser
        raw_doc = self._parse_document(file_path, resolved_type)
        raw_text = raw_doc.full_text

        # 2. Filter noise (running headers, footers, page numbers, whitespace)
        cleaned_doc = self.noise_filter.filter(raw_doc)
        cleaned_text = cleaned_doc.full_text

        # 3. Generate semantic chunks
        chunks = self.chunker.chunk(cleaned_doc)

        # 4. Compile statistics and metadata
        file_size = 0
        try:
            file_size = os.path.getsize(file_path)
        except OSError:
            pass

        has_scanned = any(p.is_scanned for p in cleaned_doc.pages)
        tables_count = sum(len(p.tables) for p in cleaned_doc.pages)

        result_metadata: Dict[str, Any] = {
            "filename": os.path.basename(file_path),
            "file_type": resolved_type,
            "file_size_bytes": file_size,
            "raw_char_count": len(raw_text),
            "cleaned_char_count": len(cleaned_text),
            "page_count": len(cleaned_doc.pages),
            "chunk_count": len(chunks),
            "is_scanned": has_scanned,
            "tables_count": tables_count,
            "headings_count": len(cleaned_doc.all_headings),
            "parser_metadata": cleaned_doc.metadata,
        }

        logger.info(
            "Completed processing '%s': %d pages, %d chunks, %d tables",
            file_path,
            len(cleaned_doc.pages),
            len(chunks),
            tables_count,
        )

        return ProcessingResult(
            raw_text=raw_text,
            cleaned_text=cleaned_text,
            chunks=chunks,
            page_count=len(cleaned_doc.pages),
            metadata=result_metadata,
        )

    def _resolve_file_type(self, file_path: str, file_type: Optional[str]) -> str:
        """Resolve and validate the document file type."""
        ext = file_type
        if not ext:
            _, ext_part = os.path.splitext(file_path)
            ext = ext_part.lstrip(".").lower()

        ext = ext.lower().strip()
        if ext == "md":
            ext = "txt"

        if ext not in SUPPORTED_TYPES:
            raise UnsupportedFileTypeError(
                f"Unsupported file type '{ext}'. Supported formats: {sorted(list(SUPPORTED_TYPES))}"
            )

        return ext

    def _parse_document(self, file_path: str, file_type: str) -> ParsedDocument:
        """Dispatch to the relevant parser based on file type."""
        try:
            if file_type == "pdf":
                return self.pdf_parser.parse(file_path)
            elif file_type == "pptx":
                return self.pptx_parser.parse(file_path)
            elif file_type in ("txt", "md"):
                return self.txt_parser.parse(file_path)
            else:
                raise UnsupportedFileTypeError(f"Parser not registered for '{file_type}'")
        except (
            FileNotFoundError,
            UnsupportedFileTypeError,
            EmptyDocumentError,
            FileEncryptedError,
            FileCorruptedError,
            ParsingError,
        ):
            # Re-raise known domain exceptions directly
            raise
        except Exception as exc:
            logger.error("Unhandled error parsing '%s': %s", file_path, exc, exc_info=True)
            raise DocumentProcessingError(
                f"Failed to process document '{os.path.basename(file_path)}': {exc}"
            ) from exc
