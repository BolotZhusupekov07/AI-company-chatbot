"""Bedrock LLM model wiring."""

from functools import lru_cache
from typing import Annotated

import boto3
from fastapi import Depends
from pydantic_ai.models.bedrock import BedrockConverseModel
from pydantic_ai.providers.bedrock import BedrockProvider

from app.core.config import Settings, get_settings


@lru_cache
def build_bedrock_converse_model(*, model_id: str, region_name: str) -> BedrockConverseModel:
    """Build a Pydantic AI Bedrock Converse model."""

    bedrock_client = boto3.client("bedrock-runtime", region_name=region_name)
    return BedrockConverseModel(
        model_name=model_id,
        provider=BedrockProvider(bedrock_client=bedrock_client),
    )


def get_chat_bedrock_model(settings: Annotated[Settings, Depends(get_settings)]) -> BedrockConverseModel:
    """Return the configured chat LLM model."""

    return build_bedrock_converse_model(
        model_id=settings.CHAT_LLM_MODEL_ID,
        region_name=settings.AWS_REGION_NAME,
    )
