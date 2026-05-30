from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PATH = "./config/.env"


class Settings(BaseSettings):
    """Application settings."""

    PROJECT_NAME: str = "AI Chatbot Company"
    PROJECT_VERSION: str = "0.1.0"
    LOG_LEVEL: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"] = "INFO"
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DATABASE_URL: PostgresDsn = PostgresDsn("postgresql+psycopg://chatbot:chatbot@localhost:5433/ai_chatbot_company")

    AWS_REGION_NAME: str = "eu-west-1"
    QDRANT_URL: str = "http://localhost:6335"
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION_NAME: str = Field(default="company_knowledge_chunks", min_length=1)
    QDRANT_VECTOR_SIZE: int = Field(default=1024, ge=1)
    QDRANT_DENSE_VECTOR_NAME: str = Field(default="dense", min_length=1)
    QDRANT_SPARSE_VECTOR_NAME: str = Field(default="sparse", min_length=1)
    QDRANT_BM25_MODEL_ID: str = Field(default="Qdrant/bm25", min_length=1)
    QDRANT_BM25_LANGUAGE: str = Field(default="english", min_length=1)
    CHAT_LLM_MODEL_ID: str = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
    CHAT_LLM_MAX_TOKENS: int = 1024
    KNOWLEDGE_SOURCE_LANGUAGE: str = "en"

    HYBRID_DENSE_LIMIT: int = Field(default=20, ge=1)
    HYBRID_SPARSE_LIMIT: int = Field(default=20, ge=1)
    HYBRID_RRF_K: int = Field(default=60, ge=1)
    HYBRID_TOP_K: int = Field(default=3, ge=1)
    HYBRID_DENSE_SCORE_THRESHOLD: float | None = Field(default=0.3, ge=0.0)

    BEDROCK_RERANK_MODEL_ID: str = "cohere.rerank-v3-5:0"
    BEDROCK_RERANK_CANDIDATE_LIMIT: int = Field(default=20, ge=1)
    OPENAI_API_KEY: str | None = None
    OPENAI_API_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_RERANK_MODEL_ID: str = "gpt-4o-mini"
    OPENAI_RERANK_CANDIDATE_LIMIT: int = Field(default=8, ge=1)
    OPENAI_RERANK_TIMEOUT_SECONDS: float = Field(default=30.0, gt=0.0)

    model_config = SettingsConfigDict(env_file=ENV_PATH, extra="allow", frozen=True, str_strip_whitespace=True)


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()
