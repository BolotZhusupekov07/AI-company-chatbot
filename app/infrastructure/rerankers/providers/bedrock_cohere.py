"""Cohere rerank provider through Amazon Bedrock."""

from collections.abc import Mapping
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.infrastructure.rerankers.exceptions import RemoteRerankError
from app.infrastructure.rerankers.interface import RemoteReranker
from app.infrastructure.rerankers.schemas import RerankRequest, RerankScore

COHERE_RERANK_3_5_MODEL_ID = "cohere.rerank-v3-5:0"


class BedrockCohereRerankProvider(RemoteReranker):
    """Reranks documents with Cohere Rerank 3.5 through Bedrock Agent Runtime."""

    provider_name = "bedrock-cohere"

    def __init__(
        self,
        *,
        bedrock_agent_runtime_client: Any | None = None,
        region_name: str,
        model_id: str = COHERE_RERANK_3_5_MODEL_ID,
    ) -> None:
        self._client = bedrock_agent_runtime_client or boto3.client("bedrock-agent-runtime", region_name=region_name)
        self.model_id = model_id
        self.model_arn = f"arn:aws:bedrock:{region_name}::foundation-model/{model_id}"

    def rerank(self, request: RerankRequest) -> list[RerankScore]:
        """Return Cohere relevance scores in descending rank order."""

        try:
            response = self._client.rerank(
                queries=[
                    {
                        "type": "TEXT",
                        "textQuery": {"text": request.query},
                    }
                ],
                sources=[
                    {
                        "type": "INLINE",
                        "inlineDocumentSource": {
                            "type": "TEXT",
                            "textDocument": {"text": document},
                        },
                    }
                    for document in request.documents
                ],
                rerankingConfiguration={
                    "type": "BEDROCK_RERANKING_MODEL",
                    "bedrockRerankingConfiguration": {
                        "modelConfiguration": {
                            "modelArn": self.model_arn,
                        },
                        "numberOfResults": min(request.top_n, len(request.documents)),
                    },
                },
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
