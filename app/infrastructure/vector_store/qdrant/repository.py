from collections.abc import Mapping, Sequence
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from fastembed import SparseTextEmbedding
from qdrant_client import QdrantClient, models

from app.infrastructure.vector_store.qdrant.schemas import (
    QdrantChunkPayload,
    QdrantChunkSearchResult,
    QdrantHybridSearchRequest,
)
from app.knowledge.schemas import model as knowledge_model


class QdrantVectorRepository:
    """Stores and searches knowledge chunks in Qdrant."""

    def __init__(
        self,
        *,
        client: QdrantClient,
        collection_name: str,
        dense_vector_name: str,
        sparse_vector_name: str,
        sparse_model_id: str,
        bm25_language: str,
        dense_search_limit: int,
        sparse_search_limit: int,
        rrf_k: int,
        dense_score_threshold: float | None,
        sparse_embedding_model: SparseTextEmbedding | None = None,
    ) -> None:
        self._client = client
        self.collection_name = collection_name
        self._dense_vector_name = dense_vector_name
        self._sparse_vector_name = sparse_vector_name
        self._sparse_model_id = sparse_model_id
        self._bm25_language = bm25_language
        self._dense_search_limit = dense_search_limit
        self._sparse_search_limit = sparse_search_limit
        self._rrf_k = rrf_k
        self._dense_score_threshold = dense_score_threshold
        self._sparse_embedding_model = sparse_embedding_model

    def ensure_collection(self, *, vector_size: int, distance: models.Distance = models.Distance.COSINE) -> None:
        """Create the chunk collection when it does not already exist."""

        if self._client.collection_exists(collection_name=self.collection_name):
            return

        self._client.create_collection(
            collection_name=self.collection_name,
            vectors_config={
                self._dense_vector_name: models.VectorParams(size=vector_size, distance=distance),
            },
            sparse_vectors_config={
                self._sparse_vector_name: models.SparseVectorParams(
                    index=models.SparseIndexParams(on_disk=False),
                ),
            },
        )

    def upsert_chunks(
        self,
        chunks: Sequence[knowledge_model.KnowledgeChunk],
        vectors: Sequence[Sequence[float]],
        *,
        wait: bool = True,
    ) -> None:
        """Upsert chunk payloads and dense vectors."""

        normalized_vectors = [self._validate_vector(vector) for vector in vectors]
        vector_size = len(normalized_vectors[0])
        if any(len(vector) != vector_size for vector in normalized_vectors):
            raise ValueError("all vectors must have the same size")

        points = [
            models.PointStruct(
                id=self._point_id_from_chunk_id(chunk.chunk_id),
                vector={
                    self._dense_vector_name: vector,
                    self._sparse_vector_name: self._embed_sparse_document(chunk.content_markdown),
                },
                payload=self._payload_from_chunk(chunk).model_dump(mode="json"),
            )
            for chunk, vector in zip(chunks, normalized_vectors, strict=True)
        ]
        self._client.upsert(collection_name=self.collection_name, points=points, wait=wait)

    def search_hybrid(self, request: QdrantHybridSearchRequest) -> list[QdrantChunkSearchResult]:
        """Search chunks with Qdrant native dense/sparse prefetches and RRF fusion."""

        response = self._client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                models.Prefetch(
                    query=self._embed_sparse_query(request.query_text),
                    using=self._sparse_vector_name,
                    filter=request.sparse_filter,
                    limit=self._sparse_search_limit,
                ),
                models.Prefetch(
                    query=self._validate_vector(request.query_vector),
                    using=self._dense_vector_name,
                    filter=request.dense_filter,
                    score_threshold=self._dense_score_threshold,
                    limit=self._dense_search_limit,
                ),
            ],
            query=models.RrfQuery(rrf=models.Rrf(k=self._rrf_k)),
            limit=request.limit,
            with_payload=True,
            with_vectors=False,
        )

        return [
            QdrantChunkSearchResult(payload=self._payload_from_qdrant_item(point), score=float(point.score))
            for point in response.points
        ]

    def _embed_sparse_document(self, text: str) -> models.SparseVector:
        embedding = next(iter(self._get_sparse_embedding_model().embed([text])))
        return models.SparseVector(
            indices=embedding.indices.tolist(),
            values=embedding.values.tolist(),
        )

    def _embed_sparse_query(self, text: str) -> models.SparseVector:
        embedding = next(iter(self._get_sparse_embedding_model().query_embed(text)))
        return models.SparseVector(
            indices=embedding.indices.tolist(),
            values=embedding.values.tolist(),
        )

    def _get_sparse_embedding_model(self) -> SparseTextEmbedding:
        if self._sparse_embedding_model is None:
            self._sparse_embedding_model = SparseTextEmbedding(
                model_name=self._sparse_model_id,
                language=self._bm25_language,
            )

        return self._sparse_embedding_model

    def _validate_vector(self, vector: Sequence[float]) -> list[float]:
        if not vector:
            raise ValueError("vectors must not be empty")

        normalized: list[float] = []
        for value in vector:
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise TypeError("vectors must contain only numbers")
            normalized.append(float(value))

        return normalized

    def _payload_from_qdrant_item(self, item: Any) -> QdrantChunkPayload:
        payload = getattr(item, "payload", None)
        if not isinstance(payload, Mapping):
            raise ValueError("Qdrant item is missing payload")

        return QdrantChunkPayload.model_validate(payload)

    def _payload_from_chunk(self, chunk: knowledge_model.KnowledgeChunk) -> QdrantChunkPayload:
        """Build the Qdrant payload for a knowledge chunk."""

        return QdrantChunkPayload(
            chunk_id=chunk.chunk_id,
            source_id=chunk.source_id,
            document_group_id=chunk.document_group_id,
            language=chunk.language,
            space=chunk.space,
            allowed_users=chunk.allowed_users,
            allowed_groups=chunk.allowed_groups,
            text=chunk.content_markdown,
            chunk_index=chunk.chunk_index,
            character_count=chunk.character_count,
        )

    def _point_id_from_chunk_id(self, chunk_id: str) -> str:
        """Convert an arbitrary chunk ID into a deterministic Qdrant point UUID."""

        if not chunk_id.strip():
            raise ValueError("chunk_id must not be blank")

        return str(uuid5(NAMESPACE_URL, chunk_id))


def build_acl_filter(user_email: str, user_groups: Sequence[str]) -> models.Filter:
    email = user_email.strip().lower()
    groups = [group.strip() for group in user_groups if group.strip()]

    should_conditions: list[models.Condition] = [
        models.FieldCondition(
            key="allowed_users",
            match=models.MatchValue(value=email),
        )
    ]

    if groups:
        should_conditions.append(
            models.FieldCondition(
                key="allowed_groups",
                match=models.MatchAny(any=groups),
            )
        )

    return models.Filter(should=should_conditions)


def build_acl_language_filter(user_email: str, user_groups: Sequence[str], language: str) -> models.Filter:
    normalized_language = language.strip().lower()
    if not normalized_language:
        raise ValueError("language must not be blank")

    return models.Filter(
        must=[
            build_acl_filter(user_email, user_groups),
            models.FieldCondition(
                key="language",
                match=models.MatchValue(value=normalized_language),
            ),
        ]
    )
