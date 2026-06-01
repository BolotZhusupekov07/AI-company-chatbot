"""Shared rerank service contract."""

from abc import ABC, abstractmethod

from app.services.rerank.schemas import RerankRequest, RerankScore


class RemoteReranker(ABC):
    """Small interface shared by remote reranker implementations."""

    provider_name: str

    @abstractmethod
    async def rerank(self, request: RerankRequest) -> list[RerankScore]:
        """Return relevance scores for input documents."""
