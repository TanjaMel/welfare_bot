import { useState, useEffect, useCallback } from "react";

interface UserRiskRow {
  user_id: number;
  name: string;
  latest_risk_level: string;
  latest_risk_score: number;
  trend: string;
  last_active: string | null;
  days_since_contact: number;
  alert: boolean;
  alert_reason: string;
}

interface PopulationSummary {
  total_users: number;
  active_today: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  no_data_count: number;
  avg_wellbeing_score: number | null;
  users_needing_attention: number;
}

interface DashboardData {
  generated_at: string;
  summary: PopulationSummary;
  users: UserRiskRow[];
  heatmap: { date: string; critical: number; high: number; medium: number; low: number }[];
}

interface PredictionRow {
  user_id: number;
  name: string;
  predicted_score: number | null;
  current_score: number | null;
  trend_direction: string;
  confidence: string;
  days_of_data: number;
  alert: boolean;
  message: string;
}

interface PopulationPredictions {
  generated_at: string;
  total_users: number;
  declining_count: number;
  stable_count: number;
  improving_count: number;
  predictions: PredictionRow[];
}

interface AccuracyMetrics {
  total_alerts: number;
  feedback_received: number;
  feedback_coverage_pct: number;
  true_positives: number;
  false_positives: number;
  precision: number | null;
  interpretation: string;
  recommendation: string;
}

const API_BASE = "/api/v1";

const AVATAR_COLORS = [
  "#4F7DF3", "#7C3AED", "#059669", "#DC2626", "#D97706",
  "#0891B2", "#BE185D", "#65A30D", "#9333EA", "#0284C7",
];

function getAvatarColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

function Avatar({ name }: { name: string }) {
  const color = getAvatarColor(name);
  return (
    <div className="admin-user-avatar" style={{ background: color }}>
      {name.charAt(0).toUpperCase()}
    </div>
  );
}

function RiskBadge({ level }: { level: string }) {
  const cls = `admin-risk-badge admin-risk-${level === "no_data" ? "none" : level}`;
  const labels: Record<string, string> = {
    critical: "Critical", high: "High", medium: "Medium", low: "Low", no_data: "No data",
  };
  return (
    <span className={cls}>
      <span className="admin-risk-dot" />
      {labels[level] ?? level}
    </span>
  );
}

function TrendBadge({ trend }: { trend: string }) {
  const icons: Record<string, string> = {
    improving: "↑", worsening: "↓", stable: "→", no_data: "—", declining: "↓",
  };
  const labels: Record<string, string> = {
    improving: "Improving", worsening: "Worsening", stable: "Stable", no_data: "No trend", declining: "Declining",
  };
  const colorMap: Record<string, string> = {
    improving: "improving", worsening: "worsening", declining: "worsening", stable: "stable", no_data: "no_data",
  };
  return (
    <span className={`admin-trend ${colorMap[trend] ?? "no_data"}`}>
      {icons[trend] ?? "—"} {labels[trend] ?? trend}
    </span>
  );
}

function ContactDays({ days }: { days: number }) {
  if (days === 999) return <span className="admin-contact-days late">Never</span>;
  const cls = days >= 3 ? "late" : "ok";
  return <span className={`admin-contact-days ${cls}`}>{days}d</span>;
}

type TabType = "overview" | "predictions" | "accuracy";

