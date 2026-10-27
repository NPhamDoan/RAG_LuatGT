import { useState } from "react";
import type { useChatSessions } from "../hooks/useChatSessions";
import ChatInput from "../components/chat/ChatInput";
import MessageList from "../components/chat/MessageList";
import ChatSidebar from "../components/chat/ChatSidebar";
import WelcomeSuggestions from "../components/chat/WelcomeSuggestions";

interface Props {
  chat: ReturnType<typeof useChatSessions>;
}

export default function ChatPage({ chat }: Props) {
  const {
    messages,
    loading,
    sendQuery,
    sessions,
    currentId,
    newSession,
    switchSession,
    deleteSession,
  } = chat;

  const [collapsed, setCollapsed] = useState(false);
  const hasMessages = messages.length > 0;

  return (
    <div className="flex h-full">
      <ChatSidebar
        sessions={sessions}
        currentId={currentId}
        collapsed={collapsed}
        onToggle={() => setCollapsed((c) => !c)}
        onNew={newSession}
        onSwitch={switchSession}
        onDelete={deleteSession}
      />

      <div className="flex h-full min-w-0 flex-1 flex-col">
        {hasMessages ? (
          <MessageList messages={messages} loading={loading} />
        ) : (
          <WelcomeSuggestions onSuggestionClick={sendQuery} />
        )}

        {/* Input */}
        <div className="shrink-0 border-t border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3">
          <div className="mx-auto max-w-3xl">
            <ChatInput onSend={sendQuery} disabled={loading} />
          </div>
        </div>
      </div>
    </div>
  );
}
