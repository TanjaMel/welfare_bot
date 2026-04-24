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
import WellbeingPanel from "./components/WellbeingPanel";

const USER_ID_STORAGE_KEY = "welfare-bot-user-id";

type WellbeingInfo = {
  label: string;
  sub: string;
  cls: "none" | "low" | "medium" | "high" | "critical";
};
function AppLogo({ small = false }: { small?: boolean }) {
  return (
    <img
      src="/android-chrome-512x512.png"
      alt="Welfare Bot"
      className={`brand-logo-img ${small ? "small" : ""}`}
    />
  );
}

function getWellbeingInfo(riskLevel: string | undefined): WellbeingInfo {
  if (!riskLevel) {
    return {
      label: "No recent assessment",
      sub: "Start or continue the conversation.",
      cls: "none",
    };
  }

  switch (riskLevel.toLowerCase()) {
    case "low":
      return {
        label: "Stable condition",
        sub: "No immediate concerns detected.",
        cls: "low",
      };
    case "medium":
      return {
        label: "Needs closer follow-up",
        sub: "Some concerns were detected.",
        cls: "medium",
      };
    case "high":
      return {
        label: "Attention recommended",
        sub: "Support may be needed soon.",
        cls: "high",
      };
    case "critical":
      return {
        label: "Urgent attention needed",
        sub: "Immediate action may be required.",
        cls: "critical",
      };
    default:
      return {
        label: "No recent assessment",
        sub: "Start or continue the conversation.",
        cls: "none",
      };
  }
}

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

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(!!localStorage.getItem("access_token"));
  const [users, setUsers] = useState<User[]>([]);
  const [userId, setUserId] = useState<number | null>(null);
  const [userName, setUserName] = useState<string>("Loading...");
  const [_userLanguage, setUserLanguage] = useState<string>("fi");
  const [currentUserRole, setCurrentUserRole] = useState<string>("user");
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [riskAnalyses, setRiskAnalyses] = useState<RiskAnalysis[]>([]);
  const [loading, setLoading] = useState(false);
  const [bootstrapping, setBootstrapping] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<"chat" | "trends">("chat");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const latestRisk = useMemo(() => (riskAnalyses.length > 0 ? riskAnalyses[0] : null), [riskAnalyses]);
  const wellbeing = getWellbeingInfo(latestRisk?.risk_level);
  const userInitial = userName ? userName.charAt(0).toUpperCase() : "?";

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

  async function loadConversationData(id: number) {
    const [, riskResult] = await Promise.allSettled([Promise.resolve(), loadRiskAnalysis(id)]);

    if (riskResult.status === "rejected") {
      setRiskAnalyses([]);
    }

    try {
      const allMessages = await getMessages(id);
      const todayMessages = allMessages.filter(
        (m) => new Date(m.created_at).toDateString() === new Date().toDateString()
      );

      if (todayMessages.length === 0) {
        await startConversation(id);
        const refreshed = await getMessages(id);
        setMessages(refreshed);
      } else {
        setMessages(allMessages);
      }
    } catch (e) {
      console.warn("Could not load/start conversation:", e);
      setMessages([]);
    }
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

      let activeUser: User | null = null;

      if (currentUser.role === "admin") {
        const allUsers = await getUsers();
        setUsers(allUsers);

        const storedId = getStoredUserId();
        activeUser = storedId ? allUsers.find((u) => u.id === storedId) ?? allUsers[0] : allUsers[0];
      } else {
        setUsers([currentUser]);
        activeUser = currentUser;
      }

      if (!activeUser) {
        setError("No available user found.");
        setMessages([]);
        setRiskAnalyses([]);
        return;
      }

      applyUserMeta(activeUser);
      await loadConversationData(activeUser.id);
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

      setMessages((prev) => [
        ...prev,
        { id: now, role: "user", content: trimmed, created_at: new Date().toISOString() },
        { id: pendingAssistantId, role: "assistant", content: "", created_at: new Date().toISOString() },
      ]);

      await sendMessageStream({ user_id: userId, message: trimmed, language: "auto" }, (chunk) => {
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === pendingAssistantId ? { ...msg, content: msg.content + chunk } : msg
          )
        );
      });

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
          msg.id === pendingAssistantId ? { ...msg, content: msg.content || "Failed to send." } : msg
        )
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
    setActiveView("chat");
    setSidebarOpen(false);
    applyUserMeta(selected);
    await loadConversationData(selected.id);
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

  useEffect(() => {
    if (isAuthenticated) void bootstrap();
  }, [isAuthenticated]);

  if (!isAuthenticated) {
    return <LoginPage onSuccess={() => setIsAuthenticated(true)} />;
  }

  const timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  return (
    <div className="app-shell">
      <header className="top-app-bar">
        <div className="top-app-row">
          <div className="top-brand">
            <AppLogo />
            <div className="top-brand-copy">
              <span className="top-brand-name">Welfare Bot</span>
              <span className="top-brand-sub">Care. Support. Well-being.</span>
            </div>
          </div>

          <div className="top-user-card">
            <div className="top-user-avatar">{userInitial}</div>
            <div className="top-user-copy">
              <span className="top-user-name">{userName}</span>
              <span className="top-user-sub">Current user</span>
            </div>
          </div>
        </div>

        <div className="top-nav-row">
          <button
            type="button"
            className="top-menu-btn"
            aria-label="Open menu"
            onClick={() => setSidebarOpen((value) => !value)}
          >
            <svg viewBox="0 0 24 24" fill="none" width="20" height="20">
              <path d="M3 7H21" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              <path d="M3 12H21" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              <path d="M3 17H21" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>

          <div className="top-tabs" role="tablist" aria-label="Main navigation">
            <button
              type="button"
              role="tab"
              aria-selected={activeView === "chat"}
              className={`top-tab ${activeView === "chat" ? "active" : ""}`}
              onClick={() => setActiveView("chat")}
            >
              Chat
            </button>

            <button
              type="button"
              role="tab"
              aria-selected={activeView === "trends"}
              className={`top-tab ${activeView === "trends" ? "active" : ""}`}
              onClick={() => setActiveView("trends")}
            >
              Your wellbeing trends
            </button>
          </div>
        </div>
      </header>

      <div className="app-body">
        <aside className={`sidebar ${sidebarOpen ? "sidebar-open" : ""}`}>
          <div className="sidebar-brand">
            <AppLogo />
            <div className="sidebar-brand-copy">
              <h2>Welfare Bot</h2>
              <p>Care. Support. Well-being.</p>
            </div>
          </div>

          <div className="sidebar-profile-compact">
            <div className="profile-avatar">{userInitial}</div>
            <div className="profile-copy">
              <div className="profile-name">{userName}</div>
              <div className="profile-sub">Current user</div>
            </div>
          </div>

          {currentUserRole === "admin" && users.length > 1 && (
            <section className="sidebar-section">
              <h3 className="section-title">User selection</h3>
              <div className="sidebar-card">
                <label className="field-label" htmlFor="user-select">
                  Active user
                </label>
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
            </section>
          )}

          <section className="sidebar-section">
            <h3 className="section-title">Today&apos;s status</h3>
            <div className="sidebar-card wellbeing-card redesigned">
              <div className={`wellbeing-status-dot ${wellbeing.cls}`} />
              <div className="wellbeing-copy">
                <div className="wellbeing-text-main">{wellbeing.label}</div>
                <div className="wellbeing-text-sub">{wellbeing.sub}</div>

                {latestRisk?.reason && (
                  <div className="risk-meta-block">
                    <span className="risk-meta-label">Reason</span>
                    <p>{latestRisk.reason}</p>
                  </div>
                )}

                {latestRisk?.suggested_action && (
                  <div className="risk-meta-block">
                    <span className="risk-meta-label">Suggested action</span>
                    <p>{latestRisk.suggested_action}</p>
                  </div>
                )}

                {latestRisk?.follow_up_question && (
                  <div className="risk-meta-block">
                    <span className="risk-meta-label">Follow-up</span>
                    <p>{latestRisk.follow_up_question}</p>
                  </div>
                )}

                {(latestRisk?.needs_family_notification || latestRisk?.should_alert_family) && (
                  <div className="risk-notice">Family notification recommended</div>
                )}

                <div className="wellbeing-time">Checked at {timeStr}</div>
              </div>
            </div>
          </section>

          <section className="sidebar-section">
            <h3 className="section-title">Care contact</h3>
            {userId && <CareContactForm userId={userId} />}
          </section>

          <section className="sidebar-section">
            <h3 className="section-title">Quick actions</h3>
            <div className="actions-list">
              <button
                className="action-item"
                onClick={() => void handleRefresh()}
                disabled={!userId || loading || bootstrapping}
              >
                <span className="action-icon blue">
                  <svg viewBox="0 0 24 24" fill="none">
                    <path
                      d="M20 12A8 8 0 1 1 17.657 6.343"
                      stroke="currentColor"
                      strokeWidth="1.9"
                      strokeLinecap="round"
                    />
                    <path
                      d="M20 5V10H15"
                      stroke="currentColor"
                      strokeWidth="1.9"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </span>
                <span>
                  <strong>Refresh conversation</strong>
                  <small>Get the latest updates</small>
                </span>
                <span className="action-arrow">›</span>
              </button>

              <button
                className="action-item danger"
                onClick={() => void handleClearChat()}
                disabled={!userId || loading}
              >
                <span className="action-icon red">
                  <svg viewBox="0 0 24 24" fill="none">
                    <path d="M5 7H19" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" />
                    <path d="M10 11V17" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" />
                    <path d="M14 11V17" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" />
                    <path
                      d="M8 7L8.6 19H15.4L16 7"
                      stroke="currentColor"
                      strokeWidth="1.9"
                      strokeLinejoin="round"
                    />
                    <path
                      d="M10 7V5H14V7"
                      stroke="currentColor"
                      strokeWidth="1.9"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </span>
                <span>
                  <strong>Clear chat</strong>
                  <small>Start a new conversation</small>
                </span>
                <span className="action-arrow">›</span>
              </button>

              <button className="action-item" onClick={() => logout()}>
                <span className="action-icon gray">
                  <svg viewBox="0 0 24 24" fill="none">
                    <path
                      d="M10 6H6.8C5.806 6 5 6.806 5 7.8V16.2C5 17.194 5.806 18 6.8 18H10"
                      stroke="currentColor"
                      strokeWidth="1.9"
                      strokeLinecap="round"
                    />
                    <path
                      d="M14 8L18 12L14 16"
                      stroke="currentColor"
                      strokeWidth="1.9"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                    <path d="M18 12H10" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" />
                  </svg>
                </span>
                <span>
                  <strong>Log out</strong>
                  <small>Sign out from your account</small>
                </span>
                <span className="action-arrow">›</span>
              </button>
            </div>
          </section>

          <div className="sidebar-footer">Reliable conversational support</div>
        </aside>

        {sidebarOpen && <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />}

        <main className="main-panel">
          <div className="main-view-tabs" role="tablist" aria-label="Main navigation">
            <button
              type="button"
              role="tab"
              aria-selected={activeView === "chat"}
              className={activeView === "chat" ? "active" : ""}
              onClick={() => setActiveView("chat")}
            >
              Chat
            </button>

            <button
              type="button"
              role="tab"
              aria-selected={activeView === "trends"}
              className={activeView === "trends" ? "active" : ""}
              onClick={() => setActiveView("trends")}
            >
              Your wellbeing trends
            </button>
          </div>

          {activeView === "trends" && userId ? (
            <WellbeingPanel userId={userId} />
          ) : (
            <ChatWindow
              title="Welfare Bot Chat"
              subtitle="Reliable conversational support for everyday well-being"
              messages={messages}
              onSend={handleSend}
              loading={loading || bootstrapping}
              error={error}
              language="auto"
              userInitial={userInitial}
            />
          )}
        </main>
      </div>
    </div>
  );
}