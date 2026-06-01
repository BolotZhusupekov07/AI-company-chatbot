from hashlib import sha256
from typing import Any, cast

from fastembed import SparseTextEmbedding
from pydantic import ValidationError
import pytest
from qdrant_client import QdrantClient, models

from app.infrastructure.vector_store.qdrant.repository import (
    QdrantVectorRepository,
    build_acl_filter,
    build_acl_language_filter,
)
from app.infrastructure.vector_store.qdrant.schemas import QdrantHybridSearchRequest
from app.knowledge.schemas import model as knowledge_model

DENSE_VECTOR_NAME = "test-dense"
SPARSE_VECTOR_NAME = "test-sparse"


def test_ensure_collection_creates_dense_and_sparse_vectors() -> None:
    class FakeQdrantClient:
        def __init__(self) -> None:
            self.created_collection: dict[str, Any] | None = None

        def collection_exists(self, *, collection_name: str) -> bool:
            return False

        def create_collection(self, **kwargs: Any) -> None:
            self.created_collection = kwargs

    client = FakeQdrantClient()
    repository = _repository(client)

    repository.ensure_collection(vector_size=1024)

    assert client.created_collection is not None
    assert client.created_collection["collection_name"] == "chunks"
    assert client.created_collection["vectors_config"][DENSE_VECTOR_NAME].size == 1024
    sparse_config = client.created_collection["sparse_vectors_config"][SPARSE_VECTOR_NAME]
    assert sparse_config.index.on_disk is False


def test_upsert_chunks_stores_dense_vector_and_explicit_sparse_vector() -> None:
    class FakeQdrantClient:
        def __init__(self) -> None:
            self.upsert_call: dict[str, Any] | None = None

        def upsert(self, **kwargs: Any) -> None:
            self.upsert_call = kwargs

    client = FakeQdrantClient()
    repository = _repository(client, sparse_embedding_model=cast(SparseTextEmbedding, FakeSparseEmbeddingModel()))
    chunk = _knowledge_chunk("hr/vpn.en.md:chunk:0001", "# VPN\n\nUse SAML.")

    repository.upsert_chunks([chunk], [[0.1, 0.2]])

    assert client.upsert_call is not None
    point = client.upsert_call["points"][0]
    assert point.vector[DENSE_VECTOR_NAME] == [0.1, 0.2]
    sparse_vector = point.vector[SPARSE_VECTOR_NAME]
    assert sparse_vector.indices == [11, 22]
    assert sparse_vector.values == [1.5, 2.5]
    assert point.payload["chunk_id"] == "hr/vpn.en.md:chunk:0001"


