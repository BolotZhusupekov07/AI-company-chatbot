"""Pydantic AI chat agent construction."""

from typing import Annotated

from fastapi import Depends
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.bedrock import BedrockConverseModel

from app.services.chat_answer.bedrock.model import get_chat_bedrock_model
from app.services.chat_answer.dependencies import ChatAgentDeps
from app.services.chat_answer.prompts import CHAT_AGENT_INSTRUCTIONS, CHAT_STREAMING_AGENT_INSTRUCTIONS
from app.services.chat_answer.schemas import ChatAgentOutput
from app.services.chat_answer.tools import (
    search_company_knowledge_tool,
    validate_citation_verified_output_tool,
)


def build_chat_agent(model: BedrockConverseModel) -> Agent[ChatAgentDeps, ChatAgentOutput]:
    """Build the chat answer agent."""

    agent = Agent[ChatAgentDeps, ChatAgentOutput](
        model=model,
        output_type=ChatAgentOutput,
        deps_type=ChatAgentDeps,
        instructions=CHAT_AGENT_INSTRUCTIONS,
    )

    @agent.tool
    async def search_company_knowledge(ctx: RunContext[ChatAgentDeps], query: str) -> str:
        """Search company knowledge for company-specific facts, policies, processes, access, or internal systems."""

        return await search_company_knowledge_tool(ctx.deps, query=query)

    @agent.output_validator
    def validate_output(ctx: RunContext[ChatAgentDeps], output: ChatAgentOutput) -> ChatAgentOutput:
        """Reject RAG answers that cite sources the search tool did not return."""

        return validate_citation_verified_output_tool(output, ctx.deps)

    return agent


def build_chat_streaming_agent(model: BedrockConverseModel) -> Agent[ChatAgentDeps, str]:
    """Build the plain-text streaming chat answer agent."""

    agent = Agent[ChatAgentDeps, str](
        model=model,
        output_type=str,
        deps_type=ChatAgentDeps,
        instructions=CHAT_STREAMING_AGENT_INSTRUCTIONS,
    )

    @agent.tool
    async def search_company_knowledge(ctx: RunContext[ChatAgentDeps], query: str) -> str:
        """Search company knowledge for company-specific facts, policies, processes, access, or internal systems."""

        return await search_company_knowledge_tool(ctx.deps, query=query)

    return agent


def get_chat_agent(
    model: Annotated[BedrockConverseModel, Depends(get_chat_bedrock_model)],
) -> Agent[ChatAgentDeps, ChatAgentOutput]:
    """Return the configured chat agent."""

    return build_chat_agent(model)


def get_chat_streaming_agent(
    model: Annotated[BedrockConverseModel, Depends(get_chat_bedrock_model)],
) -> Agent[ChatAgentDeps, str]:
    """Return the configured plain-text streaming chat agent."""

    return build_chat_streaming_agent(model)
