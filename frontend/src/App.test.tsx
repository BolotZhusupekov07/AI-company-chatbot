import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import * as chatApi from "./api/chatApi";
import type { Chat, ChatListItem, ChatMessage, Page } from "./types";

vi.mock("./api/chatApi");

const mockedChatApi = vi.mocked(chatApi);

describe("App", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.resetAllMocks();
  });

  it("loads chats for the default user and opens the newest pinned chat", async () => {
    mockedChatApi.listChats.mockResolvedValue(pageOfChats([vacationChat(), vpnChat({ isPinned: true })]));
    mockedChatApi.getChat.mockResolvedValue(chatDetail(vpnChat({ isPinned: true }), [agentMessage("VPN answer")]));

    render(<App />);

    expect(await screen.findByDisplayValue("aida@example.com")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "VPN access" })).toBeInTheDocument();
    expect(await screen.findByText("VPN answer")).toBeInTheDocument();
    expect(mockedChatApi.listChats).toHaveBeenCalledWith("aida@example.com");
    expect(mockedChatApi.getChat).toHaveBeenCalledWith("chat-vpn", "aida@example.com");
  });

  it("applies a changed user email and reloads chats", async () => {
    const user = userEvent.setup();
    mockedChatApi.listChats.mockResolvedValueOnce(pageOfChats([])).mockResolvedValueOnce(pageOfChats([vpnChat()]));
    mockedChatApi.getChat.mockResolvedValue(chatDetail(vpnChat(), []));

    render(<App />);

    const emailInput = await screen.findByLabelText("User email");
    await user.clear(emailInput);
    await user.type(emailInput, "mira@example.com");
    await user.click(screen.getByRole("button", { name: "Apply user email" }));

    await waitFor(() => expect(mockedChatApi.listChats).toHaveBeenLastCalledWith("mira@example.com"));
    expect(window.localStorage.getItem("chat-web-app:user-email")).toBe("mira@example.com");
  });

  it("sends the first message for a new chat", async () => {
    const user = userEvent.setup();
    mockedChatApi.listChats.mockResolvedValue(pageOfChats([]));
    mockedChatApi.streamChatMessage.mockImplementation(async (_input, handlers) => {
      handlers.onDelta({ chatId: "chat-new", delta: "Use " });
      handlers.onDelta({ chatId: "chat-new", delta: "the VPN guide." });
      handlers.onDone({ chatId: "chat-new", message: agentMessage("Use the VPN guide.", "chat-new") });
    });
    mockedChatApi.getChat.mockResolvedValue(
      chatDetail(vpnChat({ id: "chat-new" }), [agentMessage("Use the VPN guide.", "chat-new")]),
    );

    render(<App />);

    await user.click(await screen.findByRole("button", { name: "New chat" }));
    await user.type(screen.getByLabelText("Message"), "How do I access VPN?");
    await user.click(screen.getByRole("button", { name: "Send message" }));

    await waitFor(() =>
      expect(mockedChatApi.streamChatMessage).toHaveBeenCalledWith(
        {
          content: "How do I access VPN?",
          userEmail: "aida@example.com",
        },
        expect.objectContaining({
          onDelta: expect.any(Function),
          onDone: expect.any(Function),
        }),
      ),
    );
    expect(await screen.findByText("Use the VPN guide.")).toBeInTheDocument();
  });

  it("sends a follow-up message to the selected chat", async () => {
    const user = userEvent.setup();
    mockedChatApi.listChats.mockResolvedValue(pageOfChats([vpnChat()]));
    mockedChatApi.getChat
      .mockResolvedValueOnce(chatDetail(vpnChat(), [agentMessage("Existing answer")]))
      .mockResolvedValueOnce(
        chatDetail(vpnChat(), [agentMessage("Existing answer"), agentMessage("Follow-up answer")]),
      );
    mockedChatApi.streamChatMessage.mockImplementation(async (_input, handlers) => {
      handlers.onDelta({ chatId: "chat-vpn", delta: "Follow-up answer" });
      handlers.onDone({ chatId: "chat-vpn", message: agentMessage("Follow-up answer") });
    });

    render(<App />);

    await screen.findByText("Existing answer");
    await user.type(screen.getByLabelText("Message"), "Tell me more.");
    await user.click(screen.getByRole("button", { name: "Send message" }));

    await waitFor(() =>
      expect(mockedChatApi.streamChatMessage).toHaveBeenCalledWith(
        {
          chatId: "chat-vpn",
          content: "Tell me more.",
          userEmail: "aida@example.com",
        },
        expect.objectContaining({
          onDelta: expect.any(Function),
          onDone: expect.any(Function),
        }),
      ),
    );
  });

  it("renders API errors without losing the draft message", async () => {
    const user = userEvent.setup();
    mockedChatApi.listChats.mockResolvedValue(pageOfChats([]));
    mockedChatApi.streamChatMessage.mockRejectedValue(new Error("Model unavailable"));

    render(<App />);

    await user.type(await screen.findByLabelText("Message"), "How do I access VPN?");
    await user.click(screen.getByRole("button", { name: "Send message" }));

    expect(await screen.findByText("Model unavailable")).toBeInTheDocument();
    expect(screen.getByLabelText("Message")).toHaveValue("How do I access VPN?");
  });
});

function pageOfChats(items: ChatListItem[]): Page<ChatListItem> {
  return { items, page: 1, size: 50, total: items.length, pages: items.length > 0 ? 1 : 0 };
}

function vacationChat(): ChatListItem {
  return {
    id: "chat-vacation",
    title: "Vacation policy",
    isPinned: false,
    createdAt: "2026-06-04T08:00:00",
    updatedAt: "2026-06-04T08:00:00",
    userEmail: "aida@example.com",
  };
}

function vpnChat(overrides: Partial<ChatListItem> = {}): ChatListItem {
  return {
    id: "chat-vpn",
    title: "VPN access",
    isPinned: false,
    createdAt: "2026-06-04T08:00:00",
    updatedAt: "2026-06-04T09:00:00",
    userEmail: "aida@example.com",
    ...overrides,
  };
}

function chatDetail(summary: ChatListItem, messages: ChatMessage[]): Chat {
  return { ...summary, messages };
}

function agentMessage(content: string, chatId = "chat-vpn"): ChatMessage {
  return {
    id: `message-${content}`,
    chatId,
    role: "AGENT",
    content,
    language: "RU",
    createdAt: "2026-06-04T09:01:00",
    updatedAt: "2026-06-04T09:01:00",
  };
}
