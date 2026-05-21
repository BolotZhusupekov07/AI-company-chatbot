from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, Field
from qdrant_client import QdrantClient, models

from app.core.config import Settings, get_settings
from app.knowledge.schemas import model as knowledge_model


class QdrantChunkPayload(BaseModel):
    """Payload stored with each knowledge chunk point."""

    chunk_id: str
    source_id: str
    document_group_id: str
    language: str
    space: str
    allowed_users: list[str] = Field(default_factory=list)
    allowed_groups: list[str] = Field(default_factory=list)
    text: str
    chunk_index: int
    character_count: int


@dataclass(frozen=True)
class QdrantChunkSearchResult:
    """Chunk payload returned from Qdrant with the dense-search score."""

    payload: QdrantChunkPayload
    score: float


class QdrantVectorRepository:
    """Stores and searches knowledge chunks in Qdrant."""

    def __init__(self, *, client: QdrantClient, collection_name: str) -> None:
        self._client = client
        self.collection_name = collection_name

    def ensure_collection(self, *, vector_size: int, distance: models.Distance = models.Distance.COSINE) -> None:
        """Create the chunk collection when it does not already exist."""

        if vector_size < 1:
            raise ValueError("vector_size must be greater than zero")

        if self._client.collection_exists(collection_name=self.collection_name):
            return

        self._client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(size=vector_size, distance=distance),
        )

    def upsert_chunks(
        self,
        chunks: Sequence[knowledge_model.KnowledgeChunk],
        vectors: Sequence[Sequence[float]],
        *,
        wait: bool = True,
    ) -> None:
        """Upsert chunk payloads and dense vectors."""

        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        if not chunks:
            return

        normalized_vectors = [_validate_vector(vector) for vector in vectors]
        vector_size = len(normalized_vectors[0])
        if any(len(vector) != vector_size for vector in normalized_vectors):
            raise ValueError("all vectors must have the same size")

        points = [
            models.PointStruct(
                id=point_id_from_chunk_id(chunk.chunk_id),
                vector=vector,
                payload=payload_from_chunk(chunk).model_dump(mode="json"),
            )
            for chunk, vector in zip(chunks, normalized_vectors, strict=True)
        ]
        self._client.upsert(collection_name=self.collection_name, points=points, wait=wait)

    def search_dense(
        self,
        query_vector: Sequence[float],
        *,
        limit: int = 10,
        query_filter: models.Filter | None = None,
        score_threshold: float | None = None,
    ) -> list[QdrantChunkSearchResult]:
        """Search chunks by dense vector similarity."""

        if limit < 1:
            raise ValueError("limit must be greater than zero")

        response = self._client.query_points(
            collection_name=self.collection_name,
            query=_validate_vector(query_vector),
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
            score_threshold=score_threshold,
        )

        return [
            QdrantChunkSearchResult(payload=_payload_from_qdrant_item(point), score=float(point.score))
            for point in response.points
        ]


def payload_from_chunk(chunk: knowledge_model.KnowledgeChunk) -> QdrantChunkPayload:
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


def point_id_from_chunk_id(chunk_id: str) -> str:
    """Convert an arbitrary chunk ID into a deterministic Qdrant point UUID."""

    if not chunk_id.strip():
        raise ValueError("chunk_id must not be blank")

    return str(uuid5(NAMESPACE_URL, f"ai-chatbot-company:knowledge-chunk:{chunk_id}"))


def _validate_vector(vector: Sequence[float]) -> list[float]:
    if not vector:
        raise ValueError("vectors must not be empty")

    normalized: list[float] = []
    for value in vector:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise TypeError("vectors must contain only numbers")
        normalized.append(float(value))

    return normalized


def _payload_from_qdrant_item(item: Any) -> QdrantChunkPayload:
    payload = getattr(item, "payload", None)
    if not isinstance(payload, Mapping):
        raise ValueError("Qdrant item is missing payload")

    return QdrantChunkPayload.model_validate(payload)


def build_acl_filter(user_email: str, user_groups: Sequence[str]) -> models.Filter:
    email = user_email.strip().lower()
    groups = [group.strip() for group in user_groups if group.strip()]

    should_conditions = [
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
