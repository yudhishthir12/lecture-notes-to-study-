"""
Custom exceptions for document parsing and processing in LectureForge AI.
"""


class DocumentProcessingError(Exception):
    """Base exception for all document processing errors."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class FileCorruptedError(DocumentProcessingError):
    """Raised when a document file is corrupted, malformed, or unreadable."""

    pass


class FileEncryptedError(DocumentProcessingError):
    """Raised when a document file is encrypted or password-protected."""

    pass


class UnsupportedFileTypeError(DocumentProcessingError):
    """Raised when an unsupported file type is requested."""

    pass


class EmptyDocumentError(DocumentProcessingError):
    """Raised when an input document contains no pages or readable content."""

    pass


class OCRUnavailableError(DocumentProcessingError):
    """Raised when OCR fallback is required but Tesseract is not installed or available."""

    pass


class ParsingError(DocumentProcessingError):
    """Raised when an unrecoverable error occurs during parsing."""

    pass
