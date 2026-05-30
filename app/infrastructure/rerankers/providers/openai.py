"""OpenAI fallback rerank provider."""

from collections.abc import Mapping
import json
from typing import Any

import httpx

from app.infrastructure.rerankers.exceptions import RemoteRerankError
from app.infrastructure.rerankers.interface import RemoteReranker
from app.infrastructure.rerankers.schemas import RerankRequest, RerankScore


class OpenAIRerankProvider(RemoteReranker):
    """Reranks documents by asking an OpenAI model for structured relevance scores."""

    provider_name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model_id: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 30.0,
    ) -> None:
        if not api_key.strip():
            raise ValueError("api_key must not be blank")

        self._api_key = api_key
        self.model_id = model_id
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def rerank(self, request: RerankRequest) -> list[RerankScore]:
        """Return model-generated relevance scores for the supplied documents."""

        request_body = {
            "model": self.model_id,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "You rerank search results. Return JSON with one score per input document. "
                        "Scores are relevance values from 0 to 1. Include each input index at most once."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "query": request.query,
                            "documents": [
                                {
                                    "index": index,
                                    "text": document,
                                }
                                for index, document in enumerate(request.documents)
                            ],
                            "top_n": min(request.top_n, len(request.documents)),
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "temperature": 0,
            "max_output_tokens": 1200,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "rerank_response",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "results": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "index": {"type": "integer"},
                                        "score": {"type": "number"},
                                    },
                                    "required": ["index", "score"],
                                    "additionalProperties": False,
                                },
                            }
                        },
                        "required": ["results"],
                        "additionalProperties": False,
                    },
                }
            },
        }

        try:
            response = httpx.post(
                f"{self.base_url}/responses",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=request_body,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise RemoteRerankError("OpenAI rerank request failed") from error

        return self._extract_rerank_scores(response.json(), top_n=min(request.top_n, len(request.documents)))

    def _extract_rerank_scores(self, response_body: Mapping[str, Any], *, top_n: int) -> list[RerankScore]:
        output_text = self._extract_output_text(response_body)

        try:
            parsed_output = json.loads(output_text)
        except json.JSONDecodeError as error:
            raise RemoteRerankError("OpenAI rerank response is not valid JSON") from error

        results = parsed_output.get("results")

        scores: list[RerankScore] = []
        for result in results[:top_n]:
            index = result.get("index")
            score = result.get("score")
            scores.append(RerankScore(index=index, score=max(0.0, min(1.0, float(score)))))

        return scores

    def _extract_output_text(self, response_body: Mapping[str, Any]) -> str:
        output_text = response_body.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text

        text_parts: list[str] = []
        output_items = response_body.get("output")
        if isinstance(output_items, list):
            for output_item in output_items:
                if not isinstance(output_item, Mapping):
                    continue
                content_items = output_item.get("content")
                if not isinstance(content_items, list):
                    continue
                for content_item in content_items:
                    if not isinstance(content_item, Mapping):
                        continue
                    text = content_item.get("text")
                    if isinstance(text, str):
                        text_parts.append(text)

        combined_text = "".join(text_parts).strip()
        if not combined_text:
            raise RemoteRerankError("OpenAI rerank response is missing output text")

        return combined_text
