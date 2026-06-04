"""Chat API tests."""

from datetime import UTC, datetime, timedelta
import json
from typing import Any
from uuid import UUID, uuid4

from fastapi_pagination import Page
from httpx import AsyncClient
from pydantic import TypeAdapter
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.chats.schemas import ChatListItem, ChatMessageCreate
from app.core.enums import Language, Role
from app.infrastructure.db.models.chat import ChatModel
from app.services.chat_answer.constants import CHAT_ANSWER_NOT_FOUND_MESSAGE
from app.services.chat_service import ChatService
from tests.conftest import StubChatAnswerService


async def create_test_chat(
    session: AsyncSession,
    *,
    user_email: str,
    title: str,
    is_pinned: bool = False,
    created_at: datetime | None = None,
) -> ChatModel:
    """Create a chat directly for API tests."""

    timestamps: dict[str, datetime] = {}
    if created_at is not None:
        timestamps["created_at"] = created_at
        timestamps["updated_at"] = created_at

    result = await session.execute(
        insert(ChatModel)
        .values(
            user_email=user_email,
            title=title,
            is_pinned=is_pinned,
            **timestamps,
        )
        .returning(ChatModel)
    )
    return result.scalar_one()


class TestListChats:
    """GET /v1/chats."""

    CHAT_PAGE_ADAPTER: TypeAdapter[Page[ChatListItem]] = TypeAdapter(Page[ChatListItem])

    async def test_returns_paginated_chats_without_messages(
        self,
        session: AsyncSession,
        client: AsyncClient,
    ) -> None:
        service = ChatService(session)
        user_email = f"list-user-{uuid4()}@example.com"
        other_user_email = f"other-list-user-{uuid4()}@example.com"
        vacation_chat = await create_test_chat(session, user_email=user_email, title="Vacation days remaining")
        sick_leave_chat = await create_test_chat(session, user_email=user_email, title="Sick leave process")
        await create_test_chat(session, user_email=other_user_email, title="Other user chat")
        await service.create_message(
            ChatMessageCreate(
                chat_id=vacation_chat.id,
                content="How many vacation days do I have left?",
                role=Role.USER,
            )
        )

        response = await client.get(
            "/v1/chats",
            params={"user_email": user_email, "sort_by": "title", "sort_order": "asc"},
        )

        assert response.status_code == 200
        response_data = response.json()
        chats = self.CHAT_PAGE_ADAPTER.validate_python(response_data)
        assert [chat.id for chat in chats.items] == [sick_leave_chat.id, vacation_chat.id]
        assert response_data["total"] == 2
        assert response_data["page"] == 1
        assert response_data["size"] == 50
        assert [item["title"] for item in response_data["items"]] == ["Sick leave process", "Vacation days remaining"]
        assert all("messages" not in item for item in response_data["items"])

    async def test_filters_by_chat_ids_and_created_range(
        self,
        session: AsyncSession,
        client: AsyncClient,
    ) -> None:
        user_email = f"filtered-user-{uuid4()}@example.com"
        base_created_at = datetime(2026, 4, 14, 9, tzinfo=UTC)
        outside_range_chat = await create_test_chat(
            session,
            user_email=user_email,
            title="Outside range",
            created_at=base_created_at,
        )
        matching_chat = await create_test_chat(
            session,
            user_email=user_email,
            title="Matching chat",
            created_at=base_created_at + timedelta(days=1),
        )
        outside_ids_chat = await create_test_chat(
            session,
            user_email=user_email,
            title="Outside ids",
            created_at=base_created_at + timedelta(days=1, minutes=30),
        )

        response = await client.get(
            "/v1/chats",
            params=[
                ("chat_ids", str(outside_range_chat.id)),
                ("chat_ids", str(matching_chat.id)),
                ("created_from", (base_created_at + timedelta(days=1)).isoformat()),
                ("created_to", (base_created_at + timedelta(days=1, minutes=15)).isoformat()),
            ],
        )

        assert response.status_code == 200
        response_data = response.json()
        assert [item["id"] for item in response_data["items"]] == [str(matching_chat.id)]
        assert response_data["total"] == 1
        assert outside_ids_chat.id != matching_chat.id


