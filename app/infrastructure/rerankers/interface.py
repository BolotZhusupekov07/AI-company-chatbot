"""Shared reranker models."""

from abc import ABC, abstractmethod

from app.infrastructure.rerankers.schemas import RerankRequest, RerankScore


class RemoteReranker(ABC):
    """Small interface shared by remote reranker providers."""

    provider_name: str

    @abstractmethod
    def rerank(self, request: RerankRequest) -> list[RerankScore]:
        """Return relevance scores for input documents."""
