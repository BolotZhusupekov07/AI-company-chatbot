"""Chat API routes."""

from collections.abc import AsyncIterator
import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from fastapi_pagination import Page, Params
from pydantic import BaseModel, EmailStr
from starlette.responses import StreamingResponse

from app.api.v1.chats.schemas import (
    Chat,
    ChatListFilters,
    ChatListItem,
    ChatListSorting,
    ChatMessage,
    ChatMessageCreate,
    ChatMessageCreateRequest,
    ChatMessageStreamDelta,
    ChatMessageStreamDone,
    ChatMessageStreamError,
    ChatSummary,
    ChatUpdateRequest,
)
from app.core.enums import Role
from app.services.chat_answer.schemas import ChatAnswerStreamComplete, ChatAnswerStreamDelta
from app.services.chat_answer.service import ChatAnswerService
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
    answer_service: Annotated[ChatAnswerService, Depends()],
) -> ChatMessage:
    """Create a user message and return the retrieved answer message."""

    if payload.chat_id:
        chat = await service.get_chat(payload.chat_id, user_email)
        chat_id = payload.chat_id
        message_history = chat.messages
    else:
        chat_id = await service.create_chat(user_email)
        message_history = []

    user_message = await service.create_message(
        ChatMessageCreate(chat_id=chat_id, content=payload.content, role=Role.USER)
    )

    answer = await answer_service.answer(
        question=payload.content,
        user_email=user_email,
        message_history=message_history,
    )
    return await service.create_message(
        ChatMessageCreate(chat_id=chat_id, content=answer, role=Role.AGENT, message_id=user_message.id)
    )


@router.post("/chats/messages/stream")
async def stream_chat_message(
    payload: ChatMessageCreateRequest,
    user_email: Annotated[EmailStr, Header(alias="X-User-Email", min_length=1)],
    service: Annotated[ChatService, Depends()],
    answer_service: Annotated[ChatAnswerService, Depends()],
) -> StreamingResponse:
    """Create a user message and stream the retrieved answer message."""

    if payload.chat_id:
        chat = await service.get_chat(payload.chat_id, user_email)
        chat_id = payload.chat_id
        message_history = chat.messages
    else:
        chat_id = await service.create_chat(user_email)
        message_history = []

    user_message = await service.create_message(
        ChatMessageCreate(chat_id=chat_id, content=payload.content, role=Role.USER)
    )

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for event in answer_service.stream_answer(
                question=payload.content,
                user_email=user_email,
                message_history=message_history,
            ):
                if isinstance(event, ChatAnswerStreamDelta):
                    yield _sse_event(
                        "message",
                        ChatMessageStreamDelta(chat_id=chat_id, delta=event.delta),
                    )
                    continue

                if isinstance(event, ChatAnswerStreamComplete):
                    answer_message = await service.create_message(
                        ChatMessageCreate(
                            chat_id=chat_id,
                            content=event.answer,
                            role=Role.AGENT,
                            message_id=user_message.id,
                        )
                    )
                    yield _sse_event(
                        "done",
                        ChatMessageStreamDone(chat_id=chat_id, message=answer_message),
                    )
                    return
        except Exception as exc:
            yield _sse_event("error", ChatMessageStreamError(detail=str(exc) or "Answer generation failed."))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse_event(
    event: str,
    payload: BaseModel,
) -> str:
    data = json.dumps(payload.model_dump(mode="json", by_alias=True), separators=(",", ":"))
    return f"event: {event}\ndata: {data}\n\n"
