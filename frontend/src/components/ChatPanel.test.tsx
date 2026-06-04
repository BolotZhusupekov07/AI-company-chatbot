import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChatPanel } from "./ChatPanel";
import type { Chat } from "../types";

describe("ChatPanel", () => {
  it("renders assistant markdown emphasis and bullet lists", () => {
    render(
      <ChatPanel
        chat={chatWithAnswer(
          [
            "Based on our office access policy:",
            "",
            "**Employees** can access the office with their personal access badge.",
            "",
            "**Specific Zone Access:**",
            "- **Issyk-Kul Hall** (Training, onboarding, all-hands): Employees and registered guests",
            "- **Archive Cabinet** (Printed HR and finance records): HR and Finance only",
          ].join("\n"),
        )}
        draft=""
        renameDraft="Office access"
        isLoadingChat={false}
        isSending={false}
        onDraftChange={vi.fn()}
        onRenameDraftChange={vi.fn()}
        onSaveTitle={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );

    expect(screen.getByText("Employees").tagName).toBe("STRONG");
    expect(screen.getByText("Specific Zone Access:").tagName).toBe("STRONG");

    const listItems = screen.getAllByRole("listitem");
    expect(listItems).toHaveLength(2);
    expect(within(listItems[0]).getByText("Issyk-Kul Hall").tagName).toBe("STRONG");
    expect(within(listItems[1]).getByText("Archive Cabinet").tagName).toBe("STRONG");
  });
});

function chatWithAnswer(content: string): Chat {
  return {
    id: "chat-office",
    title: "Office access",
    isPinned: false,
    createdAt: "2026-06-04T09:00:00",
    updatedAt: "2026-06-04T09:01:00",
    userEmail: "aida@example.com",
    messages: [
      {
        id: "message-office",
        chatId: "chat-office",
        role: "AGENT",
        content,
        language: "RU",
        createdAt: "2026-06-04T09:01:00",
        updatedAt: "2026-06-04T09:01:00",
      },
    ],
  };
}
