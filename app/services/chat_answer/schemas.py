"""Chat answer schemas."""

from pydantic import BaseModel, ConfigDict, Field


class ChatAgentOutput(BaseModel):
    """Structured output returned by the chat agent."""

    model_config = ConfigDict(frozen=True)

    answer: str = Field(min_length=1)
    used_rag: bool
    confidence: float = Field(ge=0.0, le=1.0)
    sources: list[str] = Field(default_factory=list)


class ChatAnswerStreamDelta(BaseModel):
    """A newly generated answer suffix from the chat agent stream."""

    model_config = ConfigDict(frozen=True)

    delta: str


class ChatAnswerStreamComplete(BaseModel):
    """Final formatted answer from the chat agent stream."""

    model_config = ConfigDict(frozen=True)

    answer: str
