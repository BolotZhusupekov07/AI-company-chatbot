"""OpenAI rerank service."""

from pydantic_ai import Agent

from app.services.rerank.exceptions import RemoteRerankError
from app.services.rerank.interface import RemoteReranker
from app.services.rerank.openai.agent import build_openai_rerank_agent
from app.services.rerank.openai.model import build_openai_rerank_model
from app.services.rerank.openai.prompts import OPENAI_RERANK_USER_PROMPT
from app.services.rerank.openai.schemas import OpenAIRerankOutput
from app.services.rerank.schemas import RerankRequest, RerankScore


class OpenAIRerankService(RemoteReranker):
    """Reranks documents using a Pydantic AI OpenAI agent."""

    provider_name = "openai"

    def __init__(
        self,
        *,
        agent: Agent[RerankRequest, OpenAIRerankOutput],
        timeout_seconds: float,
    ) -> None:
        self._agent = agent
        self.timeout_seconds = timeout_seconds

    @classmethod
    def build(
        cls,
        *,
        api_key: str,
        model_id: str,
        base_url: str,
        timeout_seconds: float,
    ) -> "OpenAIRerankService":
        """Build the OpenAI rerank service with its agent."""

        model = build_openai_rerank_model(
            api_key=api_key, model_id=model_id, base_url=base_url, timeout=timeout_seconds
        )
        return cls(
            agent=build_openai_rerank_agent(model),
            timeout_seconds=timeout_seconds,
        )

    async def rerank(self, request: RerankRequest) -> list[RerankScore]:
        """Return model-generated relevance scores for the supplied documents."""

        try:
            result = await self._agent.run(
                OPENAI_RERANK_USER_PROMPT,
                deps=request,
            )
        except Exception as error:
            raise RemoteRerankError("OpenAI rerank request failed") from error

        return self._extract_rerank_scores(result.output, top_n=min(request.top_n, len(request.documents)))

    @staticmethod
    def _extract_rerank_scores(output: OpenAIRerankOutput, *, top_n: int) -> list[RerankScore]:
        scores: list[RerankScore] = []
        used_indexes: set[int] = set()

        for result in output.results:
            if result.index in used_indexes:
                continue
            used_indexes.add(result.index)
            scores.append(RerankScore(index=result.index, score=result.score))
            if len(scores) == top_n:
                break

        return scores


def build_openai_rerank_service(
    *,
    api_key: str,
    model_id: str,
    base_url: str,
    timeout_seconds: float,
) -> OpenAIRerankService:
    """Build the configured OpenAI rerank service."""

    return OpenAIRerankService.build(
        api_key=api_key,
        model_id=model_id,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
    )
