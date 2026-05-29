"""Chat API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from fastapi_pagination import Page, Params
from pydantic import EmailStr

from app.api.v1.chats.schemas import (
    Chat,
    ChatListFilters,
    ChatListItem,
    ChatListSorting,
    ChatMessage,
    ChatMessageCreate,
    ChatMessageCreateRequest,
    ChatSummary,
    ChatUpdateRequest,
)
from app.core.enums import Role
from app.services.chat_service import ChatService

router = APIRouter(tags=["Chats"])


@router.get("/chats")
async def list_chats(
    filters: Annotated[ChatListFilters, Depends()],
    sorting: Annotated[ChatListSorting, Depends()],
    pagination_params: Annotated[Params, Depends()],
    service: Annotated[ChatService, Depends()],
) -> Page[ChatListItem]:
    """List chats."""

    return await service.list_chats(filters, sorting, pagination_params)


@router.get("/chats/{chat_id}")
async def get_chat(
    chat_id: UUID,
    service: Annotated[ChatService, Depends()],
    user_email: Annotated[EmailStr | None, Header(alias="X-User-Email", min_length=1)] = None,
) -> Chat:
    """Get a chat with messages."""

    return await service.get_chat(chat_id, user_email)


@router.patch("/chats/{chat_id}")
async def update_chat(
    chat_id: UUID,
    payload: ChatUpdateRequest,
    service: Annotated[ChatService, Depends()],
) -> ChatSummary:
    """Rename or pin/unpin a chat."""

    return await service.update_chat(chat_id, title=payload.title, is_pinned=payload.is_pinned)


@router.delete("/chats/{chat_id}", status_code=204)
async def delete_chat(
    chat_id: UUID,
    service: Annotated[ChatService, Depends()],
) -> None:
    """Soft-delete a chat."""

    await service.delete_chat(chat_id)


@router.post("/chats/messages", status_code=201)
async def create_chat_message(
    payload: ChatMessageCreateRequest,
    user_email: Annotated[EmailStr, Header(alias="X-User-Email", min_length=1)],
    service: Annotated[ChatService, Depends()],
) -> ChatMessage:
    """Create a user message, creating the chat first when needed."""

    if payload.chat_id:
        await service.ensure_chat_exists(payload.chat_id, user_email)
        chat_id = payload.chat_id
    else:
        chat_id = await service.create_chat(user_email)

    return await service.create_message(
        ChatMessageCreate(
            chat_id=chat_id,
            content=payload.content,
            role=Role.USER,
        )
    )
