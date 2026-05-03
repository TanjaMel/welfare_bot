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
    improving: "↑", worsening: "↓", stable: "→", no_data: "—",
  };
  const labels: Record<string, string> = {
    improving: "Improving", worsening: "Worsening", stable: "Stable", no_data: "No trend",
  };
  return (
    <span className={`admin-trend ${trend}`}>
      {icons[trend] ?? "—"} {labels[trend] ?? trend}
    </span>
  );
}

function ContactDays({ days }: { days: number }) {
  if (days === 999) return <span className="admin-contact-days late">Never</span>;
  const cls = days >= 3 ? "late" : "ok";
  return <span className={`admin-contact-days ${cls}`}>{days}d</span>;
}

export default function AdminDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState(7);
  const [filter, setFilter] = useState("all");
  const [expandedUser, setExpandedUser] = useState<number | null>(null);

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem("access_token");
      const res = await fetch(`${API_BASE}/admin/dashboard?days=${period}`, {
        headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      });
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      setData(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  }, [period]);

  useEffect(() => { void fetchDashboard(); }, [fetchDashboard]);

  const alertUsers = data?.users.filter(u => u.alert) ?? [];
  const filteredUsers = data ? (
    filter === "all" ? data.users :
    filter === "alert" ? alertUsers :
    data.users.filter(u => u.latest_risk_level === filter)
  ) : [];

  const s = data?.summary;

  return (
    <div className="admin-dashboard">

      {/* Hero header */}
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
              <button
                key={d}
                className={`admin-filter-btn ${period === d ? "active" : ""}`}
                onClick={() => setPeriod(d)}
              >
                {d}d
              </button>
            ))}
          </div>
          <button className="admin-secondary-btn" onClick={fetchDashboard} disabled={loading}>
            {loading ? "Loading…" : "↻ Refresh"}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="admin-state-card error" style={{ marginBottom: 20, padding: "16px 20px", textAlign: "left" }}>
          <p>{error}</p>
        </div>
      )}

      {s && (
        <>
          {/* Stats grid */}
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
              <span className="admin-stat-value">
                {s.avg_wellbeing_score !== null ? `${s.avg_wellbeing_score}%` : "—"}
              </span>
              <span className="admin-stat-sub">7-day average</span>
            </div>
          </div>

          {/* Priority queue */}
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
                  <div
                    key={u.user_id}
                    className={`admin-alert-card ${expandedUser === u.user_id ? "expanded" : ""}`}
                  >
                    <button
                      className="admin-alert-main"
                      onClick={() => setExpandedUser(expandedUser === u.user_id ? null : u.user_id)}
                    >
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
                        <span className="admin-last-active">
                          Last active: {u.last_active ?? "Never"}
                        </span>
                        <ContactDays days={u.days_since_contact} />
                        <span className="admin-chevron">
                          {expandedUser === u.user_id ? "▲" : "▼"}
                        </span>
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
                          <strong>
                            {u.days_since_contact === 999 ? "Never contacted" : `${u.days_since_contact} days`}
                          </strong>
                        </div>
                        <div>
                          <span>Recommended action</span>
                          <strong>
                            {u.latest_risk_level === "critical" ? "Contact immediately" :
                             u.latest_risk_level === "high" ? "Call today" :
                             u.days_since_contact >= 5 ? "Schedule check-in call" :
                             "Monitor closely"}
                          </strong>
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

          {/* All users table */}
          <div className="admin-table-card">
            <div className="admin-section-header" style={{ padding: "16px 20px", borderBottom: "1px solid var(--border)", margin: 0 }}>
              <div>
                <span className="admin-section-kicker" style={{ marginBottom: 2 }}>User Monitoring</span>
                <span style={{ fontWeight: 700, fontSize: 16, color: "var(--primary-dark)" }}>All users</span>
              </div>
              <div className="admin-filter-row">
                {["all", "alert", "critical", "high", "medium", "low", "no_data"].map(f => (
                  <button
                    key={f}
                    className={`admin-filter-btn ${filter === f ? "active" : ""}`}
                    onClick={() => setFilter(f)}
                  >
                    {f === "alert" ? "Needs attention" : f === "no_data" ? "No data" : f.charAt(0).toUpperCase() + f.slice(1)}
                  </button>
                ))}
              </div>
            </div>

            <div style={{ overflowX: "auto" }}>
              <table className="admin-table">
                <thead>
                  <tr>
                    {["Name", "Risk", "Reason", "Trend", "Last active", "Days"].map(h => (
                      <th key={h}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredUsers.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="admin-empty-table">No users match this filter.</td>
                    </tr>
                  ) : filteredUsers.map(u => (
                    <tr key={u.user_id} className={u.alert ? "needs-attention" : ""}>
                      <td>
                        <div className="admin-table-user">
                          <Avatar name={u.name} />
                          <strong>{u.name}</strong>
                        </div>
                      </td>
                      <td><RiskBadge level={u.latest_risk_level} /></td>
                      <td className="admin-reason-cell">
                        {u.alert_reason || <span style={{ color: "var(--text-muted)" }}>No immediate concerns.</span>}
                      </td>
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
