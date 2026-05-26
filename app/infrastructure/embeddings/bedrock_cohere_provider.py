from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from typing import TYPE_CHECKING, Any, Literal

import boto3

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime import BedrockRuntimeClient

COHERE_EMBED_MULTILINGUAL_V3_MODEL_ID = "cohere.embed-multilingual-v3"
DEFAULT_MAX_TEXTS_PER_REQUEST = 96

CohereEmbedInputType = Literal["search_document", "search_query", "classification", "clustering"]
CohereEmbedTruncate = Literal["NONE", "START", "END"]


class BedrockCohereEmbeddingError(RuntimeError):
    """Raised when Bedrock returns an unexpected Cohere embedding response."""


class BedrockCohereEmbeddingProvider:
    """Embeds text with Cohere Embed Multilingual v3 through Amazon Bedrock Runtime."""

    def __init__(
        self,
        *,
        bedrock_runtime_client: BedrockRuntimeClient | None = None,
        region_name: str | None = None,
        model_id: str = COHERE_EMBED_MULTILINGUAL_V3_MODEL_ID,
        truncate: CohereEmbedTruncate = "NONE",
        max_texts_per_request: int = DEFAULT_MAX_TEXTS_PER_REQUEST,
    ) -> None:
        if truncate not in {"NONE", "START", "END"}:
            raise ValueError("truncate must be one of: NONE, START, END")
        if max_texts_per_request < 1 or max_texts_per_request > DEFAULT_MAX_TEXTS_PER_REQUEST:
            raise ValueError("max_texts_per_request must be between 1 and 96")

        self._client = bedrock_runtime_client or _build_bedrock_runtime_client(region_name)
        self.model_id = model_id
        self.truncate = truncate
        self.max_texts_per_request = max_texts_per_request

    def embed_chunks(self, chunk_texts: Sequence[str]) -> list[list[float]]:
        """Embed chunk text for storage and later vector search."""

        return self.embed_texts(chunk_texts, input_type="search_document")

    def embed_query(self, query_text: str) -> list[float]:
        """Embed a query for searching stored chunk vectors."""

        return self.embed_texts([query_text], input_type="search_query")[0]

    def embed_texts(self, texts: Sequence[str], *, input_type: CohereEmbedInputType) -> list[list[float]]:
        """Embed texts using a Cohere input type accepted by Bedrock."""

        text_batch = list(texts)
        if not text_batch:
            return []

        _validate_texts(text_batch)

        embeddings: list[list[float]] = []
        for batch in _batched(text_batch, self.max_texts_per_request):
            embeddings.extend(self._embed_batch(batch, input_type=input_type))

        return embeddings

    def _embed_batch(self, texts: Sequence[str], *, input_type: CohereEmbedInputType) -> list[list[float]]:
        request_body = json.dumps(
            {
                "texts": list(texts),
                "input_type": input_type,
                "truncate": self.truncate,
            },
        )
        response = self._client.invoke_model(
            body=request_body,
            modelId=self.model_id,
            accept="application/json",
            contentType="application/json",
        )
        response_body = _read_response_body(response)

        return _extract_float_embeddings(response_body, expected_count=len(texts))


def _build_bedrock_runtime_client(region_name: str | None) -> BedrockRuntimeClient:
    if region_name is None:
        return boto3.client("bedrock-runtime")

    return boto3.client("bedrock-runtime", region_name=region_name)


def _validate_texts(texts: Sequence[str]) -> None:
    for text in texts:
        if not isinstance(text, str):
            raise TypeError("texts must contain only strings")
        if not text.strip():
            raise ValueError("texts must not contain blank strings")


def _batched(texts: Sequence[str], batch_size: int) -> list[list[str]]:
    return [list(texts[index : index + batch_size]) for index in range(0, len(texts), batch_size)]


def _read_response_body(response: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        body = response["body"]
    except KeyError as error:
        raise BedrockCohereEmbeddingError("Bedrock response is missing body") from error

    raw_body = body.read() if hasattr(body, "read") else body

    try:
        parsed_body = json.loads(raw_body)
    except (TypeError, json.JSONDecodeError) as error:
        raise BedrockCohereEmbeddingError("Bedrock response body is not valid JSON") from error

    if not isinstance(parsed_body, Mapping):
        raise BedrockCohereEmbeddingError("Bedrock response body must be a JSON object")

    return parsed_body


def _extract_float_embeddings(response_body: Mapping[str, Any], *, expected_count: int) -> list[list[float]]:
    embeddings = response_body.get("embeddings")
    if not isinstance(embeddings, list):
        raise BedrockCohereEmbeddingError("Cohere response is missing embeddings list")
    if len(embeddings) != expected_count:
        raise BedrockCohereEmbeddingError("Cohere embeddings count does not match input text count")

    return [_coerce_float_vector(embedding) for embedding in embeddings]


def _coerce_float_vector(embedding: Any) -> list[float]:
    if not isinstance(embedding, list):
        raise BedrockCohereEmbeddingError("Each Cohere embedding must be a list")

    vector: list[float] = []
    for value in embedding:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise BedrockCohereEmbeddingError("Cohere embeddings must contain only numbers")
        vector.append(float(value))

    return vector
