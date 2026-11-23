"""FastAPI API routes module."""

from app.api.documents import router as documents_router
from app.api.router import api_router
from app.api.study_packs import router as study_packs_router

__all__ = ["api_router", "documents_router", "study_packs_router"]
