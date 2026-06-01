from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.providers.openai import OpenAIProvider


def build_openai_rerank_model(*, api_key: str, model_id: str, base_url: str, timeout: float) -> OpenAIChatModel:
    """Build an OpenAI chat model for reranking."""

    return OpenAIChatModel(
        model_id,
        provider=OpenAIProvider(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
        ),
        settings=OpenAIChatModelSettings(
            temperature=0.0,
            timeout=timeout,
            openai_prompt_cache_key="openai_cache_key",
        ),
    )