class TestGetChat:
    """GET /v1/chats/{chat_id}."""

    async def test_returns_chat_with_messages(
        self,
        session: AsyncSession,
        client: AsyncClient,
    ) -> None:
        service = ChatService(session)
        user_email = f"existing-user-{uuid4()}@example.com"
        chat_id = await service.create_chat(user_email, title="Vacation policy")
        message = await service.create_message(
            ChatMessageCreate(
                chat_id=chat_id,
                content="What is our vacation policy?",
                role=Role.USER,
            )
        )

        response = await client.get(f"/v1/chats/{chat_id}")

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["id"] == str(chat_id)
        assert response_data["title"] == "Vacation policy"
        assert response_data["userEmail"] == user_email
        assert response_data["messages"] == [
            {
                "id": str(message.id),
                "chatId": str(chat_id),
                "role": Role.USER,
                "content": "What is our vacation policy?",
                "language": Language.RU,
                "createdAt": response_data["messages"][0]["createdAt"],
                "updatedAt": response_data["messages"][0]["updatedAt"],
            }
        ]

    async def test_returns_not_found_when_chat_id_does_not_exist(self, client: AsyncClient) -> None:
        chat_id = uuid4()

        response = await client.get(f"/v1/chats/{chat_id}")

        assert response.status_code == 404
        assert response.json() == {"detail": f"Chat(id={chat_id}) not found"}


class TestUpdateChat:
    """PATCH /v1/chats/{chat_id}."""

    async def test_renames_chat_title(
        self,
        session: AsyncSession,
        client: AsyncClient,
    ) -> None:
        service = ChatService(session)
        user_email = f"existing-user-{uuid4()}@example.com"
        chat_id = await service.create_chat(user_email, title="Old title")

        response = await client.patch(f"/v1/chats/{chat_id}", json={"title": "  Updated title  "})

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["id"] == str(chat_id)
        assert response_data["title"] == "Updated title"
        assert response_data["isPinned"] is False
        assert response_data["userEmail"] == user_email

    async def test_rejects_empty_update_payload(
        self,
        session: AsyncSession,
        client: AsyncClient,
    ) -> None:
        service = ChatService(session)
        chat_id = await service.create_chat(f"existing-user-{uuid4()}@example.com", title="Original title")

        response = await client.patch(f"/v1/chats/{chat_id}", json={})

        assert response.status_code == 422


class TestDeleteChat:
    """DELETE /v1/chats/{chat_id}."""

    async def test_deletes_chat_by_id(
        self,
        session: AsyncSession,
        client: AsyncClient,
    ) -> None:
        service = ChatService(session)
        user_email = f"existing-user-{uuid4()}@example.com"
        chat_id = await service.create_chat(user_email, title="Chat to delete")

        response = await client.delete(f"/v1/chats/{chat_id}")

        assert response.status_code == 204
        assert response.content == b""
        get_response = await client.get(f"/v1/chats/{chat_id}")
        assert get_response.status_code == 404
        assert get_response.json() == {"detail": f"Chat(id={chat_id}) not found"}


