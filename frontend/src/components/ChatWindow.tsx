import { useState } from "react";
import type { ConversationMessage } from "../types";

type Props = {
  messages: ConversationMessage[];
  onSend: (text: string) => Promise<void>;
  loading: boolean;
  error: string | null;
};

export default function ChatWindow({
  messages,
  onSend,
  loading,
  error,
}: Props) {
  const [input, setInput] = useState("");

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();

    const text = input.trim();
    if (!text || loading) return;

    try {
      await onSend(text);
      setInput("");
    } catch {
      // parent handles error state
    }
  }

  return (
    <div className="chat-window">
      <div className="chat-header">
        <h1>Welfare Bot Chat</h1>
        <p>Streaming AI conversation</p>
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="message-list">
        {messages.length === 0 ? (
          <div className="empty-state">No messages yet</div>
        ) : (
          messages.map((message) => {
            const isUser = message.role === "user";

            return (
              <div
                key={message.id}
                className={`message-row ${
                  isUser ? "message-row-user" : "message-row-assistant"
                }`}
              >
                <div
                  className={`message-bubble ${
                    isUser ? "user" : "assistant"
                  }`}
                >
                  <div className="message-role">
                    {isUser ? "You" : "Welfare Bot"}
                  </div>

                  <div className="message-content">
                    {message.content || (!isUser ? "..." : "")}
                  </div>

                  {message.created_at && (
                    <div className="message-time">
                      {new Date(message.created_at).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {loading && <div className="loading-box">Welfare Bot is typing...</div>}

      <form className="message-input-form" onSubmit={handleSubmit}>
        <textarea
          className="message-input"
          placeholder="Write a message..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={loading}
        />

        <button
          className="send-button"
          type="submit"
          disabled={loading || !input.trim()}
        >
          {loading ? "Sending..." : "Send"}
        </button>
      </form>
    </div>
  );
}