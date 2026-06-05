import { MessageSquarePlus, Pin, PinOff, Trash2 } from "lucide-react";
import type { FormEvent } from "react";

import type { ChatListItem } from "../types";
import { formatTimestamp } from "../utils/chatFormat";

interface SidebarProps {
  chats: ChatListItem[];
  emailDraft: string;
  selectedChatId: string | null;
  isLoadingChats: boolean;
  onEmailDraftChange: (value: string) => void;
  onApplyEmail: () => void;
  onNewChat: () => void;
  onSelectChat: (chatId: string) => void;
  onTogglePin: (chat: ChatListItem) => void;
  onDeleteChat: (chat: ChatListItem) => void;
}

export function Sidebar({
  chats,
  emailDraft,
  selectedChatId,
  isLoadingChats,
  onEmailDraftChange,
  onApplyEmail,
  onNewChat,
  onSelectChat,
  onTogglePin,
  onDeleteChat,
}: SidebarProps) {
  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    onApplyEmail();
  }

  return (
    <aside className="sidebar" aria-label="Chat history">
      <div className="sidebar-header">
        <div>
          <p className="eyebrow">Company knowledge</p>
          <h1>Company Assistant</h1>
        </div>
        <button
          className="icon-button primary-action"
          type="button"
          onClick={onNewChat}
          title="New chat"
          aria-label="New chat"
        >
          <MessageSquarePlus aria-hidden="true" size={18} />
        </button>
      </div>

      <form className="email-form" onSubmit={handleSubmit}>
        <label htmlFor="user-email">User email</label>
        <div className="email-row">
          <input
            id="user-email"
            value={emailDraft}
            onChange={(event) => onEmailDraftChange(event.target.value)}
            autoComplete="email"
          />
          <button type="submit" aria-label="Apply user email">
            Apply
          </button>
        </div>
      </form>

      <div className="chat-list" aria-label="Saved chats">
        {isLoadingChats ? <p className="muted">Loading chats...</p> : null}
        {!isLoadingChats && chats.length === 0 ? <p className="muted">No chats yet.</p> : null}
        {chats.map((chat) => (
          <div className={chat.id === selectedChatId ? "chat-row selected" : "chat-row"} key={chat.id}>
            <button className="chat-select" type="button" onClick={() => onSelectChat(chat.id)} aria-label={chat.title}>
              <span className="chat-title">{chat.title}</span>
              <span className="chat-time">{formatTimestamp(chat.updatedAt)}</span>
            </button>
            <button
              className="icon-button subtle-action"
              type="button"
              onClick={() => onTogglePin(chat)}
              title={chat.isPinned ? "Unpin chat" : "Pin chat"}
              aria-label={chat.isPinned ? "Unpin chat" : "Pin chat"}
            >
              {chat.isPinned ? <PinOff aria-hidden="true" size={15} /> : <Pin aria-hidden="true" size={15} />}
            </button>
            <button
              className="icon-button danger-action"
              type="button"
              onClick={() => onDeleteChat(chat)}
              title="Delete chat"
              aria-label="Delete chat"
            >
              <Trash2 aria-hidden="true" size={15} />
            </button>
          </div>
        ))}
      </div>
    </aside>
  );
}
