"""FastAPI application entrypoint for LectureForge AI.

Configures application lifespan, database table creation, CORS middleware,
structured logging with structlog, custom exception handlers, and API routing.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.database import close_db, init_db
from app.core.logging import get_logger, setup_logging

# Configure structured logging before application initialization
setup_logging()
logger = get_logger("lectureforge.app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle events."""
    logger.info(
        "LectureForge AI Backend starting up",
        prompt_version=settings.PROMPT_VERSION,
        gemini_model=settings.GEMINI_MODEL,
        upload_dir=str(settings.resolved_upload_dir),
        export_dir=str(settings.resolved_export_dir),
    )

    # Ensure required runtime storage directories exist
    settings.resolved_upload_dir
    settings.resolved_export_dir

    # Create database schema on startup if not already created
    try:
        await init_db()
        logger.info("Database schema initialized successfully")
    except Exception as exc:
        logger.error(
            "Database table initialization failed on startup (will rely on migrations)",
            error=str(exc),
        )

    yield

    # Graceful shutdown: release database pool
    logger.info("LectureForge AI Backend shutting down")
    await close_db()


app = FastAPI(
    title="LectureForge AI API",
    description=(
        "Production-ready backend API that transforms lecture notes, textbook chapters, "
        "and slide decks into comprehensive study packs with citations, evaluation rubrics, "
        "and export pipelines."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS Middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Standardize validation error responses."""
    logger.warning(
        "Request validation error",
        path=request.url.path,
        errors=exc.errors(),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": jsonable_encoder(exc.errors()),
            "message": "Request validation failed. Please check your payload parameters.",
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Format HTTP exceptions into consistent JSON errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all error handler for unexpected server exceptions."""
    logger.error(
        "Unhandled server error occurred",
        path=request.url.path,
        error=str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred. Please contact system support.",
        },
    )


# Health check endpoints
@app.get(
    "/health",
    tags=["System"],
    summary="Root Health Check",
    description="Returns operational status and uptime timestamp.",
)
async def health_check() -> dict[str, str]:
    """Health check for load balancers and container orchestrators."""
    return {
        "status": "healthy",
        "app": "LectureForge AI",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get(
    "/",
    tags=["System"],
    summary="Application Root",
    description="Returns API service information.",
)
async def root() -> dict[str, str]:
    """Service landing endpoint with links to documentation."""
    return {
        "message": "Welcome to LectureForge AI API",
        "docs": "/docs",
        "health": "/health",
        "api_prefix": "/api",
    }


# Mount API routers under /api prefix
app.include_router(api_router, prefix="/api")