export default function AdminDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [predictions, setPredictions] = useState<PopulationPredictions | null>(null);
  const [accuracy, setAccuracy] = useState<AccuracyMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState(7);
  const [filter, setFilter] = useState("all");
  const [expandedUser, setExpandedUser] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>("overview");
  const [feedbackSent, setFeedbackSent] = useState<Record<number, boolean>>({});

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem("access_token");
      const headers: HeadersInit = token
  ? { Authorization: `Bearer ${token}` }
  : {};
      const [dashRes, predRes, accRes] = await Promise.all([
        fetch(`${API_BASE}/admin/dashboard?days=${period}`, { headers }),
        fetch(`${API_BASE}/admin/predictions`, { headers }),
        fetch(`${API_BASE}/admin/feedback/accuracy`, { headers }),
      ]);
      
      if (!dashRes.ok) throw new Error(`Dashboard error: ${dashRes.status}`);
      setData(await dashRes.json());
      if (predRes.ok) setPredictions(await predRes.json());
      if (accRes.ok) setAccuracy(await accRes.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  }, [period]);

  useEffect(() => { void fetchDashboard(); }, [fetchDashboard]);

  async function submitFeedback(riskAnalysisId: number, wasHelpful: boolean) {
    try {
      const token = localStorage.getItem("access_token");
      await fetch(`${API_BASE}/admin/feedback`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ risk_analysis_id: riskAnalysisId, was_helpful: wasHelpful }),
      });
      setFeedbackSent(prev => ({ ...prev, [riskAnalysisId]: true }));
    } catch {
      console.warn("Feedback submission failed");
    }
  }

  const alertUsers = data?.users.filter(u => u.alert) ?? [];
  const filteredUsers = data ? (
    filter === "all" ? data.users :
    filter === "alert" ? alertUsers :
    data.users.filter(u => u.latest_risk_level === filter)
  ) : [];
  const s = data?.summary;

  return (
    <div className="admin-dashboard">

      {/* Hero */}
      <div className="admin-hero">
        <div>
          <span className="admin-kicker">Care Team Overview</span>
          <h1>Population wellbeing</h1>
          <p>Monitor risk levels, recent contact and users who may need human follow-up.</p>
        </div>
        <div className="admin-hero-actions">
          <span className="admin-updated">Updated {data?.generated_at ?? "—"}</span>
          <div style={{ display: "flex", gap: 8 }}>
            {[7, 14, 30].map(d => (
              <button key={d} className={`admin-filter-btn ${period === d ? "active" : ""}`} onClick={() => setPeriod(d)}>
                {d}d
              </button>
            ))}
          </div>
          <button className="admin-secondary-btn" onClick={fetchDashboard} disabled={loading}>
            {loading ? "Loading…" : "↻ Refresh"}
          </button>
        </div>
      </div>

      {/* Tab navigation */}
      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        {(["overview", "predictions", "accuracy"] as TabType[]).map(tab => (
          <button
            key={tab}
            className={`admin-filter-btn ${activeTab === tab ? "active" : ""}`}
            onClick={() => setActiveTab(tab)}
            style={{ padding: "10px 18px", fontSize: 13 }}
          >
            {tab === "overview" ? "Overview" :
             tab === "predictions" ? `Predictions ${predictions?.declining_count ? `(${predictions.declining_count} declining)` : ""}` :
             `ML Accuracy ${accuracy?.precision != null ? `(${accuracy.precision}%)` : ""}`}
          </button>
        ))}
      </div>

      {error && (
        <div className="admin-state-card error" style={{ marginBottom: 20, padding: "16px 20px", textAlign: "left" }}>
          <p>{error}</p>
        </div>
      )}

      {/* ── OVERVIEW TAB ── */}
      {activeTab === "overview" && s && (
        <>
          <div className="admin-stats-grid">
            <div className="admin-stat-card neutral">
              <span className="admin-stat-label">Total users</span>
              <span className="admin-stat-value">{s.total_users}</span>
              <span className="admin-stat-sub">{s.active_today} active today</span>
            </div>
            <div className={`admin-stat-card ${s.users_needing_attention > 0 ? "danger" : "success"}`}>
              <span className="admin-stat-label">Need attention</span>
              <span className="admin-stat-value">{s.users_needing_attention}</span>
              <span className="admin-stat-sub">{s.users_needing_attention > 0 ? "Follow-up recommended" : "All clear"}</span>
            </div>
            <div className="admin-stat-card danger">
              <span className="admin-stat-label">Critical</span>
              <span className="admin-stat-value">{s.critical_count}</span>
              <span className="admin-stat-sub">Immediate priority</span>
            </div>
            <div className="admin-stat-card warning">
              <span className="admin-stat-label">High risk</span>
              <span className="admin-stat-value">{s.high_count}</span>
              <span className="admin-stat-sub">Call today</span>
            </div>
            <div className="admin-stat-card warning">
              <span className="admin-stat-label">Medium risk</span>
              <span className="admin-stat-value">{s.medium_count}</span>
              <span className="admin-stat-sub">Monitor this week</span>
            </div>
            <div className="admin-stat-card success">
              <span className="admin-stat-label">Avg wellbeing</span>
              <span className="admin-stat-value">{s.avg_wellbeing_score !== null ? `${s.avg_wellbeing_score}%` : "—"}</span>
              <span className="admin-stat-sub">7-day average</span>
            </div>
          </div>

          {alertUsers.length > 0 ? (
            <div className="admin-section" style={{ marginBottom: 22 }}>
              <div className="admin-section-header">
                <div>
                  <span className="admin-section-kicker">Priority Queue</span>
                  <h2>Needs attention</h2>
                </div>
                <span className="admin-count-pill">{alertUsers.length} users</span>
              </div>
              <div className="admin-alert-list">
                {alertUsers.map(u => (
                  <div key={u.user_id} className={`admin-alert-card ${expandedUser === u.user_id ? "expanded" : ""}`}>
                    <button className="admin-alert-main" onClick={() => setExpandedUser(expandedUser === u.user_id ? null : u.user_id)}>
                      <div className="admin-user-main">
                        <Avatar name={u.name} />
                        <div>
                          <strong>{u.name}</strong>
                          <span>{u.alert_reason}</span>
                        </div>
                      </div>
                      <div className="admin-alert-meta">
                        <RiskBadge level={u.latest_risk_level} />
                        <TrendBadge trend={u.trend} />
                        <span className="admin-last-active">Last active: {u.last_active ?? "Never"}</span>
                        <ContactDays days={u.days_since_contact} />
                        <span className="admin-chevron">{expandedUser === u.user_id ? "▲" : "▼"}</span>
                      </div>
                    </button>

                    {expandedUser === u.user_id && (
                      <div className="admin-alert-details">
                        <div>
                          <span>Risk level</span>
                          <strong><RiskBadge level={u.latest_risk_level} /></strong>
                        </div>
                        <div>
                          <span>Trend</span>
                          <strong><TrendBadge trend={u.trend} /></strong>
                        </div>
                        <div>
                          <span>Days since contact</span>
                          <strong>{u.days_since_contact === 999 ? "Never contacted" : `${u.days_since_contact} days`}</strong>
                        </div>
                        <div>
                          <span>Recommended action</span>
                          <strong>
                            {u.latest_risk_level === "critical" ? "Contact immediately" :
                             u.latest_risk_level === "high" ? "Call today" :
                             u.days_since_contact >= 5 ? "Schedule check-in call" : "Monitor closely"}
                          </strong>
                        </div>
                        <div style={{ gridColumn: "1 / -1" }}>
                          <span>Was this alert helpful?</span>
                          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                            {feedbackSent[u.user_id] ? (
                              <span style={{ fontSize: 13, color: "var(--success)", fontWeight: 600 }}>✓ Feedback recorded — thank you</span>
                            ) : (
                              <>
                                <button
                                  className="admin-secondary-btn"
                                  style={{ padding: "6px 14px", fontSize: 12 }}
                                  onClick={() => void submitFeedback(u.user_id, true)}
                                >
                                  👍 Helpful
                                </button>
                                <button
                                  className="admin-secondary-btn"
                                  style={{ padding: "6px 14px", fontSize: 12, color: "var(--danger)", borderColor: "var(--danger)" }}
                                  onClick={() => void submitFeedback(u.user_id, false)}
                                >
                                  👎 False alarm
                                </button>
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="admin-state-card" style={{ marginBottom: 22, padding: "24px 30px", textAlign: "left", display: "flex", alignItems: "center", gap: 16 }}>
              <span style={{ fontSize: 24, color: "var(--success)" }}>✓</span>
              <div>
                <h2 style={{ color: "var(--success)", fontSize: 16 }}>All users within normal parameters</h2>
                <p style={{ marginTop: 4, fontSize: 13, color: "var(--text-soft)" }}>No urgent follow-ups needed today.</p>
              </div>
            </div>
          )}

          <div className="admin-table-card">
            <div className="admin-section-header" style={{ padding: "16px 20px", borderBottom: "1px solid var(--border)", margin: 0 }}>
              <div>
                <span className="admin-section-kicker" style={{ marginBottom: 2 }}>User Monitoring</span>
                <span style={{ fontWeight: 700, fontSize: 16, color: "var(--primary-dark)" }}>All users</span>
              </div>
              <div className="admin-filter-row">
                {["all", "alert", "critical", "high", "medium", "low", "no_data"].map(f => (
                  <button key={f} className={`admin-filter-btn ${filter === f ? "active" : ""}`} onClick={() => setFilter(f)}>
                    {f === "alert" ? "Needs attention" : f === "no_data" ? "No data" : f.charAt(0).toUpperCase() + f.slice(1)}
                  </button>
                ))}
              </div>
            </div>
            <div style={{ overflowX: "auto" }}>
              <table className="admin-table">
                <thead>
                  <tr>{["Name", "Risk", "Reason", "Trend", "Last active", "Days"].map(h => <th key={h}>{h}</th>)}</tr>
                </thead>
                <tbody>
                  {filteredUsers.length === 0 ? (
                    <tr><td colSpan={6} className="admin-empty-table">No users match this filter.</td></tr>
                  ) : filteredUsers.map(u => (
                    <tr key={u.user_id} className={u.alert ? "needs-attention" : ""}>
                      <td><div className="admin-table-user"><Avatar name={u.name} /><strong>{u.name}</strong></div></td>
                      <td><RiskBadge level={u.latest_risk_level} /></td>
                      <td className="admin-reason-cell">{u.alert_reason || <span style={{ color: "var(--text-muted)" }}>No immediate concerns.</span>}</td>
                      <td><TrendBadge trend={u.trend} /></td>
                      <td className="admin-last-active">{u.last_active ?? "—"}</td>
                      <td><ContactDays days={u.days_since_contact} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* ── PREDICTIONS TAB ── */}
      {activeTab === "predictions" && (
        <div className="admin-section">
          <div className="admin-section-header">
            <div>
              <span className="admin-section-kicker">ML Predictions</span>
              <h2>Tomorrow's wellbeing forecast</h2>
            </div>
            {predictions && (
              <div style={{ display: "flex", gap: 12, fontSize: 13 }}>
                <span style={{ color: "var(--danger)", fontWeight: 700 }}>↓ {predictions.declining_count} declining</span>
                <span style={{ color: "var(--text-muted)" }}>→ {predictions.stable_count} stable</span>
                <span style={{ color: "var(--success)", fontWeight: 700 }}>↑ {predictions.improving_count} improving</span>
              </div>
            )}
          </div>

          {!predictions ? (
            <p style={{ color: "var(--text-soft)", fontSize: 14 }}>Loading predictions…</p>
          ) : (
            <table className="admin-table">
              <thead>
                <tr>{["Name", "Current score", "Predicted tomorrow", "Trend", "Confidence", "Alert", "Message"].map(h => <th key={h}>{h}</th>)}</tr>
              </thead>
              <tbody>
                {predictions.predictions.map(p => (
                  <tr key={p.user_id} className={p.alert ? "needs-attention" : ""}>
                    <td><div className="admin-table-user"><Avatar name={p.name} /><strong>{p.name}</strong></div></td>
                    <td style={{ fontWeight: 600 }}>{p.current_score != null ? `${p.current_score}%` : "—"}</td>
                    <td style={{ fontWeight: 600, color: p.trend_direction === "declining" ? "var(--danger)" : p.trend_direction === "improving" ? "var(--success)" : "var(--text)" }}>
                      {p.predicted_score != null ? `${p.predicted_score}%` : "—"}
                    </td>
                    <td><TrendBadge trend={p.trend_direction} /></td>
                    <td style={{ fontSize: 12, color: "var(--text-muted)", textTransform: "capitalize" }}>{p.confidence}</td>
                    <td>{p.alert ? <span style={{ color: "var(--danger)", fontWeight: 700 }}>⚠ Yes</span> : <span style={{ color: "var(--success)" }}>✓ No</span>}</td>
                    <td style={{ fontSize: 12, color: "var(--text-soft)", maxWidth: 220 }}>{p.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ── ACCURACY TAB ── */}
      {activeTab === "accuracy" && (
        <div className="admin-section">
          <div className="admin-section-header">
            <div>
              <span className="admin-section-kicker">ML Accuracy</span>
              <h2>Alert precision monitoring</h2>
            </div>
          </div>

          {!accuracy ? (
            <p style={{ color: "var(--text-soft)", fontSize: 14 }}>Loading accuracy metrics…</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
              <div className="admin-stats-grid" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
                <div className="admin-stat-card neutral">
                  <span className="admin-stat-label">Total alerts</span>
                  <span className="admin-stat-value">{accuracy.total_alerts}</span>
                  <span className="admin-stat-sub">High + Critical</span>
                </div>
                <div className="admin-stat-card neutral">
                  <span className="admin-stat-label">Feedback received</span>
                  <span className="admin-stat-value">{accuracy.feedback_received}</span>
                  <span className="admin-stat-sub">{accuracy.feedback_coverage_pct}% coverage</span>
                </div>
                <div className="admin-stat-card success">
                  <span className="admin-stat-label">True positives</span>
                  <span className="admin-stat-value">{accuracy.true_positives}</span>
                  <span className="admin-stat-sub">Helpful alerts</span>
                </div>
                <div className="admin-stat-card danger">
                  <span className="admin-stat-label">False alarms</span>
                  <span className="admin-stat-value">{accuracy.false_positives}</span>
                  <span className="admin-stat-sub">Unnecessary alerts</span>
                </div>
              </div>

              <div className="admin-alert-card" style={{ background: "white", borderColor: "var(--border)" }}>
                <div style={{ padding: "20px 24px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                    <strong style={{ fontSize: 15, color: "var(--primary-dark)" }}>Precision</strong>
                    <span style={{ fontSize: 28, fontWeight: 800, color: accuracy.precision != null && accuracy.precision >= 80 ? "var(--success)" : accuracy.precision != null && accuracy.precision >= 60 ? "var(--warning)" : "var(--danger)" }}>
                      {accuracy.precision != null ? `${accuracy.precision}%` : "—"}
                    </span>
                  </div>
                  <p style={{ fontSize: 14, color: "var(--text-soft)", marginBottom: 8 }}>{accuracy.interpretation}</p>
                  <p style={{ fontSize: 13, color: "var(--text-muted)", fontStyle: "italic" }}>{accuracy.recommendation}</p>
                  {accuracy.feedback_received < 5 && (
                    <p style={{ marginTop: 12, fontSize: 13, color: "var(--warning)", fontWeight: 600 }}>
                      ⚠ Need at least 5 feedback items to calculate precision. Currently: {accuracy.feedback_received}.
                      Use the 👍/👎 buttons in the Overview tab to rate alerts.
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {loading && !data && (
        <div className="admin-state-card">
          <div className="admin-loading-pulse" />
          <h2>Loading dashboard…</h2>
          <p>Fetching population data</p>
        </div>
      )}
    </div>
  );
}
