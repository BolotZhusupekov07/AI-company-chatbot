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
from app.infrastructure.rerankers.providers.bedrock_cohere import BedrockCohereRerankProvider
from app.infrastructure.rerankers.providers.openai import OpenAIRerankProvider
from app.infrastructure.vector_store.qdrant.client import build_qdrant_client
from app.infrastructure.vector_store.qdrant.repository import QdrantVectorRepository
from app.services.chat_answer.agent import get_chat_agent
from app.services.chat_answer.constants import CHAT_ANSWER_NOT_FOUND_MESSAGE
from app.services.chat_answer.dependencies import ChatAgentDeps
from app.services.hybrid_search_service import HybridSearchService
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
        qdrant_repo = QdrantVectorRepository(
            client=qdrant_client,
            collection_name=self._settings.QDRANT_COLLECTION_NAME,
            dense_vector_name=self._settings.QDRANT_DENSE_VECTOR_NAME,
            sparse_vector_name=self._settings.QDRANT_SPARSE_VECTOR_NAME,
            sparse_model_id=self._settings.QDRANT_BM25_MODEL_ID,
            bm25_language=self._settings.QDRANT_BM25_LANGUAGE,
            dense_search_limit=self._settings.HYBRID_DENSE_LIMIT,
            sparse_search_limit=self._settings.HYBRID_SPARSE_LIMIT,
            rrf_k=self._settings.HYBRID_RRF_K,
            dense_score_threshold=self._settings.HYBRID_DENSE_SCORE_THRESHOLD,
        )
        primary_reranker = BedrockCohereRerankProvider(
            region_name=self._settings.AWS_REGION_NAME,
            model_id=self._settings.BEDROCK_RERANK_MODEL_ID,
        )
        secondary_reranker = (
            OpenAIRerankProvider(
                api_key=self._settings.OPENAI_API_KEY,
                model_id=self._settings.OPENAI_RERANK_MODEL_ID,
                base_url=self._settings.OPENAI_API_BASE_URL,
                timeout_seconds=self._settings.OPENAI_RERANK_TIMEOUT_SECONDS,
            )
            if self._settings.OPENAI_API_KEY
            else None
        )
        hybrid_search_service = HybridSearchService(
            embedding_provider=BedrockCohereEmbeddingProvider(region_name=self._settings.AWS_REGION_NAME),
            qdrant_repo=qdrant_repo,
            primary_reranker=primary_reranker,
            secondary_reranker=secondary_reranker,
            source_language=self._settings.KNOWLEDGE_SOURCE_LANGUAGE,
            primary_rerank_limit=self._settings.BEDROCK_RERANK_CANDIDATE_LIMIT,
            secondary_rerank_limit=self._settings.OPENAI_RERANK_CANDIDATE_LIMIT,
            top_k=self._settings.HYBRID_TOP_K,
        )
        return ChatAgentDeps(
            user_email=user_email,
            identity_resolver=self._identity_resolver,
            hybrid_search_service=hybrid_search_service,
        )

    def _build_message_history(self, messages: Sequence[ChatMessage]) -> list[ModelMessage]:
        history: list[ModelMessage] = []
        for message in messages:
            if message.role == Role.USER:
                history.append(ModelRequest(parts=[UserPromptPart(content=message.content)]))
            elif message.role == Role.AGENT:
                history.append(ModelResponse(parts=[TextPart(content=message.content)]))
        return history
