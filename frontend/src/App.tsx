import { useEffect, useMemo, useState } from "react";
import "./index.css";
import {
  createUser,
  getMessages,
  getUserRiskAnalysis,
  getUsers,
  sendMessageStream,
  type RiskAnalysis,
  type User,
} from "./api";
import type { ConversationMessage } from "./types";
import ChatWindow from "./components/ChatWindow";
import { deleteMessages } from "./api";

const TEST_USER = {
  first_name: "Maija",
  last_name: "Meikäläinen",
  phone_number: "+358401234568",
  language: "fi",
};

const USER_ID_STORAGE_KEY = "welfare-bot-user-id";

export default function App() {
  const [selectedLanguage, setSelectedLanguage] = useState<string>("fi");
  const [users, setUsers] = useState<User[]>([]);
  const [userId, setUserId] = useState<number | null>(null);
  const [userName, setUserName] = useState<string>("Loading...");
  const [userLanguage, setUserLanguage] = useState<string>("fi");
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [riskAnalyses, setRiskAnalyses] = useState<RiskAnalysis[]>([]);
  const [loading, setLoading] = useState(false);
  const [bootstrapping, setBootstrapping] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const latestRisk = useMemo(() => {
    return riskAnalyses.length > 0 ? riskAnalyses[0] : null;
  }, [riskAnalyses]);

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

  function applyUserMeta(user: User) {
    setUserId(user.id);
    setUserName(`${user.first_name} ${user.last_name}`);
    setUserLanguage(user.language);
    setSelectedLanguage(user.language || "en");
    storeUserId(user.id);
  }

  async function loadMessages(id: number) {
    const history = await getMessages(id);
    setMessages(history);
  }

  async function loadRiskAnalysis(id: number) {
    const data = await getUserRiskAnalysis(id);
    setRiskAnalyses(data);
  }

  async function ensureUser(): Promise<User> {
    const fetchedUsers = await getUsers();
    setUsers(fetchedUsers);

    const storedId = getStoredUserId();

    if (storedId) {
      const storedUser = fetchedUsers.find((user) => user.id === storedId);
      if (storedUser) {
        applyUserMeta(storedUser);
        return storedUser;
      }

      localStorage.removeItem(USER_ID_STORAGE_KEY);
    }

    if (fetchedUsers.length > 0) {
      const firstUser = fetchedUsers[0];
      applyUserMeta(firstUser);
      return firstUser;
    }

    const newUser = await createUser(TEST_USER);
    setUsers([newUser]);
    applyUserMeta(newUser);
    return newUser;
  }

  async function bootstrap() {
    try {
      setBootstrapping(true);
      setError(null);

      const currentUser = await ensureUser();

      await Promise.all([
        loadMessages(currentUser.id),
        loadRiskAnalysis(currentUser.id),
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to initialize app");
    } finally {
      setBootstrapping(false);
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
          language: selectedLanguage,
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

      await Promise.all([loadMessages(userId), loadRiskAnalysis(userId)]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send message");
      await Promise.all([loadMessages(userId), loadRiskAnalysis(userId)]);
    } finally {
      setLoading(false);
    }
  }

  async function handleRefresh() {
    if (!userId) return;

    try {
      setError(null);
      await Promise.all([loadMessages(userId), loadRiskAnalysis(userId)]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to refresh data");
    }
  }

  async function handleUserChange(nextUserId: number) {
    const selected = users.find((user) => user.id === nextUserId);
    if (!selected) return;

    try {
      setError(null);
      applyUserMeta(selected);
      await Promise.all([
        loadMessages(selected.id),
        loadRiskAnalysis(selected.id),
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to switch user");
    }
  }
  async function handleClearChat() {
  if (!userId) return;

  try {
    await deleteMessages(userId);
    setMessages([]);
    setRiskAnalyses([]);
  } catch (err) {
    setError("Failed to clear chat");
  }
}

  function handleResetUser() {
    localStorage.removeItem(USER_ID_STORAGE_KEY);
    setUserId(null);
    setUserName("Loading...");
    setUserLanguage("fi");
    setSelectedLanguage("fi");
    setMessages([]);
    setRiskAnalyses([]);
    setError(null);
    void bootstrap();
  }

  useEffect(() => {
    void bootstrap();
  }, []);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <h2>Welfare Bot MVP</h2>

        <div className="sidebar-card">
          <div className="card-title">Current user</div>
          <div>
            <strong>User ID:</strong> {userId ?? "Loading..."}
          </div>
          <div>
            <strong>Name:</strong> {userName}
          </div>
          <div>
            <strong>Language:</strong> {selectedLanguage}
          </div>
        </div>

        <div className="sidebar-card">
          <label className="field-label" htmlFor="user-select">
            Select user
          </label>
          <select
            id="user-select"
            className="user-select"
            value={userId ?? ""}
            onChange={(e) => void handleUserChange(Number(e.target.value))}
            disabled={loading || bootstrapping || users.length === 0}
          >
            {users.length === 0 ? (
              <option value="">No users yet</option>
            ) : (
              users.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.first_name} {user.last_name} (#{user.id})
                </option>
              ))
            )}
          </select>
        </div>

        <div className="sidebar-card">
          <label className="field-label" htmlFor="language-select">
            Reply language
          </label>
          <select
            id="language-select"
            className="user-select"
            value={selectedLanguage}
            onChange={(e) => setSelectedLanguage(e.target.value)}
            disabled={loading || bootstrapping}
          >
            <option value="en">English</option>
            <option value="fi">Finnish</option>
            <option value="sv">Swedish</option>
          </select>
        </div>

        <div className="sidebar-card">
          <div className="card-title">Risk status</div>

          {latestRisk ? (
            <>
              <div
                className={`risk-badge risk-${String(latestRisk.risk_level).toLowerCase()}`}
              >
                {latestRisk.risk_level}
              </div>

              <div className="risk-meta">
                <strong>Category:</strong> {latestRisk.category}
              </div>

              <div className="risk-meta">
                <strong>Reason:</strong> {latestRisk.reason}
              </div>

              <div className="risk-meta">
                <strong>Suggested action:</strong> {latestRisk.suggested_action}
              </div>

              {latestRisk.needs_family_notification && (
                <div className="risk-alert">Family notification needed</div>
              )}
            </>
          ) : (
            <div className="muted-text">No risk analysis yet</div>
          )}
        </div>

        <button
          className="refresh-button"
          onClick={() => void handleRefresh()}
          disabled={!userId || loading || bootstrapping}
        >
          Refresh history
        </button>

        <button
          className="refresh-button"
          onClick={handleResetUser}
          disabled={loading || bootstrapping}
          style={{ marginTop: "10px" }}
        >
          Reset user
        </button>
        <button
          className="refresh-button"
          onClick={handleClearChat}
          disabled={!userId || loading}
          style={{ marginTop: "10px", background: "#dc2626" }}
        >
          Clear chat
        </button>
      </aside>

      <main className="main-panel">
        <ChatWindow
          title="Welfare Bot Chat"
          subtitle="Streaming AI conversation"
          messages={messages}
          onSend={handleSend}
          loading={loading || bootstrapping}
          error={error}
        />
      </main>
    </div>
  );
}