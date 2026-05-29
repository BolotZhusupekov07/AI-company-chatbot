"""Pydantic AI chat agent construction."""

from typing import Annotated

from fastapi import Depends
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.bedrock import BedrockConverseModel

from app.infrastructure.llms.bedrock import get_chat_bedrock_model
from app.services.chat_answer.dependencies import ChatAgentDeps
from app.services.chat_answer.prompts import CHAT_AGENT_INSTRUCTIONS
from app.services.chat_answer.tools import search_company_knowledge_tool


def build_chat_agent(model: BedrockConverseModel) -> Agent[ChatAgentDeps, str]:
    """Build the chat answer agent."""

    agent = Agent(
        model=model,
        output_type=str,
        deps_type=ChatAgentDeps,
        instructions=CHAT_AGENT_INSTRUCTIONS,
    )

    @agent.tool
    def search_company_knowledge(ctx: RunContext[ChatAgentDeps], query: str) -> str:
        """Search company knowledge and return the first matching chunk text."""

        return search_company_knowledge_tool(ctx.deps, query=query)

    return agent


def get_chat_agent(
    model: Annotated[BedrockConverseModel, Depends(get_chat_bedrock_model)],
) -> Agent[ChatAgentDeps, str]:
    """Return the configured chat agent."""

    return build_chat_agent(model)
