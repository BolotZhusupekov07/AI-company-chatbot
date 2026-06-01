"""Pydantic AI OpenAI rerank agent construction."""

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel

from app.services.rerank.openai.prompts import OPENAI_RERANK_INSTRUCTIONS
from app.services.rerank.openai.schemas import OpenAIRerankOutput
from app.services.rerank.schemas import RerankRequest


def build_openai_rerank_agent(model: OpenAIChatModel) -> Agent[RerankRequest, OpenAIRerankOutput]:
    """Build the OpenAI rerank agent."""

    agent = Agent[RerankRequest, OpenAIRerankOutput](
        model=model,
        output_type=OpenAIRerankOutput,
        deps_type=RerankRequest,
        instructions=OPENAI_RERANK_INSTRUCTIONS,
    )

    @agent.instructions
    def add_rerank_context(ctx: RunContext[RerankRequest]) -> str:
        """Add the query and candidate documents to the model context."""

        top_n = min(ctx.deps.top_n, len(ctx.deps.documents))
        documents = "\n\n".join(
            f"Document index: {index}\nText:\n{document}" for index, document in enumerate(ctx.deps.documents)
        )
        return f"Query:\n{ctx.deps.query}\n\nTop N: {top_n}\n\nDocuments:\n{documents}"

    return agent
