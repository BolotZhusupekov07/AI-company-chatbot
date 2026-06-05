"""Chat answer agent dependencies."""

from pydantic import BaseModel, ConfigDict, Field, SkipValidation

from app.core.config import Settings
from app.infrastructure.embeddings.bedrock_cohere_provider import BedrockCohereEmbeddingProvider
from app.infrastructure.vector_store.qdrant.client import build_qdrant_client
from app.infrastructure.vector_store.qdrant.repository import QdrantVectorRepository
from app.services.hybrid_search_service import HybridSearchService
from app.services.identity_resolution_service import LocalIdentityResolver
from app.services.rerank.bedrock.service import BedrockCohereRerankService
from app.services.rerank.openai.service import build_openai_rerank_service


class ChatAgentDeps(BaseModel):
    """Dependencies available to chat agent tools."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    user_email: str
    identity_resolver: SkipValidation[LocalIdentityResolver]
    hybrid_search_service: SkipValidation[HybridSearchService]
    retrieved_source_ids: list[str] = Field(default_factory=list)

    def remember_retrieved_source_id(self, source_id: str) -> None:
        """Remember a source id returned by the knowledge search tool during this agent run."""

        normalized_source_id = source_id.strip()
        if normalized_source_id and normalized_source_id not in self.retrieved_source_ids:
            self.retrieved_source_ids.append(normalized_source_id)


def get_chat_agent_deps(user_email: str, settings: Settings):
    qdrant_client = build_qdrant_client(settings)
    qdrant_repo = QdrantVectorRepository(
        client=qdrant_client,
        collection_name=settings.QDRANT_COLLECTION_NAME,
        dense_vector_name=settings.QDRANT_DENSE_VECTOR_NAME,
        sparse_vector_name=settings.QDRANT_SPARSE_VECTOR_NAME,
        sparse_model_id=settings.QDRANT_BM25_MODEL_ID,
        bm25_language=settings.QDRANT_BM25_LANGUAGE,
        dense_search_limit=settings.HYBRID_DENSE_LIMIT,
        sparse_search_limit=settings.HYBRID_SPARSE_LIMIT,
        rrf_k=settings.HYBRID_RRF_K,
        dense_score_threshold=settings.HYBRID_DENSE_SCORE_THRESHOLD,
    )
    primary_reranker = BedrockCohereRerankService(
        region_name=settings.AWS_REGION_NAME,
        model_id=settings.BEDROCK_RERANK_MODEL_ID,
    )
    secondary_reranker = (
        build_openai_rerank_service(
            api_key=settings.OPENAI_API_KEY,
            model_id=settings.OPENAI_RERANK_MODEL_ID,
            base_url=settings.OPENAI_API_BASE_URL,
            timeout_seconds=settings.OPENAI_RERANK_TIMEOUT_SECONDS,
        )
        if settings.OPENAI_API_KEY
        else None
    )
    hybrid_search_service = HybridSearchService(
        embedding_provider=BedrockCohereEmbeddingProvider(region_name=settings.AWS_REGION_NAME),
        qdrant_repo=qdrant_repo,
        primary_reranker=primary_reranker,
        secondary_reranker=secondary_reranker,
        source_language=settings.KNOWLEDGE_SOURCE_LANGUAGE,
        primary_rerank_limit=settings.BEDROCK_RERANK_CANDIDATE_LIMIT,
        secondary_rerank_limit=settings.OPENAI_RERANK_CANDIDATE_LIMIT,
        top_k=settings.HYBRID_TOP_K,
    )
    identity_resolver = LocalIdentityResolver()
    return ChatAgentDeps(
        user_email=user_email,
        identity_resolver=identity_resolver,
        hybrid_search_service=hybrid_search_service,
    )
