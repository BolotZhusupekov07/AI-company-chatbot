from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field
from qdrant_client import models as qdrant_models


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


class QdrantChunkSearchResult(BaseModel):
    """Chunk payload returned from Qdrant with a search score."""

    model_config = ConfigDict(frozen=True)

    payload: QdrantChunkPayload
    score: float


class QdrantHybridSearchRequest(BaseModel):
    """Validated inputs for one Qdrant hybrid search."""

    model_config = ConfigDict(str_strip_whitespace=True)

    query_vector: Sequence[float]
    query_text: str = Field(min_length=1)
    limit: int = Field(ge=1, strict=True)
    dense_filter: qdrant_models.Filter | None = None
    sparse_filter: qdrant_models.Filter | None = None
