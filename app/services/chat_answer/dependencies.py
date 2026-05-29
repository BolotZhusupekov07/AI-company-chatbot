"""Chat answer agent dependencies."""

from dataclasses import dataclass

from app.infrastructure.embeddings.bedrock_cohere_provider import BedrockCohereEmbeddingProvider
from app.infrastructure.vector_store.qdrant.repository import QdrantVectorRepository
from app.services.identity_resolution_service import LocalIdentityResolver


@dataclass(frozen=True, slots=True)
class ChatAgentDeps:
    """Dependencies available to chat agent tools."""

    user_email: str
    identity_resolver: LocalIdentityResolver
    embedding_provider: BedrockCohereEmbeddingProvider
    qdrant_repo: QdrantVectorRepository
