import { useEffect, useMemo, useState } from "react";

import { ChatApiError, createChatMessage, deleteChat, getChat, listChats, updateChat } from "./api/chatApi";
import { ChatPanel } from "./components/ChatPanel";
import { ErrorBanner } from "./components/ErrorBanner";
import { Sidebar } from "./components/Sidebar";
import { usePersistentUserEmail } from "./hooks/usePersistentUserEmail";
import type { Chat, ChatListItem, ChatMessage } from "./types";
import { sortChats } from "./utils/chatFormat";

export default function App() {
  const { userEmail, setUserEmail } = usePersistentUserEmail();
  const [emailDraft, setEmailDraft] = useState(userEmail);
  const [chats, setChats] = useState<ChatListItem[]>([]);
  const [selectedChatId, setSelectedChatId] = useState<string | null>(null);
  const [activeChat, setActiveChat] = useState<Chat | null>(null);
  const [draft, setDraft] = useState("");
  const [renameDraft, setRenameDraft] = useState("");
  const [isLoadingChats, setIsLoadingChats] = useState(false);
  const [isLoadingChat, setIsLoadingChat] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const sortedChats = useMemo(() => sortChats(chats), [chats]);

  useEffect(() => {
    void loadChats(userEmail);
  }, [userEmail]);

  useEffect(() => {
    if (!selectedChatId) {
      setActiveChat(null);
      setRenameDraft("");
      return;
    }

    void loadChat(selectedChatId, userEmail);
  }, [selectedChatId, userEmail]);

  async function loadChats(email: string, preferredChatId?: string): Promise<void> {
    setIsLoadingChats(true);
    setErrorMessage(null);

    try {
      const page = await listChats(email);
      const sortedItems = sortChats(page.items);
      setChats(sortedItems);

      if (preferredChatId) {
        setSelectedChatId(preferredChatId);
      } else if (!selectedChatId && sortedItems.length > 0) {
        setSelectedChatId(sortedItems[0].id);
      } else if (selectedChatId && sortedItems.every((chat) => chat.id !== selectedChatId)) {
        setSelectedChatId(sortedItems[0]?.id ?? null);
      }
    } catch (error) {
      setErrorMessage(readErrorMessage(error));
    } finally {
      setIsLoadingChats(false);
    }
  }

  async function loadChat(chatId: string, email: string): Promise<void> {
    setIsLoadingChat(true);
    setErrorMessage(null);

    try {
      const chat = await getChat(chatId, email);
      setActiveChat(chat);
      setRenameDraft(chat.title);
    } catch (error) {
      setErrorMessage(readErrorMessage(error));
    } finally {
      setIsLoadingChat(false);
    }
  }

  function handleApplyEmail(): void {
    const trimmedEmail = emailDraft.trim();

    if (trimmedEmail.length === 0) {
      setErrorMessage("User email is required.");
      return;
    }

    setSelectedChatId(null);
    setActiveChat(null);
    setChats([]);
    setUserEmail(trimmedEmail);
  }

  function handleNewChat(): void {
    setSelectedChatId(null);
    setActiveChat(null);
    setRenameDraft("");
    setDraft("");
    setErrorMessage(null);
  }

  async function handleSendMessage(): Promise<void> {
    const content = draft.trim();

    if (content.length === 0) {
      return;
    }

    const previousChat = activeChat;
    const temporaryMessage = buildTemporaryUserMessage(content, selectedChatId ?? "pending-chat");
    setDraft("");
    setIsSending(true);
    setErrorMessage(null);

    if (previousChat) {
      setActiveChat({ ...previousChat, messages: [...previousChat.messages, temporaryMessage] });
    } else {
      setActiveChat({
        id: "pending-chat",
        title: "New chat",
        isPinned: false,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        userEmail,
        messages: [temporaryMessage],
      });
    }

    try {
      const answer = await createChatMessage({ chatId: selectedChatId ?? undefined, content, userEmail });
      setSelectedChatId(answer.chatId);
      await loadChat(answer.chatId, userEmail);
      await loadChats(userEmail, answer.chatId);
    } catch (error) {
      setDraft(content);
      setActiveChat(previousChat);
      setErrorMessage(readErrorMessage(error));
    } finally {
      setIsSending(false);
    }
  }

  async function handleSaveTitle(): Promise<void> {
    if (!activeChat) {
      return;
    }

    const trimmedTitle = renameDraft.trim();

    if (trimmedTitle.length === 0 || trimmedTitle === activeChat.title) {
      return;
    }

    const previousChat = activeChat;
    setActiveChat({ ...activeChat, title: trimmedTitle });
    setChats((currentChats) =>
      currentChats.map((chat) => (chat.id === activeChat.id ? { ...chat, title: trimmedTitle } : chat)),
    );

    try {
      await updateChat(activeChat.id, { title: trimmedTitle });
      await loadChats(userEmail, activeChat.id);
    } catch (error) {
      setActiveChat(previousChat);
      setRenameDraft(previousChat.title);
      setChats((currentChats) =>
        currentChats.map((chat) => (chat.id === previousChat.id ? { ...chat, title: previousChat.title } : chat)),
      );
      setErrorMessage(readErrorMessage(error));
    }
  }

  async function handleTogglePin(chat: ChatListItem): Promise<void> {
    const nextPinnedState = !chat.isPinned;
    const previousChats = chats;
    setChats((currentChats) =>
      sortChats(currentChats.map((item) => (item.id === chat.id ? { ...item, isPinned: nextPinnedState } : item))),
    );

    try {
      await updateChat(chat.id, { isPinned: nextPinnedState });
      await loadChats(userEmail, selectedChatId ?? chat.id);
    } catch (error) {
      setChats(previousChats);
      setErrorMessage(readErrorMessage(error));
    }
  }

  async function handleDeleteChat(chat: ChatListItem): Promise<void> {
    const previousChats = chats;
    const previousActiveChat = activeChat;
    setChats((currentChats) => currentChats.filter((item) => item.id !== chat.id));

    if (selectedChatId === chat.id) {
      setSelectedChatId(null);
      setActiveChat(null);
    }

    try {
      await deleteChat(chat.id);
      await loadChats(userEmail);
    } catch (error) {
      setChats(previousChats);
      setActiveChat(previousActiveChat);
      setSelectedChatId(previousActiveChat?.id ?? selectedChatId);
      setErrorMessage(readErrorMessage(error));
    }
  }

  return (
    <main className="app-shell">
      <Sidebar
        chats={sortedChats}
        emailDraft={emailDraft}
        selectedChatId={selectedChatId}
        isLoadingChats={isLoadingChats}
        onEmailDraftChange={setEmailDraft}
        onApplyEmail={handleApplyEmail}
        onNewChat={handleNewChat}
        onSelectChat={setSelectedChatId}
        onTogglePin={handleTogglePin}
        onDeleteChat={handleDeleteChat}
      />
      <div className="workspace">
        <ErrorBanner message={errorMessage} />
        <ChatPanel
          chat={activeChat}
          draft={draft}
          renameDraft={renameDraft}
          isLoadingChat={isLoadingChat}
          isSending={isSending}
          onDraftChange={setDraft}
          onRenameDraftChange={setRenameDraft}
          onSaveTitle={handleSaveTitle}
          onSendMessage={handleSendMessage}
        />
      </div>
    </main>
  );
}

function buildTemporaryUserMessage(content: string, chatId: string): ChatMessage {
  const timestamp = new Date().toISOString();

  return {
    id: `pending-${timestamp}`,
    chatId,
    role: "USER",
    content,
    language: "RU",
    createdAt: timestamp,
    updatedAt: timestamp,
  };
}

function readErrorMessage(error: unknown): string {
  if (error instanceof ChatApiError || error instanceof Error) {
    return error.message;
  }
  return "Request failed.";
}
