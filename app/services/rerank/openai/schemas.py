"""OpenAI rerank service schemas."""

from pydantic import BaseModel, ConfigDict, Field


class OpenAIRerankResult(BaseModel):
    """One OpenAI-generated rerank score."""

    model_config = ConfigDict(frozen=True)

    index: int = Field(ge=0)
    score: float = Field(ge=0.0, le=1.0)


class OpenAIRerankOutput(BaseModel):
    """Structured OpenAI rerank output."""

    model_config = ConfigDict(frozen=True)

    results: list[OpenAIRerankResult] = Field(default_factory=list)
