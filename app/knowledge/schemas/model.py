from pathlib import Path

from pydantic import BaseModel, Field


class SourceDocument(BaseModel):
    """Normalized source document loaded from a knowledge source."""

    source_id: str
    title: str
    document_group_id: str
    language: str
    space: str
    content_markdown: str
    allowed_users: list[str] = Field(default_factory=list)
    allowed_groups: list[str] = Field(default_factory=list)
    version: int = 1
    updated_at: str | None = None
    content_hash: str
    path: Path


class KnowledgeChunk(BaseModel):
    """Markdown chunk derived from a source document."""

    chunk_id: str
    source_id: str
    document_group_id: str
    language: str
    space: str
    content_markdown: str
    chunk_index: int
    character_count: int
    content_hash: str
    allowed_users: list[str] = Field(default_factory=list)
    allowed_groups: list[str] = Field(default_factory=list)
