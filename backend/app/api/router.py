"""Main API router combining all resource routers."""

from fastapi import APIRouter

from app.api.documents import router as documents_router
from app.api.study_packs import router as study_packs_router

api_router = APIRouter()

# Mount feature sub-routers
api_router.include_router(
    documents_router,
    prefix="/documents",
    tags=["Documents"],
)
api_router.include_router(
    study_packs_router,
    prefix="/study-packs",
    tags=["Study Packs"],
)


@api_router.get(
    "/health",
    tags=["System"],
    summary="API Health Check",
    description="Returns current operational status of the LectureForge AI API.",
)
async def api_health() -> dict[str, str]:
    """Health check endpoint for Kubernetes / Docker container monitoring."""
    return {
        "status": "healthy",
        "service": "LectureForge AI Backend",
        "api_version": "v1",
    }
