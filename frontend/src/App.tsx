import { useEffect, useMemo, useState } from "react";
import "./index.css";
import {
  deleteMessages,
  getMessages,
  getUserRiskAnalysis,
  getUsers,
  logout,
  sendMessageStream,
  startConversation,
  type RiskAnalysis,
  type User,
} from "./api";
import type { ConversationMessage } from "./types";
import ChatWindow from "./components/ChatWindow";
import LoginPage from "./components/LoginPage";

const USER_ID_STORAGE_KEY = "welfare-bot-user-id";

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(
    !!localStorage.getItem("access_token")
  );
  const [selectedLanguage, setSelectedLanguage] = useState<string>("fi");
  const [users, setUsers] = useState<User[]>([]);
  const [userId, setUserId] = useState<number | null>(null);
  const [userName, setUserName] = useState<string>("Loading...");
  const [userLanguage, setUserLanguage] = useState<string>("fi");
  const [currentUserRole, setCurrentUserRole] = useState<string>("user");
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
    setUserName([user.first_name, user.last_name].filter(Boolean).join(" "));
    setUserLanguage(user.language || "fi");
    setSelectedLanguage(user.language || "fi");
    storeUserId(user.id);
  }

  async function loadRiskAnalysis(id: number) {
    const data = await getUserRiskAnalysis(id);
    setRiskAnalyses(data);
  }

  async function bootstrap() {
    try {
      setBootstrapping(true);
      setError(null);

      const stored = localStorage.getItem("current_user");
      const currentUser: User | null = stored ? JSON.parse(stored) : null;

      if (!currentUser) {
        setError("Session expired. Please log in again.");
        setBootstrapping(false);
        return;
      }

      setCurrentUserRole(currentUser.role ?? "user");

      if (currentUser.role === "admin") {
        const allUsers = await getUsers();
        setUsers(allUsers);
        const storedId = getStoredUserId();
        const target = storedId
          ? allUsers.find((u) => u.id === storedId) ?? allUsers[0]
          : allUsers[0];
        if (target) applyUserMeta(target);
      } else {
        setUsers([currentUser]);
        applyUserMeta(currentUser);
      }

      const id = currentUser.id;

      // Load risk analysis
      const [, riskResult] = await Promise.allSettled([
        Promise.resolve(),
        loadRiskAnalysis(id),
      ]);
      if (riskResult.status === "rejected") setRiskAnalyses([]);

      // Load messages and start conversation if needed
      try {
        const allMessages = await getMessages(id);
        const todayMessages = allMessages.filter((m) =>
          new Date(m.created_at).toDateString() === new Date().toDateString()
        );

        if (todayMessages.length === 0) {
          // No messages today — bot sends opening greeting
          await startConversation(id, currentUser.language || "fi");
          // Reload from DB to get correct IDs
          const refreshed = await getMessages(id);
          setMessages(refreshed);
        } else {
          setMessages(allMessages);
        }
      } catch (e) {
        console.warn("Could not load/start conversation:", e);
        setMessages([]);
      }
    } catch (err) {
      console.warn("bootstrap failed:", err);
      setMessages([]);
      setRiskAnalyses([]);
      setError("Failed to load data.");
    } finally {
      setBootstrapping(false);
    }
  }

  async function handleSend(text: string) {
    if (!userId) return;
    const trimmed = text.trim();
    if (!trimmed) return;
    const now = Date.now();
    const pendingAssistantId = now + 1;
    try {
      setLoading(true);
      setError(null);
      const userMessage: ConversationMessage = {
        id: now,
        role: "user",
        content: trimmed,
        created_at: new Date().toISOString(),
      };
      const assistantPlaceholder: ConversationMessage = {
        id: pendingAssistantId,
        role: "assistant",
        content: "",
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMessage, assistantPlaceholder]);
      await sendMessageStream(
        { user_id: userId, message: trimmed, language: selectedLanguage },
        (chunk) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === pendingAssistantId
                ? { ...msg, content: msg.content + chunk }
                : msg,
            ),
          );
        },
      );
      // Reload messages and risk after send
      const [refreshed, riskData] = await Promise.allSettled([
        getMessages(userId),
        getUserRiskAnalysis(userId),
      ]);
      if (refreshed.status === "fulfilled") setMessages(refreshed.value);
      if (riskData.status === "fulfilled") setRiskAnalyses(riskData.value);
    } catch (err) {
      console.warn("Send failed:", err);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === pendingAssistantId
            ? { ...msg, content: msg.content || "Failed to send. Please try again." }
            : msg,
        ),
      );
      setError("Message sending failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRefresh() {
    if (!userId) return;
    setError(null);
    const [refreshed, riskData] = await Promise.allSettled([
      getMessages(userId),
      getUserRiskAnalysis(userId),
    ]);
    if (refreshed.status === "fulfilled") setMessages(refreshed.value);
    if (riskData.status === "fulfilled") setRiskAnalyses(riskData.value);
  }

  async function handleUserChange(nextUserId: number) {
    const selected = users.find((u) => u.id === nextUserId);
    if (!selected) return;
    setError(null);
    applyUserMeta(selected);
    const [refreshed, riskData] = await Promise.allSettled([
      getMessages(selected.id),
      getUserRiskAnalysis(selected.id),
    ]);
    if (refreshed.status === "fulfilled") setMessages(refreshed.value);
    if (riskData.status === "fulfilled") setRiskAnalyses(riskData.value);
  }

  async function handleClearChat() {
    if (!userId) return;
    try {
      await deleteMessages(userId);
      setMessages([]);
      setRiskAnalyses([]);
    } catch {
      setMessages([]);
      setRiskAnalyses([]);
    }
  }

  function handleLogout() {
    logout();
  }

  useEffect(() => {
    if (isAuthenticated) void bootstrap();
  }, [isAuthenticated]);

  if (!isAuthenticated) {
    return <LoginPage onSuccess={() => setIsAuthenticated(true)} />;
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <h2>Welfare Bot</h2>

        <div className="sidebar-card">
          <div className="card-title">Current user</div>
          <div><strong>ID:</strong> {userId ?? "..."}</div>
          <div><strong>Name:</strong> {userName}</div>
          <div><strong>Language:</strong> {userLanguage}</div>
          <div><strong>Role:</strong> {currentUserRole}</div>
        </div>

        {currentUserRole === "admin" && users.length > 1 && (
          <div className="sidebar-card">
            <label className="field-label" htmlFor="user-select">Select user</label>
            <select
              id="user-select"
              className="user-select"
              value={userId ?? ""}
              onChange={(e) => void handleUserChange(Number(e.target.value))}
              disabled={loading || bootstrapping}
            >
              {users.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.first_name} {user.last_name} (#{user.id})
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="sidebar-card">
          <label className="field-label" htmlFor="language-select">Reply language</label>
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
              <div className={`risk-badge risk-${latestRisk.risk_level.toLowerCase()}`}>
                {latestRisk.risk_level.toUpperCase()} — score: {latestRisk.risk_score}
              </div>
              <div className="risk-meta"><strong>Category:</strong> {latestRisk.category}</div>
              {latestRisk.reason && (
                <div className="risk-meta"><strong>Reason:</strong> {latestRisk.reason}</div>
              )}
              {latestRisk.suggested_action && (
                <div className="risk-meta"><strong>Action:</strong> {latestRisk.suggested_action}</div>
              )}
              {latestRisk.follow_up_question && (
                <div className="risk-meta" style={{ fontStyle: "italic" }}>
                  {latestRisk.follow_up_question}
                </div>
              )}
              {(latestRisk.needs_family_notification || latestRisk.should_alert_family) && (
                <div className="risk-alert">⚠️ Family notification needed</div>
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
          onClick={() => void handleClearChat()}
          disabled={!userId || loading}
          style={{ marginTop: "10px", background: "#dc2626" }}
        >
          Clear chat
        </button>
        <button
          className="refresh-button"
          onClick={handleLogout}
          style={{ marginTop: "10px", background: "#475569" }}
        >
          Log out
        </button>
      </aside>

      <main className="main-panel">
        <ChatWindow
          title="Welfare Bot Chat"
          subtitle="AI-powered welfare assistant"
          messages={messages}
          onSend={handleSend}
          loading={loading || bootstrapping}
          error={error}
          language={selectedLanguage}
        />
      </main>
    </div>
  );
}
