"""Test fixtures."""

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.infrastructure.db.database import Base, get_session
import app.infrastructure.db.models.chat
from app.main import create_app
from app.services.chat_answer.service import ChatAnswerService

TEST_HOST = "http://test"


class StubChatAnswerService:
    """Test double for chat answer generation."""

    def __init__(self) -> None:
        self.response = "Retrieved answer"
        self.calls: list[dict[str, object]] = []

    async def answer(self, *, question: str, user_email: str, message_history: object) -> str:
        self.calls.append(
            {
                "question": question,
                "user_email": user_email,
                "message_history": message_history,
            }
        )
        return self.response


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncGenerator[AsyncEngine, Any]:
    """Create a test database for one test."""

    database_path = tmp_path / "test.db"
    test_engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}", echo=False)
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    try:
        yield test_engine
    finally:
        await test_engine.dispose()


@pytest.fixture
async def app(engine: AsyncEngine) -> AsyncGenerator[FastAPI, Any]:
    """Create an app wired to the test database."""

    test_app = create_app()
    connection = await engine.connect()
    transaction = await connection.begin()
    session_factory = async_sessionmaker(connection, expire_on_commit=False)
    session = session_factory()
    answer_service = StubChatAnswerService()
    test_app.state.answer_service = answer_service
    test_app.dependency_overrides[get_session] = lambda: session
    test_app.dependency_overrides[ChatAnswerService] = lambda: answer_service

    try:
        yield test_app
    finally:
        test_app.dependency_overrides.pop(get_session, None)
        test_app.dependency_overrides.pop(ChatAnswerService, None)
        await transaction.rollback()
        await session.close()
        await connection.close()


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, Any]:
    """Create an async HTTP client for the test app."""

    async with AsyncClient(transport=ASGITransport(app=app), base_url=TEST_HOST) as test_client:
        yield test_client


@pytest.fixture
async def session(app: FastAPI) -> AsyncSession:
    """Return the app's overridden database session."""

    return app.dependency_overrides[get_session]()


@pytest.fixture
def answer_service(app: FastAPI) -> StubChatAnswerService:
    """Return the app's overridden chat answer service."""

    return app.state.answer_service
