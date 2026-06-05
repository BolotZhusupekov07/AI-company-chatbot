"""Chat answer orchestration service."""

from collections.abc import AsyncIterator, Sequence
from typing import Annotated

from fastapi import Depends
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart

from app.api.v1.chats.schemas import ChatMessage
from app.core.config import Settings, get_settings
from app.core.enums import Role
from app.services.chat_answer.agent import get_chat_agent, get_chat_streaming_agent
from app.services.chat_answer.bedrock.model import build_bedrock_converse_model_settings
from app.services.chat_answer.constants import CHAT_ANSWER_NOT_FOUND_MESSAGE
from app.services.chat_answer.dependencies import ChatAgentDeps, get_chat_agent_deps
from app.services.chat_answer.schemas import ChatAgentOutput, ChatAnswerStreamComplete, ChatAnswerStreamDelta


class ChatAnswerService:
    """Build chat answers from an LLM agent with retrieval tools."""

    def __init__(
        self,
        settings: Annotated[Settings, Depends(get_settings)],
        agent: Annotated[Agent[ChatAgentDeps, ChatAgentOutput], Depends(get_chat_agent)],
        streaming_agent: Annotated[Agent[ChatAgentDeps, str], Depends(get_chat_streaming_agent)],
    ) -> None:
        self._settings = settings
        self._agent = agent
        self._streaming_agent = streaming_agent

    async def answer(
        self,
        *,
        question: str,
        user_email: str,
        message_history: Sequence[ChatMessage],
    ) -> str:
        """Return an agent answer for the question."""

        result = await self._agent.run(
            question,
            deps=get_chat_agent_deps(user_email, self._settings),
            message_history=self._build_message_history(message_history),
            model_settings=build_bedrock_converse_model_settings(self._settings.CHAT_LLM_MAX_TOKENS),
        )
        answer = self._format_answer(result.output)
        return answer or CHAT_ANSWER_NOT_FOUND_MESSAGE

    async def stream_answer(
        self,
        *,
        question: str,
        user_email: str,
        message_history: Sequence[ChatMessage],
    ) -> AsyncIterator[ChatAnswerStreamDelta | ChatAnswerStreamComplete]:
        """Stream answer deltas from the chat agent and finish with the formatted answer."""

        answer_parts: list[str] = []

        async with self._streaming_agent.run_stream(
            question,
            deps=get_chat_agent_deps(user_email, self._settings),
            message_history=self._build_message_history(message_history),
            model_settings=build_bedrock_converse_model_settings(self._settings.CHAT_LLM_MAX_TOKENS),
        ) as result:
            async for delta in result.stream_text(delta=True, debounce_by=None):
                if delta:
                    answer_parts.append(delta)
                    yield ChatAnswerStreamDelta(delta=delta)

        answer = "".join(answer_parts).strip()
        yield ChatAnswerStreamComplete(answer=answer or CHAT_ANSWER_NOT_FOUND_MESSAGE)

    def _format_answer(self, output: ChatAgentOutput) -> str:
        answer = output.answer.strip()
        if not answer or answer == CHAT_ANSWER_NOT_FOUND_MESSAGE:
            return answer

        if not output.used_rag:
            return answer

        sources = list(dict.fromkeys(source.strip() for source in output.sources if source.strip()))
        if not sources:
            return answer
        return f"{answer}\n\nSources: {', '.join(sources)}"

    def _build_message_history(self, messages: Sequence[ChatMessage]) -> list[ModelMessage]:
        history: list[ModelMessage] = []
        for message in messages:
            if message.role == Role.USER:
                history.append(ModelRequest(parts=[UserPromptPart(content=message.content)]))
            elif message.role == Role.AGENT:
                history.append(ModelResponse(parts=[TextPart(content=message.content)]))
        return history
