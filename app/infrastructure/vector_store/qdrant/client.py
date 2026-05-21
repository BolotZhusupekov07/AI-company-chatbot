from qdrant_client import QdrantClient

from app.core.config import Settings, get_settings


def build_qdrant_client(settings: Settings | None = None) -> QdrantClient:
    """Build a Qdrant client from application settings."""

    resolved_settings = settings or get_settings()
    api_key = resolved_settings.QDRANT_API_KEY or None

    return QdrantClient(url=resolved_settings.QDRANT_URL, api_key=api_key)
