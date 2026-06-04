import type { ChatListItem, ChatMessage } from "../types";

export function sortChats(chats: ChatListItem[]): ChatListItem[] {
  return [...chats].sort((left, right) => {
    if (left.isPinned !== right.isPinned) {
      return left.isPinned ? -1 : 1;
    }
    return new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime();
  });
}

export function formatTimestamp(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function getMessageAuthor(message: ChatMessage): string {
  return message.role === "USER" ? "You" : "Assistant";
}
