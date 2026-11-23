"""Application configuration module using pydantic-settings.

Loads environment variables from .env file or system environment with typed
defaults and validation for all core infrastructure, AI models, pipelines,
storage paths, and security settings.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """LectureForge AI backend application settings."""

    # Project directories
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://lectureforge:lectureforge@localhost:5432/lectureforge",
        description="Async PostgreSQL connection string using asyncpg driver",
    )
    DATABASE_URL_SYNC: str | None = Field(
        default="postgresql://lectureforge:lectureforge@localhost:5432/lectureforge",
        description="Synchronous PostgreSQL connection string for sync migrations if needed",
    )

    # Redis & Celery
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for caching and state management",
    )
    CELERY_BROKER_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Celery message broker URL",
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://localhost:6379/1",
        description="Celery result backend URL",
    )

    # AI / Gemini API
    GEMINI_API_KEY: str | None = Field(
        default=None,
        description="Google Gemini API key. If not set, AI generation endpoints will return 400.",
    )
    GEMINI_MODEL: str = Field(
        default="gemini-3.5-flash",
        description="Default Gemini model to use for extraction, summarization, and evaluation",
    )

    # File Storage
    MAX_UPLOAD_SIZE_MB: int = Field(
        default=50,
        description="Maximum allowed upload file size in megabytes",
    )
    UPLOAD_DIR: str = Field(
        default="uploads",
        description="Directory path where uploaded documents are stored",
    )
    EXPORT_DIR: str = Field(
        default="exports",
        description="Directory path where exported study packs are saved",
    )

    # Security & CORS
    CORS_ORIGINS: list[str] | str = Field(
        default=["http://localhost:3000", "http://frontend:3000"],
        description="List of allowed CORS origins or comma-separated string",
    )
    SECRET_KEY: str = Field(
        default="lectureforge-insecure-default-secret-key-change-in-production",
        description="Secret key used for security operations and token signing",
    )

    # Logging & Observability
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Application logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    LOG_FORMAT: str = Field(
        default="console",
        description="Log format: 'json' for production or 'console' for local dev",
    )

    # Pipeline & Processing Configuration
    PROMPT_VERSION: str = Field(
        default="v1.0",
        description="Version tag of active prompts used during extraction and generation",
    )
    MAX_RETRY_ATTEMPTS: int = Field(
        default=2,
        description="Maximum retry attempts allowed for pipeline generation phases",
    )
    CHUNK_SIZE: int = Field(
        default=2000,
        description="Target token or character size for document text chunks",
    )
    CHUNK_OVERLAP: int = Field(
        default=200,
        description="Overlap size between contiguous document text chunks",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, value: Any) -> list[str]:
        """Parse comma-separated or JSON origin strings into a cleaned list."""
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return ["http://localhost:3000"]
            if value.startswith("[") and value.endswith("]"):
                try:
                    import json

                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return [str(origin).strip() for origin in parsed if str(origin).strip()]
                except Exception:
                    pass
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        if isinstance(value, (list, tuple, set)):
            return [str(origin).strip() for origin in value if str(origin).strip()]
        return ["http://localhost:3000"]

    @property
    def max_upload_size_bytes(self) -> int:
        """Return the maximum upload size in bytes."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def resolved_upload_dir(self) -> Path:
        """Return the resolved absolute Path to the upload directory."""
        upload_path = Path(self.UPLOAD_DIR)
        if not upload_path.is_absolute():
            upload_path = self.BASE_DIR / upload_path
        upload_path.mkdir(parents=True, exist_ok=True)
        return upload_path

    @property
    def resolved_export_dir(self) -> Path:
        """Return the resolved absolute Path to the export directory."""
        export_path = Path(self.EXPORT_DIR)
        if not export_path.is_absolute():
            export_path = self.BASE_DIR / export_path
        export_path.mkdir(parents=True, exist_ok=True)
        return export_path

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached singleton instance of application settings."""
    return Settings()


settings: Settings = get_settings()
