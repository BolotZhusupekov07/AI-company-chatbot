"""Cohere rerank service through Amazon Bedrock."""

import asyncio
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.services.rerank.exceptions import RemoteRerankError
from app.services.rerank.interface import RemoteReranker
from app.services.rerank.schemas import RerankRequest, RerankScore

if TYPE_CHECKING:
    from mypy_boto3_bedrock_agent_runtime.client import AgentsforBedrockRuntimeClient
    from mypy_boto3_bedrock_agent_runtime.type_defs import (
        RerankingConfigurationTypeDef,
        RerankQueryTypeDef,
        RerankSourceTypeDef,
    )


class BedrockCohereRerankService(RemoteReranker):
    """Reranks documents with Cohere Rerank through Bedrock Agent Runtime."""

    provider_name = "bedrock-cohere"

    def __init__(
        self,
        *,
        bedrock_agent_runtime_client: AgentsforBedrockRuntimeClient | None = None,
        region_name: str,
        model_id: str,
    ) -> None:
        self._client = bedrock_agent_runtime_client or boto3.client("bedrock-agent-runtime", region_name=region_name)
        self.model_id = model_id
        self.model_arn = f"arn:aws:bedrock:{region_name}::foundation-model/{model_id}"

    async def rerank(self, request: RerankRequest) -> list[RerankScore]:
        """Return Cohere relevance scores in descending rank order."""

        queries: list[RerankQueryTypeDef] = [
            {
                "type": "TEXT",
                "textQuery": {"text": request.query},
            }
        ]
        sources: list[RerankSourceTypeDef] = [
            {
                "type": "INLINE",
                "inlineDocumentSource": {
                    "type": "TEXT",
                    "textDocument": {"text": document},
                },
            }
            for document in request.documents
        ]
        reranking_configuration: RerankingConfigurationTypeDef = {
            "type": "BEDROCK_RERANKING_MODEL",
            "bedrockRerankingConfiguration": {
                "modelConfiguration": {
                    "modelArn": self.model_arn,
                },
                "numberOfResults": min(request.top_n, len(request.documents)),
            },
        }

        try:
            response = await asyncio.to_thread(
                self._client.rerank,
                queries=queries,
                sources=sources,
                rerankingConfiguration=reranking_configuration,
            )
        except (BotoCoreError, ClientError) as error:
            raise RemoteRerankError("Bedrock Cohere rerank request failed") from error

        return self._extract_rerank_scores(response)

    @staticmethod
    def _extract_rerank_scores(response: Mapping[str, Any]) -> list[RerankScore]:
        results = response.get("results")
        if not isinstance(results, list):
            raise RemoteRerankError("Bedrock rerank response is missing results")

        scores: list[RerankScore] = []
        for result in results:
            scores.append(RerankScore(index=result.get("index"), score=float(result.get("relevanceScore"))))

        return scores