def test_search_hybrid_uses_qdrant_prefetches_and_rrf() -> None:
    class FakeQdrantClient:
        def __init__(self) -> None:
            self.query_points_call: dict[str, Any] | None = None

        def query_points(self, **kwargs: Any) -> Any:
            self.query_points_call = kwargs
            return FakeQueryResponse(
                [
                    FakePoint(
                        payload={
                            "chunk_id": "hr/vpn.en.md:chunk:0001",
                            "source_id": "hr/vpn.en.md",
                            "document_group_id": "vpn",
                            "language": "en",
                            "space": "hr",
                            "allowed_users": [],
                            "allowed_groups": ["employees"],
                            "text": "# VPN\n\nUse SAML.",
                            "chunk_index": 0,
                            "character_count": 17,
                        },
                        score=0.04,
                    )
                ]
            )

    client = FakeQdrantClient()
    repository = _repository(client, sparse_embedding_model=cast(SparseTextEmbedding, FakeSparseEmbeddingModel()))
    dense_filter = build_acl_filter("aida@example.com", ["employees"])
    sparse_filter = build_acl_language_filter("aida@example.com", ["employees"], "en")

    results = repository.search_hybrid(
        QdrantHybridSearchRequest(
            query_vector=[0.1, 0.2],
            query_text="SAML VPN",
            limit=3,
            dense_filter=dense_filter,
            sparse_filter=sparse_filter,
        )
    )

    assert [result.payload.chunk_id for result in results] == ["hr/vpn.en.md:chunk:0001"]
    assert results[0].score == 0.04
    assert client.query_points_call is not None
    call = client.query_points_call
    assert call["collection_name"] == "chunks"
    assert call["limit"] == 3
    assert call["with_payload"] is True
    assert call["with_vectors"] is False
    assert isinstance(call["query"], models.RrfQuery)
    assert call["query"].rrf.k == 60

    sparse_prefetch, dense_prefetch = call["prefetch"]
    assert sparse_prefetch.using == SPARSE_VECTOR_NAME
    assert sparse_prefetch.limit == 5
    assert sparse_prefetch.filter is sparse_filter
    assert sparse_prefetch.query.indices == [33, 44]
    assert sparse_prefetch.query.values == [3.5, 4.5]

    assert dense_prefetch.using == DENSE_VECTOR_NAME
    assert dense_prefetch.limit == 7
    assert dense_prefetch.filter is dense_filter
    assert dense_prefetch.score_threshold == 0.5
    assert dense_prefetch.query == [0.1, 0.2]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"query_text": " ", "limit": 1},
        {"query_text": "SAML VPN", "limit": 0},
    ],
)
def test_search_hybrid_validates_request_with_pydantic(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        QdrantHybridSearchRequest(query_vector=[0.1], **kwargs)


def test_build_acl_language_filter_requires_acl_and_language() -> None:
    query_filter = build_acl_language_filter("AIDA@example.com", ["employees"], "en")
    filter_dump = query_filter.model_dump(mode="json")

    assert filter_dump["must"][0]["should"][0]["match"]["value"] == "aida@example.com"
    assert filter_dump["must"][1]["key"] == "language"
    assert filter_dump["must"][1]["match"]["value"] == "en"


def _knowledge_chunk(chunk_id: str, text: str) -> knowledge_model.KnowledgeChunk:
    return knowledge_model.KnowledgeChunk(
        chunk_id=chunk_id,
        source_id="hr/vpn.en.md",
        document_group_id="vpn",
        language="en",
        space="hr",
        content_markdown=text,
        chunk_index=0,
        character_count=len(text),
        content_hash=sha256(text.encode("utf-8")).hexdigest(),
        allowed_users=[],
        allowed_groups=["employees"],
    )


def _repository(
    client: Any,
    *,
    sparse_embedding_model: SparseTextEmbedding | None = None,
) -> QdrantVectorRepository:
    return QdrantVectorRepository(
        client=cast(QdrantClient, client),
        collection_name="chunks",
        dense_vector_name=DENSE_VECTOR_NAME,
        sparse_vector_name=SPARSE_VECTOR_NAME,
        sparse_model_id="Qdrant/bm25",
        bm25_language="english",
        dense_search_limit=7,
        sparse_search_limit=5,
        rrf_k=60,
        dense_score_threshold=0.5,
        sparse_embedding_model=sparse_embedding_model,
    )


class FakeSparseEmbeddingModel:
    def embed(self, documents: list[str]) -> Any:
        assert documents == ["# VPN\n\nUse SAML."]
        return iter([FakeSparseEmbedding(indices=[11, 22], values=[1.5, 2.5])])

    def query_embed(self, query: str) -> Any:
        assert query == "SAML VPN"
        return iter([FakeSparseEmbedding(indices=[33, 44], values=[3.5, 4.5])])


class FakeSparseArray(list[Any]):
    def tolist(self) -> list[Any]:
        return list(self)


class FakeSparseEmbedding:
    def __init__(self, *, indices: list[int], values: list[float]) -> None:
        self.indices = FakeSparseArray(indices)
        self.values = FakeSparseArray(values)


class FakeQueryResponse:
    def __init__(self, points: list[Any]) -> None:
        self.points = points


class FakePoint:
    def __init__(self, *, payload: dict[str, Any], score: float) -> None:
        self.payload = payload
        self.score = score