class TestCreateChatMessage:
    """POST /v1/chats/messages."""

    async def test_creates_chat_user_message_and_agent_answer_when_chat_id_is_not_provided(
        self,
        session: AsyncSession,
        client: AsyncClient,
        answer_service: StubChatAnswerService,
    ) -> None:
        user_email = f"new-user-{uuid4()}@example.com"
        answer_service.response = "Employees receive 20 paid vacation days per year."

        response = await client.post(
            "/v1/chats/messages",
            headers={"X-User-Email": user_email},
            json={"content": "What is our vacation policy?"},
        )

        assert response.status_code == 201
        response_data = response.json()
        message_id = UUID(response_data["id"])
        chat_id = UUID(response_data["chatId"])
        assert response_data == {
            "id": str(message_id),
            "chatId": str(chat_id),
            "role": Role.AGENT,
            "content": "Employees receive 20 paid vacation days per year.",
            "language": Language.RU,
            "createdAt": response_data["createdAt"],
            "updatedAt": response_data["updatedAt"],
        }

        service = ChatService(session)
        chat = await service.get_chat(chat_id)
        assert chat.user_email == user_email
        assert [message.role for message in chat.messages] == [Role.USER, Role.AGENT]
        assert chat.messages[0].content == "What is our vacation policy?"
        assert chat.messages[1].id == message_id
        assert chat.messages[1].content == "Employees receive 20 paid vacation days per year."
        assert answer_service.calls == [
            {
                "question": "What is our vacation policy?",
                "user_email": user_email,
                "message_history": [],
            }
        ]

    async def test_adds_user_message_and_agent_answer_to_existing_chat(
        self,
        session: AsyncSession,
        client: AsyncClient,
        answer_service: StubChatAnswerService,
    ) -> None:
        service = ChatService(session)
        user_email = f"existing-user-{uuid4()}@example.com"
        chat_id = await service.create_chat(user_email)
        previous_user_message = await service.create_message(
            ChatMessageCreate(
                chat_id=chat_id,
                content="Earlier question",
                role=Role.USER,
            )
        )
        previous_agent_message = await service.create_message(
            ChatMessageCreate(
                chat_id=chat_id,
                content="Earlier answer",
                role=Role.AGENT,
                message_id=previous_user_message.id,
            )
        )
        answer_service.response = "Sick leave starts by notifying your manager."

        response = await client.post(
            "/v1/chats/messages",
            headers={"X-User-Email": user_email},
            json={"chatId": str(chat_id), "content": "Tell me about sick leave."},
        )

        assert response.status_code == 201
        response_data = response.json()
        assert response_data["chatId"] == str(chat_id)
        assert response_data["role"] == Role.AGENT
        assert response_data["content"] == "Sick leave starts by notifying your manager."

        chats_count = await session.scalar(select(func.count()).select_from(ChatModel).where(ChatModel.id == chat_id))
        assert chats_count == 1
        assert answer_service.calls[0]["message_history"] == [
            previous_user_message,
            previous_agent_message,
        ]

    async def test_returns_not_found_when_existing_chat_belongs_to_another_user(
        self,
        session: AsyncSession,
        client: AsyncClient,
    ) -> None:
        service = ChatService(session)
        chat_id = await service.create_chat(f"owner-{uuid4()}@example.com")

        response = await client.post(
            "/v1/chats/messages",
            headers={"X-User-Email": f"other-{uuid4()}@example.com"},
            json={"chatId": str(chat_id), "content": "Tell me about sick leave."},
        )

        assert response.status_code == 404
        assert response.json() == {"detail": f"Chat(id={chat_id}) not found"}

    async def test_returns_fallback_agent_message_when_answer_is_not_found(
        self,
        session: AsyncSession,
        client: AsyncClient,
        answer_service: StubChatAnswerService,
    ) -> None:
        user_email = f"fallback-user-{uuid4()}@example.com"
        answer_service.response = CHAT_ANSWER_NOT_FOUND_MESSAGE

        response = await client.post(
            "/v1/chats/messages",
            headers={"X-User-Email": user_email},
            json={"content": "Unknown policy question."},
        )

        assert response.status_code == 201
        response_data = response.json()
        chat_id = UUID(response_data["chatId"])
        assert response_data["role"] == Role.AGENT
        assert response_data["content"] == CHAT_ANSWER_NOT_FOUND_MESSAGE

        service = ChatService(session)
        chat = await service.get_chat(chat_id)
        assert [message.role for message in chat.messages] == [Role.USER, Role.AGENT]
        assert chat.messages[1].content == CHAT_ANSWER_NOT_FOUND_MESSAGE


