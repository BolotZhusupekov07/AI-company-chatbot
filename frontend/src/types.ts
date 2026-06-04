export type ChatRole = "USER" | "AGENT";
export type ChatLanguage = "EN" | "RU" | "UK";

export interface Page<T> {
  items: T[];
  page: number;
  size: number;
  total: number;
  pages: number;
}

export interface ChatSummary {
  id: string;
  title: string;
  isPinned: boolean;
  createdAt: string;
  updatedAt: string;
  userEmail: string;
}

export type ChatListItem = ChatSummary;

export interface ChatMessage {
  id: string;
  chatId: string;
  role: ChatRole;
  content: string;
  language: ChatLanguage;
  createdAt: string;
  updatedAt: string;
}

export interface Chat extends ChatSummary {
  messages: ChatMessage[];
}

export interface CreateChatMessageInput {
  chatId?: string;
  content: string;
  userEmail: string;
}

export interface UpdateChatInput {
  title?: string;
  isPinned?: boolean;
}
