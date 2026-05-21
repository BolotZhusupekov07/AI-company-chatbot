from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PATH = "./config/.env"


class Settings(BaseSettings):
    """Application settings."""

    PROJECT_NAME: str = "AI Chatbot Company"
    PROJECT_VERSION: str = "0.1.0"
    LOG_LEVEL: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"] = "INFO"
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    AWS_REGION_NAME: str = "eu-west-1"
    QDRANT_URL: str = "http://localhost:6335"
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION_NAME: str = "company_knowledge_chunks"

    model_config = SettingsConfigDict(env_file=ENV_PATH, extra="allow", frozen=True)


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()