class TestStreamChatMessage:
    """POST /v1/chats/messages/stream."""

    async def test_streams_new_chat_answer_and_persists_messages(
        self,
        session: AsyncSession,
        client: AsyncClient,
        answer_service: StubChatAnswerService,
    ) -> None:
        user_email = f"stream-user-{uuid4()}@example.com"
        answer_service.stream_chunks = ["Use ", "the VPN guide."]
        answer_service.response = "Use the VPN guide."

        response = await client.post(
            "/v1/chats/messages/stream",
            headers={"X-User-Email": user_email, "Accept": "text/event-stream"},
            json={"content": "How do I access VPN?"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = _parse_sse_events(response.text)
        assert [event_name for event_name, _payload in events] == ["message", "message", "done"]
        assert events[0][1] == {"chatId": events[0][1]["chatId"], "delta": "Use "}
        assert events[1][1] == {"chatId": events[0][1]["chatId"], "delta": "the VPN guide."}
        assert events[2][1]["message"]["content"] == "Use the VPN guide."

        chat_id = UUID(events[2][1]["chatId"])
        service = ChatService(session)
        chat = await service.get_chat(chat_id)
        assert [message.role for message in chat.messages] == [Role.USER, Role.AGENT]
        assert chat.messages[0].content == "How do I access VPN?"
        assert chat.messages[1].content == "Use the VPN guide."
        assert answer_service.calls == [
            {
                "question": "How do I access VPN?",
                "user_email": user_email,
                "message_history": [],
            }
        ]

    async def test_streams_existing_chat_answer_with_history(
        self,
        session: AsyncSession,
        client: AsyncClient,
        answer_service: StubChatAnswerService,
    ) -> None:
        service = ChatService(session)
        user_email = f"existing-stream-user-{uuid4()}@example.com"
        chat_id = await service.create_chat(user_email)
        previous_user_message = await service.create_message(
            ChatMessageCreate(chat_id=chat_id, content="Earlier question", role=Role.USER)
        )
        previous_agent_message = await service.create_message(
            ChatMessageCreate(
                chat_id=chat_id,
                content="Earlier answer",
                role=Role.AGENT,
                message_id=previous_user_message.id,
            )
        )
        answer_service.stream_chunks = ["Follow-up"]
        answer_service.response = "Follow-up"

        response = await client.post(
            "/v1/chats/messages/stream",
            headers={"X-User-Email": user_email, "Accept": "text/event-stream"},
            json={"chatId": str(chat_id), "content": "Tell me more."},
        )

        assert response.status_code == 200
        events = _parse_sse_events(response.text)
        assert events[0][1] == {"chatId": str(chat_id), "delta": "Follow-up"}
        assert answer_service.calls[0]["message_history"] == [
            previous_user_message,
            previous_agent_message,
        ]

    async def test_stream_returns_not_found_when_existing_chat_belongs_to_another_user(
        self,
        session: AsyncSession,
        client: AsyncClient,
    ) -> None:
        service = ChatService(session)
        chat_id = await service.create_chat(f"owner-{uuid4()}@example.com")

        response = await client.post(
            "/v1/chats/messages/stream",
            headers={"X-User-Email": f"other-{uuid4()}@example.com", "Accept": "text/event-stream"},
            json={"chatId": str(chat_id), "content": "Tell me about sick leave."},
        )

        assert response.status_code == 404
        assert response.json() == {"detail": f"Chat(id={chat_id}) not found"}


def _parse_sse_events(body: str) -> list[tuple[str, dict[str, Any]]]:
    events = []
    for frame in body.strip().split("\n\n"):
        lines = frame.split("\n")
        event_name = next(line.removeprefix("event: ") for line in lines if line.startswith("event: "))
        data = next(line.removeprefix("data: ") for line in lines if line.startswith("data: "))
        events.append((event_name, json.loads(data)))
    return events
