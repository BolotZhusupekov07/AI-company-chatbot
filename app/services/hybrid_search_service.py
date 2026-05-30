"""Hybrid retrieval orchestration."""

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from app.infrastructure.embeddings.bedrock_cohere_provider import BedrockCohereEmbeddingProvider
from app.infrastructure.rerankers.exceptions import RemoteRerankError
from app.infrastructure.rerankers.interface import RemoteReranker
from app.infrastructure.rerankers.schemas import RerankRequest, RerankScore
from app.infrastructure.vector_store.qdrant.repository import (
    QdrantVectorRepository,
    build_acl_filter,
    build_acl_language_filter,
)
from app.infrastructure.vector_store.qdrant.schemas import QdrantChunkPayload, QdrantHybridSearchRequest


class HybridSearchResult(BaseModel):
    """A fused and optionally reranked search result."""

    model_config = ConfigDict(frozen=True)

    payload: QdrantChunkPayload
    rrf_score: float
    dense_score: float | None = None
    sparse_score: float | None = None
    rerank_score: float | None = None
    rerank_provider: str | None = None


class HybridSearchService:
    """Runs Qdrant hybrid search and remote reranking."""

    def __init__(
        self,
        *,
        embedding_provider: BedrockCohereEmbeddingProvider,
        qdrant_repo: QdrantVectorRepository,
        primary_reranker: RemoteReranker,
        secondary_reranker: RemoteReranker | None,
        source_language: str,
        primary_rerank_limit: int,
        secondary_rerank_limit: int,
        top_k: int,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._qdrant_repo = qdrant_repo
        self._primary_reranker = primary_reranker
        self._secondary_reranker = secondary_reranker
        self._source_language = source_language
        self._primary_rerank_limit = primary_rerank_limit
        self._secondary_rerank_limit = secondary_rerank_limit
        self._top_k = top_k

    def search(self, *, query: str, user_email: str, user_groups: Sequence[str]) -> list[HybridSearchResult]:
        """Return the best chunks for a query after hybrid retrieval and reranking."""

        query_text = query.strip()
        if not query_text:
            raise ValueError("query must not be blank")

        query_vector = self._embedding_provider.embed_query(query_text)
        fused_results = self._qdrant_repo.search_hybrid(
            QdrantHybridSearchRequest(
                query_vector=query_vector,
                query_text=query_text,
                limit=max(self._primary_rerank_limit, self._top_k),
                dense_filter=build_acl_filter(user_email, user_groups),
                sparse_filter=build_acl_language_filter(user_email, user_groups, self._source_language),
            )
        )
        fused = [
            HybridSearchResult(
                payload=result.payload,
                rrf_score=result.score,
            )
            for result in fused_results
        ]
        if not fused:
            return []

        return self._rerank(query=query_text, candidates=fused)[: self._top_k]

    def _rerank(self, *, query: str, candidates: Sequence[HybridSearchResult]) -> list[HybridSearchResult]:
        primary_candidates = list(candidates[: self._primary_rerank_limit])
        try:
            return self._apply_rerank_scores(
                candidates=primary_candidates,
                scores=self._primary_reranker.rerank(
                    RerankRequest(
                        query=query,
                        documents=[candidate.payload.text for candidate in primary_candidates],
                        top_n=len(primary_candidates),
                    )
                ),
                provider_name=self._primary_reranker.provider_name,
            )
        except RemoteRerankError:
            pass

        if self._secondary_reranker is None:
            return list(candidates)

        secondary_candidates = list(candidates[: self._secondary_rerank_limit])
        try:
            return self._apply_rerank_scores(
                candidates=secondary_candidates,
                scores=self._secondary_reranker.rerank(
                    RerankRequest(
                        query=query,
                        documents=[candidate.payload.text for candidate in secondary_candidates],
                        top_n=len(secondary_candidates),
                    )
                ),
                provider_name=self._secondary_reranker.provider_name,
            )
        except RemoteRerankError:
            return list(candidates)

    @staticmethod
    def _apply_rerank_scores(
        *,
        candidates: Sequence[HybridSearchResult],
        scores: Sequence[RerankScore],
        provider_name: str,
    ) -> list[HybridSearchResult]:
        scored_results: list[HybridSearchResult] = []
        used_indexes: set[int] = set()

        for score in sorted(scores, key=lambda item: item.score, reverse=True):
            if score.index < 0 or score.index >= len(candidates) or score.index in used_indexes:
                continue
            used_indexes.add(score.index)
            scored_results.append(
                candidates[score.index].model_copy(
                    update={
                        "rerank_score": score.score,
                        "rerank_provider": provider_name,
                    }
                )
            )

        scored_results.extend(candidate for index, candidate in enumerate(candidates) if index not in used_indexes)
        return scored_results
