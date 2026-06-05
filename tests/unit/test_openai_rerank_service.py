"""OpenAI rerank service tests."""

from typing import Any

from pydantic import BaseModel
import pytest

from app.services.rerank.openai.prompts import OPENAI_RERANK_USER_PROMPT
from app.services.rerank.openai.schemas import OpenAIRerankOutput, OpenAIRerankResult
from app.services.rerank.openai.service import OpenAIRerankService
from app.services.rerank.schemas import RerankRequest


class FakeAgentResult(BaseModel):
    output: OpenAIRerankOutput


class FakeAgent:
    def __init__(self, output: OpenAIRerankOutput) -> None:
        self.output = output
        self.calls: list[dict[str, Any]] = []

    async def run(self, user_prompt: str, **kwargs: Any) -> FakeAgentResult:
        self.calls.append({"user_prompt": user_prompt, **kwargs})
        return FakeAgentResult(output=self.output)


@pytest.mark.asyncio
async def test_openai_rerank_service_uses_pydantic_ai_agent_structured_output() -> None:
    agent = FakeAgent(
        OpenAIRerankOutput(
            results=[
                OpenAIRerankResult(index=1, score=0.91),
                OpenAIRerankResult(index=0, score=0.2),
                OpenAIRerankResult(index=1, score=0.1),
            ]
        )
    )
    agent_dependency: Any = agent
    service = OpenAIRerankService(
        agent=agent_dependency,
        timeout_seconds=12.0,
    )

    scores = await service.rerank(
        RerankRequest(
            query="vpn access",
            documents=["Vacation policy", "VPN setup"],
            top_n=2,
        )
    )

    assert [(score.index, score.score) for score in scores] == [(1, 0.91), (0, 0.2)]
    call = agent.calls[0]
    assert call["user_prompt"] == OPENAI_RERANK_USER_PROMPT
    assert call["deps"] == RerankRequest(
        query="vpn access",
        documents=["Vacation policy", "VPN setup"],
        top_n=2,
    )
