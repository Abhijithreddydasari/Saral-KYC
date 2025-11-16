"""Health and readiness endpoints."""

from fastapi import APIRouter

from app import __version__
from app.schemas.system import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="API health check")
async def health_check() -> HealthResponse:
    """Returns a simple health payload."""
    return HealthResponse(status="ok", app_version=__version__)

