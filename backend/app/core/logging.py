"""Structured logging configuration using structlog.

Provides context enrichment (document_id, pipeline_run_id, stage),
JSON output for production environments, and colorized console output for local development.
"""

import logging
import sys
from typing import Any

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars, merge_contextvars

from app.core.config import settings


def setup_logging() -> None:
    """Configure structured logging for the entire application.

    Routes standard library logging through structlog processors and applies
    appropriate formatters (JSON or formatted console).
    """
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    shared_processors: list[structlog.types.Processor] = [
        merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.LOG_FORMAT.lower() == "json" or settings.LOG_LEVEL.upper() == "PROD":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(
            colors=sys.stderr.isatty(),
            pad_event=30,
        )

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Silence overly verbose third-party loggers
    for logger_name in (
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "sqlalchemy.engine",
        "asyncio",
    ):
        sub_logger = logging.getLogger(logger_name)
        sub_logger.handlers.clear()
        sub_logger.addHandler(handler)
        sub_logger.propagate = False
        sub_logger.setLevel(logging.INFO if "uvicorn" in logger_name else logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a configured structlog bound logger."""
    return structlog.get_logger(name)


def set_pipeline_context(
    document_id: Any | None = None,
    pipeline_run_id: Any | None = None,
    stage: str | None = None,
) -> None:
    """Bind pipeline-specific contextual variables to thread/task local context."""
    context: dict[str, Any] = {}
    if document_id is not None:
        context["document_id"] = str(document_id)
    if pipeline_run_id is not None:
        context["pipeline_run_id"] = str(pipeline_run_id)
    if stage is not None:
        context["stage"] = stage
    if context:
        bind_contextvars(**context)


def clear_pipeline_context() -> None:
    """Clear all bound context variables."""
    clear_contextvars()
