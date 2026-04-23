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
import CareContactForm from "./components/CareContactForm";

const USER_ID_STORAGE_KEY = "welfare-bot-user-id";

function getWellbeingInfo(riskLevel: string | undefined) {
  if (!riskLevel) return { icon: "🌿", label: "No data yet", sub: "Start a conversation", cls: "none" };
  switch (riskLevel.toLowerCase()) {
    case "low": return { icon: "😊", label: "All good", sub: "You're doing well today.", cls: "low" };
    case "medium": return { icon: "😐", label: "Some concerns", sub: "Let's check in more.", cls: "medium" };
    case "high": return { icon: "😟", label: "Needs attention", sub: "Please reach out today.", cls: "high" };
    case "critical": return { icon: "🚨", label: "Critical", sub: "Contact help immediately.", cls: "critical" };
    default: return { icon: "🌿", label: "No data yet", sub: "Start a conversation", cls: "none" };
  }
}

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(!!localStorage.getItem("access_token"));
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

  const latestRisk = useMemo(() => riskAnalyses.length > 0 ? riskAnalyses[0] : null, [riskAnalyses]);
  const wellbeing = getWellbeingInfo(latestRisk?.risk_level);
  const userInitial = userName ? userName.charAt(0).toUpperCase() : "?";

  function getStoredUserId(): number | null {
    const raw = localStorage.getItem(USER_ID_STORAGE_KEY);
    if (!raw) return null;
    const parsed = Number(raw);
    if (!Number.isInteger(parsed) || parsed <= 0) { localStorage.removeItem(USER_ID_STORAGE_KEY); return null; }
    return parsed;
  }

  function storeUserId(id: number) { localStorage.setItem(USER_ID_STORAGE_KEY, String(id)); }

  function applyUserMeta(user: User) {
    setUserId(user.id);
    setUserName([user.first_name, user.last_name].filter(Boolean).join(" "));
    setUserLanguage(user.language || "fi");
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
      if (!currentUser) { setError("Session expired. Please log in again."); setBootstrapping(false); return; }
      setCurrentUserRole(currentUser.role ?? "user");
      if (currentUser.role === "admin") {
        const allUsers = await getUsers();
        setUsers(allUsers);
        const storedId = getStoredUserId();
        const target = storedId ? allUsers.find((u) => u.id === storedId) ?? allUsers[0] : allUsers[0];
        if (target) applyUserMeta(target);
      } else {
        setUsers([currentUser]);
        applyUserMeta(currentUser);
      }
      const id = currentUser.id;
      const [, riskResult] = await Promise.allSettled([Promise.resolve(), loadRiskAnalysis(id)]);
      if (riskResult.status === "rejected") setRiskAnalyses([]);
      try {
        const allMessages = await getMessages(id);
        const todayMessages = allMessages.filter((m) =>
          new Date(m.created_at).toDateString() === new Date().toDateString()
        );
        if (todayMessages.length === 0) {
          await startConversation(id);
          const refreshed = await getMessages(id);
          setMessages(refreshed);
        } else {
          setMessages(allMessages);
        }
      } catch (e) { console.warn("Could not load/start conversation:", e); setMessages([]); }
    } catch (err) { console.warn("bootstrap failed:", err); setMessages([]); setRiskAnalyses([]); setError("Failed to load data."); }
    finally { setBootstrapping(false); }
  }

  async function handleSend(text: string) {
    if (!userId) return;
    const trimmed = text.trim();
    if (!trimmed) return;
    const now = Date.now();
    const pendingAssistantId = now + 1;
    try {
      setLoading(true); setError(null);
      setMessages((prev) => [...prev,
        { id: now, role: "user", content: trimmed, created_at: new Date().toISOString() },
        { id: pendingAssistantId, role: "assistant", content: "", created_at: new Date().toISOString() },
      ]);
      await sendMessageStream(
        { user_id: userId, message: trimmed, language: "auto" },
        (chunk) => {
          setMessages((prev) => prev.map((msg) =>
            msg.id === pendingAssistantId ? { ...msg, content: msg.content + chunk } : msg
          ));
        },
      );
      const [refreshed, riskData] = await Promise.allSettled([getMessages(userId), getUserRiskAnalysis(userId)]);
      if (refreshed.status === "fulfilled") setMessages(refreshed.value);
      if (riskData.status === "fulfilled") setRiskAnalyses(riskData.value);
    } catch (err) {
      console.warn("Send failed:", err);
      setMessages((prev) => prev.map((msg) =>
        msg.id === pendingAssistantId ? { ...msg, content: msg.content || "Failed to send." } : msg
      ));
      setError("Message sending failed.");
    } finally { setLoading(false); }
  }

  async function handleRefresh() {
    if (!userId) return;
    setError(null);
    const [refreshed, riskData] = await Promise.allSettled([getMessages(userId), getUserRiskAnalysis(userId)]);
    if (refreshed.status === "fulfilled") setMessages(refreshed.value);
    if (riskData.status === "fulfilled") setRiskAnalyses(riskData.value);
  }

  async function handleUserChange(nextUserId: number) {
    const selected = users.find((u) => u.id === nextUserId);
    if (!selected) return;
    setError(null); applyUserMeta(selected);
    const [refreshed, riskData] = await Promise.allSettled([getMessages(selected.id), getUserRiskAnalysis(selected.id)]);
    if (refreshed.status === "fulfilled") setMessages(refreshed.value);
    if (riskData.status === "fulfilled") setRiskAnalyses(riskData.value);
  }

  async function handleClearChat() {
    if (!userId) return;
    try { await deleteMessages(userId); setMessages([]); setRiskAnalyses([]); }
    catch { setMessages([]); setRiskAnalyses([]); }
  }

  useEffect(() => { if (isAuthenticated) void bootstrap(); }, [isAuthenticated]);

  if (!isAuthenticated) return <LoginPage onSuccess={() => setIsAuthenticated(true)} />;

  const timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="sidebar-logo">🤝</div>
          <div>
            <h2>Welfare Bot</h2>
            <p>AI-powered assistant</p>
          </div>
        </div>

        <div className="user-card">
          <div className="user-avatar">{userInitial}</div>
          <div>
            <div className="user-info-name">{userName}</div>
            <div className="user-info-sub">Hello! 👋</div>
          </div>
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

        <div className="wellbeing-card">
          <div className="wellbeing-label">Your well-being today</div>
          <div className="wellbeing-status">
            <div className={`wellbeing-icon ${wellbeing.cls}`}>{wellbeing.icon}</div>
            <div>
              <div className="wellbeing-text-main">{wellbeing.label}</div>
              <div className="wellbeing-text-sub">{wellbeing.sub}</div>
            </div>
          </div>
          {latestRisk && (
            <>
              {latestRisk.reason && <div className="risk-meta" style={{ marginTop: "8px" }}><strong>Reason:</strong> {latestRisk.reason}</div>}
              {latestRisk.suggested_action && <div className="risk-meta"><strong>Action:</strong> {latestRisk.suggested_action}</div>}
              {latestRisk.follow_up_question && <div className="risk-meta" style={{ fontStyle: "italic" }}>{latestRisk.follow_up_question}</div>}
              {(latestRisk.needs_family_notification || latestRisk.should_alert_family) && (
                <div className="risk-alert">⚠️ Family notification needed</div>
              )}
            </>
          )}
          <div className="wellbeing-time">🕐 Checked at {timeStr}</div>
        </div>

        {userId && <CareContactForm userId={userId} />}

        <div className="quick-actions">
          <div className="card-title" style={{ padding: "8px 12px 4px" }}>Quick actions</div>
          <button className="quick-action-btn" onClick={() => void handleRefresh()} disabled={!userId || loading || bootstrapping}>
            <div className="action-icon blue">🔄</div>
            <div><div className="action-text-main">Refresh conversation</div><div className="action-text-sub">Get the latest updates</div></div>
            <span className="action-arrow">›</span>
          </button>
          <button className="quick-action-btn" onClick={() => void handleClearChat()} disabled={!userId || loading}>
            <div className="action-icon red">🗑️</div>
            <div><div className="action-text-main">Clear chat</div><div className="action-text-sub">Start a new conversation</div></div>
            <span className="action-arrow">›</span>
          </button>
          <button className="quick-action-btn" onClick={() => logout()}>
            <div className="action-icon gray">↪️</div>
            <div><div className="action-text-main">Log out</div><div className="action-text-sub">Sign out from your account</div></div>
            <span className="action-arrow">›</span>
          </button>
        </div>

        <div className="sidebar-footer">Welfare Bot is here to support you 💙</div>
      </aside>

      <main className="main-panel">
        <ChatWindow
          title="Chat with Welfare Bot"
          subtitle="Your AI companion for well-being and support"
          messages={messages}
          onSend={handleSend}
          loading={loading || bootstrapping}
          error={error}
          language="auto"
          userInitial={userInitial}
        />
      </main>
    </div>
  );
}