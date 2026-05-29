"""Chat answer orchestration service."""

from collections.abc import Sequence
from typing import Annotated

from fastapi import Depends
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.settings import ModelSettings

from app.api.v1.chats.schemas import ChatMessage
from app.core.config import Settings, get_settings
from app.core.enums import Role
from app.infrastructure.embeddings.bedrock_cohere_provider import BedrockCohereEmbeddingProvider
from app.infrastructure.vector_store.qdrant.client import build_qdrant_client
from app.infrastructure.vector_store.qdrant.repository import QdrantVectorRepository
from app.services.chat_answer.agent import get_chat_agent
from app.services.chat_answer.constants import CHAT_ANSWER_NOT_FOUND_MESSAGE
from app.services.chat_answer.dependencies import ChatAgentDeps
from app.services.identity_resolution_service import LocalIdentityResolver


class ChatAnswerService:
    """Build chat answers from an LLM agent with retrieval tools."""

    def __init__(
        self,
        settings: Annotated[Settings, Depends(get_settings)],
        agent: Annotated[Agent[ChatAgentDeps, str], Depends(get_chat_agent)],
    ) -> None:
        self._settings = settings
        self._agent = agent
        self._identity_resolver = LocalIdentityResolver()

    async def answer(
        self,
        *,
        question: str,
        user_email: str,
        message_history: Sequence[ChatMessage],
    ) -> str:
        """Return an agent answer for the question."""

        result = await self._agent.run(
            question,
            deps=self._build_deps(user_email),
            message_history=self._build_message_history(message_history),
            model_settings=ModelSettings(
                temperature=0.0,
                max_tokens=self._settings.CHAT_LLM_MAX_TOKENS,
            ),
        )
        answer = (result.output or "").strip()
        return answer or CHAT_ANSWER_NOT_FOUND_MESSAGE

    def _build_deps(self, user_email: str) -> ChatAgentDeps:
        qdrant_client = build_qdrant_client(self._settings)
        return ChatAgentDeps(
            user_email=user_email,
            identity_resolver=self._identity_resolver,
            embedding_provider=BedrockCohereEmbeddingProvider(region_name=self._settings.AWS_REGION_NAME),
            qdrant_repo=QdrantVectorRepository(
                client=qdrant_client,
                collection_name=self._settings.QDRANT_COLLECTION_NAME,
            ),
        )

    def _build_message_history(self, messages: Sequence[ChatMessage]) -> list[ModelMessage]:
        history: list[ModelMessage] = []
        for message in messages:
            if message.role == Role.USER:
                history.append(ModelRequest(parts=[UserPromptPart(content=message.content)]))
            elif message.role == Role.AGENT:
                history.append(ModelResponse(parts=[TextPart(content=message.content)]))
        return history
