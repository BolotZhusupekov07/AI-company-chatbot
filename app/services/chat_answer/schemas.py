"""Chat answer schemas."""

from pydantic import BaseModel, ConfigDict, Field


class ChatAgentOutput(BaseModel):
    """Structured output returned by the chat agent."""

    model_config = ConfigDict(frozen=True)

    answer: str = Field(min_length=1)
    used_rag: bool
    confidence: float = Field(ge=0.0, le=1.0)
