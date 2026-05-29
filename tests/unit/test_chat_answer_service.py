"""Chat answer service tests."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from pydantic_ai import Agent
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart
import pytest

from app.api.v1.chats.schemas import ChatMessage
from app.core.config import Settings
from app.core.enums import Language, Role
from app.infrastructure.embeddings.bedrock_cohere_provider import BedrockCohereEmbeddingProvider
from app.infrastructure.vector_store.qdrant.repository import (
    QdrantChunkPayload,
    QdrantChunkSearchResult,
    QdrantVectorRepository,
)
from app.services.chat_answer import service as chat_answer_service
from app.services.chat_answer.constants import (
    CHAT_ANSWER_NOT_FOUND_MESSAGE,
    CHAT_ANSWER_SCORE_THRESHOLD,
)
from app.services.chat_answer.dependencies import ChatAgentDeps
from app.services.chat_answer.service import ChatAnswerService
from app.services.chat_answer.tools import search_company_knowledge_tool
from app.services.identity_resolution_service import LocalIdentityResolver, ResolvedIdentity


@dataclass
class FakeAgentResult:
    output: str


class FakeAgent:
    def __init__(self, output: str) -> None:
        self.output = output
        self.calls: list[dict[str, Any]] = []

    async def run(self, user_prompt: str, **kwargs: Any) -> FakeAgentResult:
        self.calls.append({"user_prompt": user_prompt, **kwargs})
        return FakeAgentResult(self.output)


@pytest.mark.asyncio
async def test_answer_calls_agent_with_message_history_and_model_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = FakeAgent("Final answer")
    settings = Settings(CHAT_LLM_MAX_TOKENS=321)
    monkeypatch.setattr(chat_answer_service, "build_qdrant_client", lambda settings: object())
    monkeypatch.setattr(chat_answer_service, "BedrockCohereEmbeddingProvider", lambda region_name: object())
    monkeypatch.setattr(chat_answer_service, "QdrantVectorRepository", lambda **kwargs: object())
    service = ChatAnswerService(settings, cast(Agent[ChatAgentDeps, str], agent))

    history_messages = [
        _chat_message(index=1, role=Role.USER, content="Earlier question"),
        _chat_message(index=2, role=Role.AGENT, content="Earlier answer"),
    ]

    answer = await service.answer(
        question="Latest question",
        user_email="aida@example.com",
        message_history=history_messages,
    )

    assert answer == "Final answer"
    call = agent.calls[0]
    assert call["user_prompt"] == "Latest question"
    assert call["deps"].user_email == "aida@example.com"
    message_history = call["message_history"]
    assert isinstance(message_history[0], ModelRequest)
    assert isinstance(message_history[0].parts[0], UserPromptPart)
    assert message_history[0].parts[0].content == "Earlier question"
    assert isinstance(message_history[1], ModelResponse)
    assert isinstance(message_history[1].parts[0], TextPart)
    assert message_history[1].parts[0].content == "Earlier answer"
    assert call["model_settings"]["temperature"] == 0.0
    assert call["model_settings"]["max_tokens"] == 321


def test_search_company_knowledge_tool_returns_first_dense_search_result() -> None:
    class FakeIdentityResolver:
        def resolve_user(self, email: str) -> ResolvedIdentity:
            return ResolvedIdentity(
                email=email.lower(),
                full_name="Aida Mamatova",
                location="Bishkek",
                department="Engineering",
                groups=["employees"],
            )

    class FakeEmbeddingProvider:
        def embed_query(self, query_text: str) -> list[float]:
            assert query_text == "vacation policy"
            return [0.1, 0.2]

    class FakeQdrantRepository:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def search_dense(self, query_vector: Sequence[float], **kwargs: Any) -> list[QdrantChunkSearchResult]:
            self.calls.append({"query_vector": query_vector, **kwargs})
            return [
                QdrantChunkSearchResult(
                    payload=QdrantChunkPayload(
                        chunk_id="chunk-1",
                        source_id="source-1",
                        document_group_id="hr",
                        language="en",
                        space="company",
                        allowed_users=[],
                        allowed_groups=["employees"],
                        text="Vacation policy answer",
                        chunk_index=0,
                        character_count=22,
                    ),
                    score=0.92,
                )
            ]

    qdrant_repo = FakeQdrantRepository()
    deps = ChatAgentDeps(
        user_email="AIDA@example.com",
        identity_resolver=cast(LocalIdentityResolver, FakeIdentityResolver()),
        embedding_provider=cast(BedrockCohereEmbeddingProvider, FakeEmbeddingProvider()),
        qdrant_repo=cast(QdrantVectorRepository, qdrant_repo),
    )

    answer = search_company_knowledge_tool(deps, query="vacation policy")

    assert answer == "Vacation policy answer"
    assert qdrant_repo.calls[0]["query_vector"] == [0.1, 0.2]
    assert qdrant_repo.calls[0]["limit"] == 1
    assert qdrant_repo.calls[0]["score_threshold"] == CHAT_ANSWER_SCORE_THRESHOLD
    assert qdrant_repo.calls[0]["query_filter"] is not None


def test_search_company_knowledge_tool_returns_fallback_for_unknown_user() -> None:
    class FakeIdentityResolver:
        def resolve_user(self, email: str) -> None:
            return None

    class UnexpectedEmbeddingProvider:
        def embed_query(self, query_text: str) -> list[float]:
            raise AssertionError("embedding provider should not be called")

    class UnexpectedQdrantRepository:
        def search_dense(self, query_vector: Sequence[float], **kwargs: Any) -> list[QdrantChunkSearchResult]:
            raise AssertionError("qdrant repository should not be called")

    deps = ChatAgentDeps(
        user_email="unknown@example.com",
        identity_resolver=cast(LocalIdentityResolver, FakeIdentityResolver()),
        embedding_provider=cast(BedrockCohereEmbeddingProvider, UnexpectedEmbeddingProvider()),
        qdrant_repo=cast(QdrantVectorRepository, UnexpectedQdrantRepository()),
    )

    assert search_company_knowledge_tool(deps, query="policy") == CHAT_ANSWER_NOT_FOUND_MESSAGE


def _chat_message(*, index: int, role: Role, content: str) -> ChatMessage:
    timestamp = datetime(2026, 5, 29, 0, 0, index, tzinfo=UTC)
    return ChatMessage(
        id=UUID(f"00000000-0000-0000-0000-{index:012d}"),
        chat_id=UUID("00000000-0000-0000-0000-000000000010"),
        role=role,
        content=content,
        language=Language.RU,
        created_at=timestamp,
        updated_at=timestamp,
    )
