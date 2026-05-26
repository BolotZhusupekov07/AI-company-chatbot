from fastapi import APIRouter, Depends

from app.api.health_checks.schemas import HealthCheckLiveResponse, HealthCheckReadyResponse
from app.core.config import Settings, get_settings

router = APIRouter(tags=["Health check"])


@router.get("/health/live")
async def health_check_liveness(
    settings: Settings = Depends(get_settings)
) -> HealthCheckLiveResponse:
    """Return liveness status."""

    return HealthCheckLiveResponse(version=settings.PROJECT_VERSION, status="UP")


@router.get("/health/ready")
async def health_check_readiness(
    settings: Settings = Depends(get_settings)
) -> HealthCheckReadyResponse:
    """Return readiness status."""

    return HealthCheckReadyResponse(version=settings.PROJECT_VERSION, status="READY")
