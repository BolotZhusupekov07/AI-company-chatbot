"""Chat API schemas."""

from datetime import UTC, datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    alias_generators,
    field_validator,
    model_validator,
)

from app.core.enums import Language, Role
from app.core.schemas import BaseListSorting

CHAT_TITLE_PATTERN = r"\A[\p{L}\p{N} [:punct:]]+\z"


class ChatMessageCreateRequest(BaseModel):
    """Request to create a user chat message."""

    chat_id: UUID | None = Field(None, description="Existing chat id")
    content: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
    ] = Field(
        description="User message content",
        examples=["What is our vacation policy?", "How do I access VPN?"],
    )

    model_config = ConfigDict(
        alias_generator=alias_generators.to_camel,
        validate_by_name=True,
    )


class ChatUpdateRequest(BaseModel):
    """Request to update chat metadata."""

    title: (
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, min_length=1, max_length=100, pattern=CHAT_TITLE_PATTERN),
        ]
        | None
    ) = Field(
        default=None,
        description="New chat title",
        examples=["Vacation policy"],
    )
    is_pinned: bool | None = Field(default=None, description="Whether chat is pinned")

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> Self:
        """Require at least one update field."""

        if self.title is None and self.is_pinned is None:
            raise ValueError("at least one of title or is_pinned must be provided")
        return self

    model_config = ConfigDict(
        alias_generator=alias_generators.to_camel,
        validate_by_name=True,
    )


class ChatMessageCreate(BaseModel):
    """Internal schema for message creation."""

    chat_id: UUID
    content: str
    role: Role
    message_id: UUID | None = None
    language: Language = Language.RU


class ChatMessage(BaseModel):
    """Chat message response."""

    id: UUID
    chat_id: UUID
    role: Role
    content: str
    language: Language
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=alias_generators.to_camel,
        validate_by_name=True,
    )


class ChatSummary(BaseModel):
    """Chat metadata response."""

    id: UUID
    title: str
    is_pinned: bool
    created_at: datetime
    updated_at: datetime
    user_email: EmailStr

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=alias_generators.to_camel,
        validate_by_name=True,
    )


class ChatListItem(ChatSummary):
    """Chat list item response."""


class ChatListFilters(BaseModel):
    """Chat list filter query parameters."""

    user_email: EmailStr | None = Field(default=None, description="Filter by user email")
    chat_ids: list[UUID] | None = Field(default=None, description="Filter by chat ids")
    created_from: datetime | None = Field(default=None, description="Filter by created at lower bound")
    created_to: datetime | None = Field(default=None, description="Filter by created at upper bound")

    @field_validator("created_from", "created_to")
    @classmethod
    def normalize_datetime_filter(cls, value: datetime | None) -> datetime | None:
        """Normalize timezone-aware datetime filters to UTC-naive values for DB comparisons."""

        if value is None or value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)

    @model_validator(mode="after")
    def validate_created_range(self) -> Self:
        """Validate that the created range is ordered."""

        if self.created_from and self.created_to and self.created_from > self.created_to:
            raise ValueError("created_from must be <= created_to")
        return self


class ChatListSorting(BaseListSorting):
    """Chat list sorting query parameters."""

    sort_by: Literal["created_at", "updated_at", "title"] = Field(
        default="updated_at",
        description="Sorting field",
    )


class Chat(ChatSummary):
    """Chat detail response."""

    messages: list[ChatMessage]
