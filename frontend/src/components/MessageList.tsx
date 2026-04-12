import type { ConversationMessage } from "../types";

type Props = {
  messages: ConversationMessage[];
};

export default function MessageList({ messages }: Props) {
  if (messages.length === 0) {
    return <div className="empty-state">No messages yet</div>;
  }

  return (
    <div className="message-list">
      {messages.map((message) => {
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
      })}
    </div>
  );
}