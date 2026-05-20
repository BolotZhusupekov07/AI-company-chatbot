from fastapi import APIRouter

from app.api.health_checks.schemas import HealthCheckLiveResponse, HealthCheckReadyResponse
from app.core.config import get_settings

router = APIRouter(tags=["Health check"])


@router.get("/health/live")
async def health_check_liveness() -> HealthCheckLiveResponse:
    """Return liveness status."""

    settings = get_settings()
    return HealthCheckLiveResponse(version=settings.PROJECT_VERSION, status="UP")


@router.get("/health/ready")
async def health_check_readiness() -> HealthCheckReadyResponse:
    """Return readiness status."""

    settings = get_settings()
    return HealthCheckReadyResponse(version=settings.PROJECT_VERSION, status="READY")
