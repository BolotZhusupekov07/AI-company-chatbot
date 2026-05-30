from pydantic import BaseModel, ConfigDict, Field


class RerankScore(BaseModel):
    """A relevance score for one input document index."""

    model_config = ConfigDict(frozen=True)

    index: int = Field(ge=0)
    score: float


class RerankRequest(BaseModel):
    """Documents to rerank for one query."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    query: str = Field(min_length=1)
    documents: list[str] = Field(min_length=1)
    top_n: int = Field(ge=1, strict=True)
