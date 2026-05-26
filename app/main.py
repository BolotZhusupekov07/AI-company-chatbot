from fastapi import FastAPI
import uvicorn

from app.api.health_checks.routes import router as health_checks_router
from app.api.v1.router import router as v1_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = get_settings()
    api = FastAPI(title=settings.PROJECT_NAME, version=settings.PROJECT_VERSION)
    api.include_router(v1_router)
    api.include_router(health_checks_router)
    return api


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "app.main:create_app", factory=True, host=settings.HOST, port=settings.PORT, log_level=settings.LOG_LEVEL
    )
