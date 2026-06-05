import { Check, Pencil, Send } from "lucide-react";
import type { FormEvent, ReactNode } from "react";

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
      <MessageContent content={message.content} />
    </article>
  );
}

interface ParagraphBlock {
  type: "paragraph";
  lines: string[];
}

interface ListBlock {
  type: "list";
  items: string[];
}

type MessageBlock = ParagraphBlock | ListBlock;

function MessageContent({ content }: { content: string }) {
  return (
    <div className="message-content">
      {parseMessageBlocks(content).map((block, index) =>
        block.type === "list" ? (
          <ul key={index}>
            {block.items.map((item, itemIndex) => (
              <li key={itemIndex}>{renderInlineMarkdown(item)}</li>
            ))}
          </ul>
        ) : (
          <p key={index}>{renderInlineMarkdown(block.lines.join("\n"))}</p>
        ),
      )}
    </div>
  );
}

function parseMessageBlocks(content: string): MessageBlock[] {
  const blocks: MessageBlock[] = [];
  let paragraphLines: string[] = [];
  let listItems: string[] = [];

  function flushParagraph(): void {
    if (paragraphLines.length > 0) {
      blocks.push({ type: "paragraph", lines: paragraphLines });
      paragraphLines = [];
    }
  }

  function flushList(): void {
    if (listItems.length > 0) {
      blocks.push({ type: "list", items: listItems });
      listItems = [];
    }
  }

  for (const rawLine of content.split("\n")) {
    const line = rawLine.trimEnd();
    const trimmedLine = line.trim();

    if (trimmedLine.length === 0) {
      flushParagraph();
      flushList();
      continue;
    }

    if (trimmedLine.startsWith("- ")) {
      flushParagraph();
      listItems.push(trimmedLine.slice(2));
      continue;
    }

    flushList();
    paragraphLines.push(line);
  }

  flushParagraph();
  flushList();
  return blocks;
}

function renderInlineMarkdown(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const boldPattern = /\*\*([^*]+)\*\*/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = boldPattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }

    nodes.push(<strong key={`${match.index}-${match[1]}`}>{match[1]}</strong>);
    lastIndex = boldPattern.lastIndex;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes;
}
