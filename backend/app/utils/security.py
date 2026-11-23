"""Security and input validation utilities for LectureForge AI.

Provides file sanitization, MIME-type and extension validation, upload size bounds
checking, and safe path resolution to prevent path traversal and arbitrary file write attacks.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Set

# Permitted file extensions for document ingestion
ALLOWED_EXTENSIONS: Set[str] = {".pdf", ".pptx", ".txt"}

# Permitted MIME types
ALLOWED_MIME_TYPES: Set[str] = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.ms-powerpoint",
    "text/plain",
    "application/octet-stream",  # Permitted when paired with a valid extension
}


def sanitize_filename(filename: str) -> str:
    """Sanitize an untrusted filename to prevent directory traversal and filesystem attacks.

    - Strips leading/trailing whitespace and control/null characters.
    - Extracts only the basename to prevent path traversal (../ or ..\\).
    - Replaces characters outside [a-zA-Z0-9._-] with underscores.
    - Collapses multiple underscores and dots.
    - Defaults to 'document.bin' if the result is empty.

    Args:
        filename: Untrusted original filename from user upload.

    Returns:
        Safe, sanitized filename string.
    """
    if not filename:
        return "document.bin"

    # Remove null bytes and control characters
    cleaned = filename.replace("\x00", "").strip()

    # Extract basename handling both Unix and Windows separators
    cleaned = cleaned.replace("\\", "/")
    base_name = cleaned.split("/")[-1]

    # Replace invalid filesystem characters with underscores
    safe_name = re.sub(r"[^\w\.-]", "_", base_name)

    # Collapse consecutive underscores or dots
    safe_name = re.sub(r"_{2,}", "_", safe_name)
    safe_name = re.sub(r"\.{2,}", ".", safe_name)

    # Prevent hidden files or leading periods/underscores
    safe_name = safe_name.strip("._")

    # If filename had an extension, ensure it wasn't stripped away
    ext = Path(base_name).suffix
    if not safe_name:
        return f"document{ext}" if ext else "document.bin"

    return safe_name


def validate_file_extension(filename: str) -> bool:
    """Check whether a filename possesses an allowed file extension.

    Args:
        filename: Filename or path to inspect.

    Returns:
        True if the file extension is one of .pdf, .pptx, or .txt (case-insensitive).
    """
    if not filename:
        return False
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXTENSIONS


def validate_mime_type(content_type: str | None) -> bool:
    """Validate that a declared MIME type matches allowed document formats.

    Args:
        content_type: Raw Content-Type header string (e.g. 'application/pdf; charset=utf-8').

    Returns:
        True if the normalized content type is permitted.
    """
    if not content_type:
        return False
    normalized = content_type.split(";")[0].strip().lower()
    return normalized in ALLOWED_MIME_TYPES


def validate_file_size(size: int, max_mb: int = 50) -> bool:
    """Validate that an uploaded file size is within acceptable bounds.

    Args:
        size: File size in bytes.
        max_mb: Maximum allowed file size in megabytes.

    Returns:
        True if size is strictly positive and does not exceed max_mb.
    """
    if size <= 0:
        return False
    max_bytes = max_mb * 1024 * 1024
    return size <= max_bytes


def safe_file_path(upload_dir: str | Path, filename: str) -> str:
    """Resolve an uploaded filename within a target directory and prevent directory traversal.

    Ensures that the final resolved path is strictly located within the upload directory.

    Args:
        upload_dir: Root directory path for storage.
        filename: Filename to combine with upload_dir.

    Returns:
        Absolute resolved string path.

    Raises:
        ValueError: If a directory traversal attack or invalid path is detected.
    """
    clean_name = sanitize_filename(filename)
    base_dir = Path(upload_dir).resolve()
    target_path = (base_dir / clean_name).resolve()

    try:
        # Check that target_path is relative to base_dir
        target_path.relative_to(base_dir)
    except ValueError as exc:
        raise ValueError(f"Path traversal detected for filename: {filename!r}") from exc

    return str(target_path)
