import { Check, Pencil, Send } from "lucide-react";
import type { FormEvent } from "react";

import type { Chat, ChatMessage } from "../types";
import { formatTimestamp, getMessageAuthor } from "../utils/chatFormat";

interface ChatPanelProps {
  chat: Chat | null;
  draft: string;
  renameDraft: string;
  isLoadingChat: boolean;
  isSending: boolean;
  onDraftChange: (value: string) => void;
  onRenameDraftChange: (value: string) => void;
  onSaveTitle: () => void;
  onSendMessage: () => void;
}

export function ChatPanel({
  chat,
  draft,
  renameDraft,
  isLoadingChat,
  isSending,
  onDraftChange,
  onRenameDraftChange,
  onSaveTitle,
  onSendMessage,
}: ChatPanelProps) {
  function handleSend(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    onSendMessage();
  }

  return (
    <section className="chat-panel" aria-label="Selected chat">
      <header className="chat-panel-header">
        {chat ? (
          <div className="rename-row">
            <Pencil aria-hidden="true" size={17} />
            <label className="sr-only" htmlFor="chat-title">
              Chat title
            </label>
            <input
              id="chat-title"
              value={renameDraft}
              onChange={(event) => onRenameDraftChange(event.target.value)}
              maxLength={100}
            />
            <button
              className="icon-button primary-action"
              type="button"
              onClick={onSaveTitle}
              title="Save title"
              aria-label="Save title"
            >
              <Check aria-hidden="true" size={17} />
            </button>
          </div>
        ) : (
          <div>
            <p className="eyebrow">Ready</p>
            <h2>Start a company knowledge chat</h2>
          </div>
        )}
      </header>

      <div className="messages" aria-live="polite">
        {isLoadingChat ? <p className="muted">Loading messages...</p> : null}
        {!isLoadingChat && !chat ? (
          <div className="empty-state">
            <h2>Ask about policies, IT access, finance, or onboarding.</h2>
            <p>Choose a saved chat or send a new message to begin.</p>
          </div>
        ) : null}
        {chat?.messages.map((message) => <MessageBubble message={message} key={message.id} />)}
        {isSending ? <p className="muted">Assistant is answering...</p> : null}
      </div>

      <form className="composer" onSubmit={handleSend}>
        <label className="sr-only" htmlFor="message">
          Message
        </label>
        <textarea
          id="message"
          value={draft}
          onChange={(event) => onDraftChange(event.target.value)}
          placeholder="Ask a company question"
          rows={3}
        />
        <button className="send-button" type="submit" disabled={isSending || draft.trim().length === 0} aria-label="Send message">
          <Send aria-hidden="true" size={18} />
          <span>Send</span>
        </button>
      </form>
    </section>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  return (
    <article className={message.role === "USER" ? "message user-message" : "message agent-message"}>
      <div className="message-meta">
        <span>{getMessageAuthor(message)}</span>
        <time dateTime={message.createdAt}>{formatTimestamp(message.createdAt)}</time>
      </div>
      <p>{message.content}</p>
    </article>
  );
}
