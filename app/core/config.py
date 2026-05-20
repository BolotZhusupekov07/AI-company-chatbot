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

    model_config = SettingsConfigDict(env_file=ENV_PATH, extra="allow", frozen=True)


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()
