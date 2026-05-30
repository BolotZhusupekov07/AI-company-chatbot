from typing import Any, cast

from qdrant_client import models

from app.infrastructure.embeddings.bedrock_cohere_provider import BedrockCohereEmbeddingProvider
from app.infrastructure.rerankers.exceptions import RemoteRerankError
from app.infrastructure.rerankers.interface import RemoteReranker
from app.infrastructure.rerankers.schemas import RerankRequest, RerankScore
from app.infrastructure.vector_store.qdrant.repository import QdrantVectorRepository
from app.infrastructure.vector_store.qdrant.schemas import (
    QdrantChunkPayload,
    QdrantChunkSearchResult,
)
from app.services.hybrid_search_service import HybridSearchService


def test_hybrid_search_service_uses_openai_fallback_after_primary_rerank_failure() -> None:
    class FakeEmbeddingProvider:
        def embed_query(self, query_text: str) -> list[float]:
            assert query_text == "SAML VPN"
            return [0.1, 0.2]

    class FakeQdrantRepository:
        def __init__(self) -> None:
            self.calls: list[Any] = []

        def search_hybrid(self, request: Any) -> list[QdrantChunkSearchResult]:
            self.calls.append(request)
            return [
                _search_result("chunk-a", score=0.04, text="Vacation policy"),
                _search_result("chunk-b", score=0.03, text="VPN setup with SAML"),
            ]

    class FailingReranker:
        provider_name = "primary"

        def rerank(self, request: RerankRequest) -> list[RerankScore]:
            raise RemoteRerankError("primary unavailable")

    class FallbackReranker:
        provider_name = "openai"

        def __init__(self) -> None:
            self.calls: list[RerankRequest] = []

        def rerank(self, request: RerankRequest) -> list[RerankScore]:
            self.calls.append(request)
            return [
                RerankScore(index=1, score=0.99),
                RerankScore(index=0, score=0.12),
            ]

    qdrant_repo = FakeQdrantRepository()
    fallback = FallbackReranker()
    service = HybridSearchService(
        embedding_provider=cast(BedrockCohereEmbeddingProvider, FakeEmbeddingProvider()),
        qdrant_repo=cast(QdrantVectorRepository, qdrant_repo),
        primary_reranker=cast(RemoteReranker, FailingReranker()),
        secondary_reranker=cast(RemoteReranker, fallback),
        source_language="en",
        primary_rerank_limit=3,
        secondary_rerank_limit=2,
        top_k=1,
    )

    results = service.search(query=" SAML VPN ", user_email="aida@example.com", user_groups=["employees"])

    assert results[0].payload.chunk_id == "chunk-b"
    assert results[0].rrf_score == 0.03
    assert results[0].dense_score is None
    assert results[0].sparse_score is None
    assert results[0].rerank_score == 0.99
    assert results[0].rerank_provider == "openai"
    assert fallback.calls[0].documents == ["Vacation policy", "VPN setup with SAML"]
    assert fallback.calls[0].top_n == 2

    request = qdrant_repo.calls[0]
    assert request.query_vector == [0.1, 0.2]
    assert request.query_text == "SAML VPN"
    assert request.limit == 3
    assert isinstance(request.dense_filter, models.Filter)
    assert isinstance(request.sparse_filter, models.Filter)


def test_hybrid_search_service_keeps_rrf_order_when_rerankers_fail() -> None:
    class FakeEmbeddingProvider:
        def embed_query(self, query_text: str) -> list[float]:
            return [0.1, 0.2]

    class FakeQdrantRepository:
        def search_hybrid(self, request: Any) -> list[QdrantChunkSearchResult]:
            return [_search_result("chunk-b", score=0.04), _search_result("chunk-a", score=0.03)]

    class FailingReranker:
        provider_name = "unavailable"

        def rerank(self, request: RerankRequest) -> list[RerankScore]:
            raise RemoteRerankError("unavailable")

    service = HybridSearchService(
        embedding_provider=cast(BedrockCohereEmbeddingProvider, FakeEmbeddingProvider()),
        qdrant_repo=cast(QdrantVectorRepository, FakeQdrantRepository()),
        primary_reranker=cast(RemoteReranker, FailingReranker()),
        secondary_reranker=cast(RemoteReranker, FailingReranker()),
        source_language="en",
        primary_rerank_limit=3,
        secondary_rerank_limit=2,
        top_k=2,
    )

    results = service.search(query="policy", user_email="aida@example.com", user_groups=["employees"])

    assert [result.payload.chunk_id for result in results] == ["chunk-b", "chunk-a"]
    assert all(result.rerank_score is None for result in results)


def _search_result(chunk_id: str, *, score: float, text: str | None = None) -> QdrantChunkSearchResult:
    return QdrantChunkSearchResult(
        payload=QdrantChunkPayload(
            chunk_id=chunk_id,
            source_id=f"{chunk_id}.md",
            document_group_id="group",
            language="en",
            space="company",
            allowed_users=[],
            allowed_groups=["employees"],
            text=text or f"{chunk_id} text",
            chunk_index=0,
            character_count=len(text or f"{chunk_id} text"),
        ),
        score=score,
    )
