import type {
  Chat,
  ChatListItem,
  ChatMessage,
  CreateChatMessageInput,
  Page,
  UpdateChatInput,
} from "../types";

const API_BASE_PATH = "/v1";

export class ChatApiError extends Error {
  readonly status: number;
  readonly details: unknown;

  constructor(message: string, status: number, details: unknown) {
    super(message);
    this.name = "ChatApiError";
    this.status = status;
    this.details = details;
  }
}

export async function listChats(userEmail: string): Promise<Page<ChatListItem>> {
  const query = new URLSearchParams({
    user_email: userEmail,
    sort_by: "updated_at",
    sort_order: "desc",
    size: "50",
  });

  return requestJson<Page<ChatListItem>>(`/chats?${query.toString()}`, {
    headers: acceptJsonHeaders(),
  });
}

export async function getChat(chatId: string, userEmail: string): Promise<Chat> {
  return requestJson<Chat>(`/chats/${encodeURIComponent(chatId)}`, {
    headers: acceptJsonHeaders({ "X-User-Email": userEmail }),
  });
}

export async function createChatMessage(input: CreateChatMessageInput): Promise<ChatMessage> {
  const body = input.chatId ? { chatId: input.chatId, content: input.content } : { content: input.content };

  return requestJson<ChatMessage>("/chats/messages", {
    method: "POST",
    headers: jsonHeaders({ "X-User-Email": input.userEmail }),
    body: JSON.stringify(body),
  });
}

export async function updateChat(chatId: string, input: UpdateChatInput): Promise<ChatListItem> {
  return requestJson<ChatListItem>(`/chats/${encodeURIComponent(chatId)}`, {
    method: "PATCH",
    headers: jsonHeaders(),
    body: JSON.stringify(input),
  });
}

export async function deleteChat(chatId: string): Promise<void> {
  await requestJson<void>(`/chats/${encodeURIComponent(chatId)}`, {
    method: "DELETE",
    headers: acceptJsonHeaders(),
  });
}

async function requestJson<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_PATH}${path}`, init);

  if (!response.ok) {
    const details = await parseResponseBody(response);
    throw new ChatApiError(readErrorMessage(details, response.statusText), response.status, details);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

function acceptJsonHeaders(extraHeaders: Record<string, string> = {}): Record<string, string> {
  return {
    Accept: "application/json",
    ...extraHeaders,
  };
}

function jsonHeaders(extraHeaders: Record<string, string> = {}): Record<string, string> {
  return {
    ...acceptJsonHeaders(extraHeaders),
    "Content-Type": "application/json",
  };
}

async function parseResponseBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get("Content-Type") ?? "";
  if (!contentType.includes("application/json")) {
    return response.statusText;
  }
  return response.json();
}

function readErrorMessage(details: unknown, fallback: string): string {
  if (typeof details === "object" && details !== null && "detail" in details) {
    const detail = (details as { detail: unknown }).detail;
    if (typeof detail === "string" && detail.trim().length > 0) {
      return detail;
    }
  }
  return fallback || "Request failed";
}
