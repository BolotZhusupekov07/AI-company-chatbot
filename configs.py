from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PATH = "./config/.env"


class MainConfig(BaseSettings):
    """Main application configuration."""

    MODE: Literal["HTTP"] = "HTTP"

    model_config = SettingsConfigDict(env_file=ENV_PATH, extra="allow")


class HttpConfig(BaseSettings):
    """HTTP server configuration."""

    HOST: str = "127.0.0.1"
    PORT: int = 8000

    model_config = SettingsConfigDict(env_file=ENV_PATH, extra="allow")


main_config = MainConfig()
