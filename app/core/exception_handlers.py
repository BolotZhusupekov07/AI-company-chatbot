"""FastAPI exception handlers."""

from typing import cast

from fastapi import FastAPI, Request
from starlette import status
from starlette.responses import JSONResponse
from starlette.types import ExceptionHandler

from app.core.exceptions import AlreadyExistError, NotFoundError


def include_exception_handlers(app: FastAPI) -> None:
    """Register service exception handlers."""

    app.add_exception_handler(NotFoundError, cast(ExceptionHandler, not_found_exception_handler))
    app.add_exception_handler(AlreadyExistError, cast(ExceptionHandler, conflict_exception_handler))


async def not_found_exception_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    """Return a 404 response for service not-found errors."""

    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc) or "Not Found"},
    )


async def conflict_exception_handler(request: Request, exc: AlreadyExistError) -> JSONResponse:
    """Return a 409 response for service conflict errors."""

    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc) or "Conflict"},
    )
