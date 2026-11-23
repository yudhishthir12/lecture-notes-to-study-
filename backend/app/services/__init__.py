"""Document parsing, AI LLM, and processing services for LectureForge AI."""

from .chunker import SemanticChunker
from .document_processor import DocumentProcessor
from .exceptions import (
    DocumentProcessingError,
    EmptyDocumentError,
    FileCorruptedError,
    FileEncryptedError,
    OCRUnavailableError,
    ParsingError,
    UnsupportedFileTypeError,
)
from .llm_service import (
    GeminiProvider,
    LLMConfigurationError,
    LLMMalformedResponseError,
    LLMRateLimitError,
    LLMService,
    LLMServiceError,
    LLMTimeoutError,
    get_llm_service,
)
from .models import (
    BlockType,
    ContentBlock,
    DocumentChunk,
    ParsedDocument,
    ParsedPage,
    ProcessingResult,
)
from .noise_filter import NoiseFilter
from .ocr_service import OCRService
from .pdf_parser import PDFParser
from .pptx_parser import PPTXParser
from .prompt_registry import (
    PROMPT_REGISTRY,
    PROMPT_VERSION,
    get_prompt,
)
from .txt_parser import TXTParser

__all__ = [
    # Document Services
    "DocumentProcessor",
    "PDFParser",
    "PPTXParser",
    "TXTParser",
    "NoiseFilter",
    "SemanticChunker",
    "OCRService",
    # AI / LLM Services
    "LLMService",
    "GeminiProvider",
    "get_llm_service",
    "LLMServiceError",
    "LLMConfigurationError",
    "LLMRateLimitError",
    "LLMTimeoutError",
    "LLMMalformedResponseError",
    # Prompt Registry
    "get_prompt",
    "PROMPT_VERSION",
    "PROMPT_REGISTRY",
    # Models
    "BlockType",
    "ContentBlock",
    "ParsedDocument",
    "ParsedPage",
    "DocumentChunk",
    "ProcessingResult",
    # Exceptions
    "DocumentProcessingError",
    "FileCorruptedError",
    "FileEncryptedError",
    "UnsupportedFileTypeError",
    "EmptyDocumentError",
    "OCRUnavailableError",
    "ParsingError",
]
