"""Chat orchestration service."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlalchemy import apaginate
from pydantic import TypeAdapter
from sqlalchemy import Select, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.chats.schemas import (
    Chat,
    ChatListFilters,
    ChatListItem,
    ChatListSorting,
    ChatMessage,
    ChatMessageCreate,
    ChatSummary,
)
from app.core.exceptions import NotFoundError
from app.infrastructure.db.database import get_session
from app.infrastructure.db.models.chat import ChatMessageModel, ChatModel


class ChatService:
    """Application service for chat persistence."""

    CHAT_LIST_ITEMS_ADAPTER: TypeAdapter[list[ChatListItem]] = TypeAdapter(list[ChatListItem])

    def __init__(self, session: Annotated[AsyncSession, Depends(get_session)]) -> None:
        self._session = session

    async def create_chat(self, user_email: str, title: str | None = None) -> UUID:
        """Create a chat and return its id."""

        query = (
            insert(ChatModel)
            .values(
                user_email=user_email,
                title=title if title else self._build_chat_title(),
            )
            .returning(ChatModel.id)
        )
        result = await self._session.execute(query)
        return result.scalar_one()

    async def create_message(self, schema: ChatMessageCreate) -> ChatMessage:
        """Create a chat message."""

        now = datetime.now(UTC)
        query = (
            insert(ChatMessageModel)
            .values(
                chat_id=schema.chat_id,
                content=schema.content,
                message_id=schema.message_id,
                role=schema.role,
                language=schema.language,
                processing_time_ms=0,
                created_at=now,
                updated_at=now,
            )
            .returning(ChatMessageModel)
        )
        message = await self._session.scalar(query)
        return ChatMessage.model_validate(message)

    async def get_chat(self, chat_id: UUID, user_email: str | None = None) -> Chat:
        """Get a chat by id."""

        chat = await self._get_chat_model(chat_id, user_email=user_email, with_messages=True)
        return Chat.model_validate(chat)

    async def list_chats(
        self,
        filters: ChatListFilters,
        sorting: ChatListSorting,
        pagination_params: Params,
    ) -> Page[ChatListItem]:
        """List chats with filters, sorting, and pagination."""

        query = select(ChatModel).where(ChatModel.deleted_at.is_(None))
        query = self._apply_filters(query, filters)
        query = query.order_by(ChatModel.is_pinned.desc())
        query = sorting.sort_query(query, ChatModel)
        return await apaginate(
            self._session,
            query,
            params=pagination_params,
            transformer=lambda chats: self.CHAT_LIST_ITEMS_ADAPTER.validate_python(chats),
        )

    def _apply_filters(self, query: Select, filters: ChatListFilters) -> Select:
        if filters.user_email is not None:
            query = query.where(ChatModel.user_email == filters.user_email)
        if filters.chat_ids is not None:
            query = query.where(ChatModel.id.in_(filters.chat_ids))
        if filters.created_from is not None:
            query = query.where(ChatModel.created_at >= filters.created_from)
        if filters.created_to is not None:
            query = query.where(ChatModel.created_at <= filters.created_to)
        return query

    async def update_chat(
        self,
        chat_id: UUID,
        *,
        title: str | None = None,
        is_pinned: bool | None = None,
    ) -> ChatSummary:
        """Update chat metadata."""

        chat = await self._get_chat_model(chat_id, with_messages=False)
        values = {}

        if title is not None:
            values["title"] = title

        if is_pinned is not None and chat.is_pinned != is_pinned:
            values["is_pinned"] = is_pinned

        if not values:
            return ChatSummary.model_validate(chat)

        result = await self._session.execute(
            update(ChatModel)
            .where(ChatModel.id == chat_id, ChatModel.deleted_at.is_(None))
            .values(**values)
            .returning(ChatModel)
        )
        updated_chat = result.scalar_one()
        return ChatSummary.model_validate(updated_chat)

    async def delete_chat(self, chat_id: UUID) -> None:
        """Soft-delete a chat."""

        query = (
            update(ChatModel)
            .where(ChatModel.id == chat_id, ChatModel.deleted_at.is_(None))
            .values(deleted_at=datetime.now(UTC))
            .returning(ChatModel.id)
        )
        result = await self._session.execute(query)
        if result.scalar_one_or_none() is None:
            raise NotFoundError(f"Chat(id={chat_id}) not found")

    async def ensure_chat_exists(self, chat_id: UUID, user_email: str | None = None) -> None:
        """Raise if the chat does not exist."""

        await self._get_chat_model(chat_id, user_email=user_email, with_messages=False)

    async def _get_chat_model(
        self,
        chat_id: UUID,
        user_email: str | None = None,
        *,
        with_messages: bool,
    ) -> ChatModel:
        where_args = [ChatModel.id == chat_id, ChatModel.deleted_at.is_(None)]
        if user_email is not None:
            where_args.append(ChatModel.user_email == user_email)

        query = select(ChatModel).where(*where_args)
        if with_messages:
            query = query.options(selectinload(ChatModel.messages))

        chat = await self._session.scalar(query)
        if chat is None:
            raise NotFoundError(f"Chat(id={chat_id}) not found")

        return chat

    @staticmethod
    def _build_chat_title() -> str:
        return datetime.now(UTC).strftime("%d-%m-%Y %H:%M")
