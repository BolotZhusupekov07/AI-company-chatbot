from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from entrypoints.http.routers import health as health_router

BASE_PREFIX = "/api/v1"


class ApplicationHttpInterface:
    """HTTP interface that wires middleware, handlers, and routes."""

    def __init__(self, fastapi_config: dict) -> None:
        self.app = FastAPI(**fastapi_config)

    async def register_middlewares(self) -> None:
        """Register HTTP middleware."""

        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def register_exception_handlers(self) -> None:
        """Register HTTP exception handlers."""

    async def register_urls(self) -> None:
        """Register HTTP routers."""

        self.app.include_router(health_router.router, prefix=BASE_PREFIX, tags=["health"])
