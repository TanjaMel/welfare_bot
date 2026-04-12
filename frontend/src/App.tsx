import { useEffect, useState } from "react";
import "./index.css";
import { createUser, getMessages, sendMessageStream } from "./api";
import type { ConversationMessage } from "./types";
import ChatWindow from "./components/ChatWindow";

const TEST_USER = {
  first_name: "Maija",
  last_name: "Meikäläinen",
  phone_number: "+358401234567",
  language: "fi",
};

const USER_ID_STORAGE_KEY = "welfare-bot-user-id";

export default function App() {
  const [userId, setUserId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function getStoredUserId(): number | null {
    const raw = localStorage.getItem(USER_ID_STORAGE_KEY);
    if (!raw) return null;

    const parsed = Number(raw);
    if (!Number.isInteger(parsed) || parsed <= 0) {
      localStorage.removeItem(USER_ID_STORAGE_KEY);
      return null;
    }

    return parsed;
  }

  function storeUserId(id: number) {
    localStorage.setItem(USER_ID_STORAGE_KEY, String(id));
  }

  async function ensureUser() {
    const storedId = getStoredUserId();

    if (storedId) {
      setUserId(storedId);
      return storedId;
    }

    const user = await createUser(TEST_USER);
    setUserId(user.id);
    storeUserId(user.id);
    return user.id;
  }

  async function loadMessages(id: number) {
    const history = await getMessages(id);
    setMessages(history);
  }

  async function bootstrap() {
    try {
      setError(null);
      const id = await ensureUser();
      await loadMessages(id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to initialize app");
    }
  }

  async function handleSend(text: string) {
    if (!userId) return;

    const trimmed = text.trim();
    if (!trimmed) return;

    try {
      setLoading(true);
      setError(null);

      const now = Date.now();

      const userMessage: ConversationMessage = {
        id: now,
        role: "user",
        content: trimmed,
        created_at: new Date().toISOString(),
      };

      const assistantMessageId = now + 1;
      const assistantPlaceholder: ConversationMessage = {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMessage, assistantPlaceholder]);

      await sendMessageStream(
        {
          user_id: userId,
          message: trimmed,
        },
        (chunk) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? {
                    ...msg,
                    content: msg.content + chunk,
                  }
                : msg,
            ),
          );
        },
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send message");
      await loadMessages(userId);
    } finally {
      setLoading(false);
    }
  }

  function handleResetUser() {
    localStorage.removeItem(USER_ID_STORAGE_KEY);
    setUserId(null);
    setMessages([]);
    setError(null);
    void bootstrap();
  }

  useEffect(() => {
    void bootstrap();
  }, []);

  return (
    <div className="app-shell">
      <div className="sidebar">
        <h2>Welfare Bot MVP</h2>

        <div className="sidebar-card">
          <div>
            <strong>User ID:</strong> {userId ?? "Loading..."}
          </div>
          <div>
            <strong>Name:</strong> {TEST_USER.first_name} {TEST_USER.last_name}
          </div>
          <div>
            <strong>Language:</strong> {TEST_USER.language}
          </div>
        </div>

        <button
          className="refresh-button"
          onClick={() => userId && loadMessages(userId)}
          disabled={!userId || loading}
        >
          Refresh history
        </button>

        <button
          className="refresh-button"
          onClick={handleResetUser}
          disabled={loading}
          style={{ marginTop: "10px" }}
        >
          Reset user
        </button>
      </div>

      <ChatWindow
        messages={messages}
        onSend={handleSend}
        loading={loading}
        error={error}
      />
    </div>
  );
}