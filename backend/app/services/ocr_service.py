"""
OCR Service fallback for scanned documents and images using Tesseract and pytesseract.
"""

from __future__ import annotations

import io
import logging
import os
import shutil
from typing import Optional

import pytesseract
from PIL import Image
from pytesseract import TesseractNotFoundError

from .exceptions import OCRUnavailableError

logger = logging.getLogger(__name__)

# Common default locations for Tesseract on Windows and Unix
DEFAULT_TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Users\hp\AppData\Local\Tesseract-OCR\tesseract.exe",
    "/usr/bin/tesseract",
    "/usr/local/bin/tesseract",
    "/opt/homebrew/bin/tesseract",
]


class OCRService:
    """Service to detect and execute optical character recognition on image data."""

    def __init__(self, tesseract_cmd: Optional[str] = None) -> None:
        self._custom_cmd = (
            tesseract_cmd or os.getenv("TESSERACT_CMD") or os.getenv("TESSERACT_PATH")
        )
        self._configure_tesseract()
        self._is_available: Optional[bool] = None

    def _configure_tesseract(self) -> None:
        """Attempt to locate and set pytesseract command path."""
        if self._custom_cmd and os.path.exists(self._custom_cmd):
            pytesseract.pytesseract.tesseract_cmd = self._custom_cmd
            return

        # Check if already in PATH
        which_tess = shutil.which("tesseract")
        if which_tess:
            pytesseract.pytesseract.tesseract_cmd = which_tess
            return

        # Check known common directories
        for path in DEFAULT_TESSERACT_PATHS:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                logger.info("Auto-configured Tesseract path to: %s", path)
                return

    def is_available(self) -> bool:
        """
        Check whether Tesseract binary is accessible and executable.
        Caches result after first check.
        """
        if self._is_available is not None:
            return self._is_available

        try:
            _ = pytesseract.get_tesseract_version()
            self._is_available = True
        except (TesseractNotFoundError, FileNotFoundError, Exception) as exc:
            logger.debug("Tesseract OCR is not available: %s", exc)
            self._is_available = False

        return self._is_available

    def extract_text_from_image(self, image_bytes: bytes, lang: str = "eng") -> str:
        """
        Extract text from raw image bytes using Tesseract OCR.

        Args:
            image_bytes: Raw bytes representing an image (PNG, JPEG, etc.).
            lang: Language code for Tesseract (default 'eng').

        Returns:
            Extracted text string.

        Raises:
            OCRUnavailableError: If Tesseract OCR is not installed or available.
            ValueError: If image_bytes is empty or invalid.
        """
        if not image_bytes:
            return ""

        if not self.is_available():
            raise OCRUnavailableError(
                "Tesseract OCR is not installed or not found in system PATH. "
                "To extract text from scanned documents, install Tesseract OCR "
                "(Windows: https://github.com/UB-Mannheim/tesseract/wiki, "
                "Ubuntu/Debian: apt-get install tesseract-ocr) and ensure it is in PATH."
            )

        try:
            image = Image.open(io.BytesIO(image_bytes))
            # Convert non-RGB/L images (like palette/RGBA) to RGB
            if image.mode not in ("L", "RGB"):
                image = image.convert("RGB")

            text = pytesseract.image_to_string(image, lang=lang)
            return text.strip()
        except OCRUnavailableError:
            raise
        except Exception as exc:
            logger.error("Error during OCR extraction: %s", exc)
            raise OCRUnavailableError(f"Failed to execute OCR on image: {exc}") from exc

    def get_status_message(self) -> str:
        """Provide a human-readable diagnostic message regarding OCR readiness."""
        if self.is_available():
            return "Tesseract OCR is installed and ready."
        return (
            "Tesseract OCR is NOT installed or configured. Scanned pages will not "
            "have OCR text extracted unless Tesseract is installed."
        )
