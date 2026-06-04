import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createChatMessage, deleteChat, getChat, listChats, streamChatMessage, updateChat } from "./chatApi";

const fetchMock = vi.fn();

describe("chatApi", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("lists chats for a user through the local API proxy", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ items: [], page: 1, size: 50, total: 0, pages: 0 }));

    await listChats("aida@example.com");

    expect(fetchMock).toHaveBeenCalledWith(
      "/v1/chats?user_email=aida%40example.com&sort_by=updated_at&sort_order=desc&size=50",
      {
        headers: { Accept: "application/json" },
      },
    );
  });

  it("loads chat detail with the user email header", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ id: "chat-1", messages: [] }));

    await getChat("chat-1", "aida@example.com");

    expect(fetchMock).toHaveBeenCalledWith("/v1/chats/chat-1", {
      headers: { Accept: "application/json", "X-User-Email": "aida@example.com" },
    });
  });

  it("sends a first message without chatId", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ id: "message-1", chatId: "chat-1" }));

    await createChatMessage({ content: "How do I access VPN?", userEmail: "aida@example.com" });

    expect(fetchMock).toHaveBeenCalledWith("/v1/chats/messages", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-User-Email": "aida@example.com",
      },
      body: JSON.stringify({ content: "How do I access VPN?" }),
    });
  });

  it("sends a follow-up message with chatId", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ id: "message-2", chatId: "chat-1" }));

    await createChatMessage({ chatId: "chat-1", content: "Tell me more.", userEmail: "aida@example.com" });

    expect(fetchMock).toHaveBeenCalledWith("/v1/chats/messages", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-User-Email": "aida@example.com",
      },
      body: JSON.stringify({ chatId: "chat-1", content: "Tell me more." }),
    });
  });

  it("streams a chat message through the local API proxy", async () => {
    fetchMock.mockResolvedValueOnce(
      streamResponse([
        'event: message\ndata: {"chatId":"chat-1","delta":"Use "}\n\n',
        'event: done\ndata: {"chatId":"chat-1","message":{"id":"message-1","chatId":"chat-1","role":"AGENT","content":"Use VPN.","language":"RU","createdAt":"2026-06-04T09:01:00","updatedAt":"2026-06-04T09:01:00"}}\n\n',
      ]),
    );
    const onDelta = vi.fn();
    const onDone = vi.fn();

    await streamChatMessage(
      { content: "How do I access VPN?", userEmail: "aida@example.com" },
      { onDelta, onDone },
    );

    expect(fetchMock).toHaveBeenCalledWith("/v1/chats/messages/stream", {
      method: "POST",
      headers: {
        Accept: "text/event-stream",
        "Content-Type": "application/json",
        "X-User-Email": "aida@example.com",
      },
      body: JSON.stringify({ content: "How do I access VPN?" }),
    });
    expect(onDelta).toHaveBeenCalledWith({ chatId: "chat-1", delta: "Use " });
    expect(onDone).toHaveBeenCalledWith(
      expect.objectContaining({
        chatId: "chat-1",
        message: expect.objectContaining({ content: "Use VPN." }),
      }),
    );
  });

  it("parses SSE events split across response chunks", async () => {
    fetchMock.mockResolvedValueOnce(
      streamResponse([
        'event: message\ndata: {"chatId":"chat-1","delta":"Hel',
        'lo"}\n\n',
        'event: done\ndata: {"chatId":"chat-1","message":{"id":"message-1","chatId":"chat-1","role":"AGENT","content":"Hello","language":"RU","createdAt":"2026-06-04T09:01:00","updatedAt":"2026-06-04T09:01:00"}}\n\n',
      ]),
    );
    const onDelta = vi.fn();

    await streamChatMessage(
      { chatId: "chat-1", content: "Hi", userEmail: "aida@example.com" },
      { onDelta, onDone: vi.fn() },
    );

    expect(onDelta).toHaveBeenCalledWith({ chatId: "chat-1", delta: "Hello" });
  });

  it("updates only the changed chat fields", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ id: "chat-1", title: "VPN access", isPinned: true }));

    await updateChat("chat-1", { isPinned: true });

    expect(fetchMock).toHaveBeenCalledWith("/v1/chats/chat-1", {
      method: "PATCH",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ isPinned: true }),
    });
  });

  it("deletes a chat", async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));

    await deleteChat("chat-1");

    expect(fetchMock).toHaveBeenCalledWith("/v1/chats/chat-1", {
      method: "DELETE",
      headers: { Accept: "application/json" },
    });
  });

  it("turns non-2xx responses into ChatApiError", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Chat(id=chat-1) not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(getChat("chat-1", "aida@example.com")).rejects.toMatchObject({
      message: "Chat(id=chat-1) not found",
      status: 404,
    });
  });
});

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function streamResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  return new Response(
    new ReadableStream({
      start(controller) {
        for (const chunk of chunks) {
          controller.enqueue(encoder.encode(chunk));
        }
        controller.close();
      },
    }),
    {
      status: 200,
      headers: { "Content-Type": "text/event-stream" },
    },
  );
}
