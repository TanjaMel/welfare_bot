import { useMemo, useState } from "react";
import type { ConversationMessage } from "../types";

type Props = {
  title?: string;
  subtitle?: string;
  messages: ConversationMessage[];
  onSend: (text: string) => void | Promise<void>;
  loading: boolean;
  error: string | null;
};

function formatTime(value?: string | null): string {
  if (!value) return "";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";

  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getRiskClass(riskLevel?: string | null): string {
  if (!riskLevel) return "";

  const normalized = riskLevel.toLowerCase();

  if (normalized === "low") return "message-risk-low";
  if (normalized === "medium") return "message-risk-medium";
  if (normalized === "high" || normalized === "critical") return "message-risk-high";

  return "";
}

export default function ChatWindow({
  title = "Welfare Bot Chat",
  subtitle = "Streaming AI conversation",
  messages,
  onSend,
  loading,
  error,
}: Props) {
  const [input, setInput] = useState("");

  const hasMessages = useMemo(() => messages.length > 0, [messages]);

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
    <div className="chat-card">
      <div className="chat-header">
        <h1 className="chat-title">{title}</h1>
        <p className="chat-subtitle">{subtitle}</p>
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="messages-box">
        {!hasMessages ? (
          <div className="empty-state">No messages yet</div>
        ) : (
          messages.map((message) => {
            const isUser = message.role === "user";
            const riskClass = getRiskClass(message.risk_level);

            return (
              <div
                key={message.id}
                className={`message-row ${isUser ? "user" : "assistant"}`}
              >
                <div
                  className={`message-bubble ${isUser ? "user" : "assistant"} ${riskClass}`}
                >
                  {message.risk_level && isUser && (
                    <div
                      className={`message-risk-pill ${riskClass}`}
                    >
                      Risk: {message.risk_level}
                      {typeof message.risk_score === "number"
                        ? ` (${message.risk_score})`
                        : ""}
                    </div>
                  )}

                  <div className="message-content">
                    {message.content || (!isUser ? "..." : "")}
                  </div>

                  <div className="message-meta">
                    <span className="message-role">
                      {isUser ? "You" : "Welfare Bot"}
                    </span>
                    <span className="message-time">
                      {formatTime(message.created_at)}
                    </span>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {loading && <div className="loading-box">Welfare Bot is typing...</div>}

      <form className="input-area" onSubmit={handleSubmit}>
        <textarea
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