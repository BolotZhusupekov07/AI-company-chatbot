import uvicorn

from configs import HttpConfig
from entrypoints.http import interface as http_interface


def _create_interface() -> http_interface.ApplicationHttpInterface:
    """Create the HTTP interface."""

    return http_interface.ApplicationHttpInterface(
        fastapi_config={
            "title": "AI Chatbot Company",
            "version": "0.1.0",
            "docs_url": "/docs",
            "redoc_url": "/redoc",
        },
    )


async def get_app():
    """Create and configure the FastAPI app without starting a server."""

    interface = _create_interface()
    await interface.register_middlewares()
    interface.register_exception_handlers()
    await interface.register_urls()
    return interface.app


async def create_app() -> None:
    """Create and serve the HTTP application."""

    app = await get_app()
    config = HttpConfig()
    server_config = uvicorn.Config(app=app, host=config.HOST, port=config.PORT, log_level="info")
    server = uvicorn.Server(server_config)
    await server.serve()
