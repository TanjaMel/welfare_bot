import { useCallback, useEffect, useMemo, useState } from "react";

interface UserRiskRow {
  user_id: number;
  name: string;
  latest_risk_level: string;
  latest_risk_score: number;
  trend: string;
  last_active: string | null;
  days_since_contact: number;
  alert: boolean;
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
  heatmap: {
    date: string;
    critical: number;
    high: number;
    medium: number;
    low: number;
  }[];
}

const API_BASE = "/api/v1";

const RISK_CONFIG: Record<
  string,
  { label: string; className: string; priority: number }
> = {
  critical: { label: "Critical", className: "admin-risk-critical", priority: 1 },
  high: { label: "High", className: "admin-risk-high", priority: 2 },
  medium: { label: "Medium", className: "admin-risk-medium", priority: 3 },
  low: { label: "Low", className: "admin-risk-low", priority: 4 },
  no_data: { label: "No data", className: "admin-risk-none", priority: 5 },
};

const TREND_LABEL: Record<string, string> = {
  improving: "Improving",
  worsening: "Worsening",
  stable: "Stable",
  no_data: "No trend",
};

const TREND_SYMBOL: Record<string, string> = {
  improving: "↑",
  worsening: "↓",
  stable: "→",
  no_data: "—",
};

const RISK_REASON: Record<string, string> = {
  critical: "Critical wellbeing signals detected. Immediate human follow-up is recommended.",
  high: "High-risk signals detected. The user may need support today.",
  medium: "Some concerns detected. Follow-up is recommended this week.",
  low: "No immediate concerns detected.",
  no_data: "No conversation data available yet.",
};

type FilterValue = "all" | "attention" | "critical" | "high" | "medium" | "low" | "no_data";

function RiskBadge({ level }: { level: string }) {
  const cfg = RISK_CONFIG[level] ?? RISK_CONFIG.no_data;

  return (
    <span className={`admin-risk-badge ${cfg.className}`}>
      <span className="admin-risk-dot" />
      {cfg.label}
    </span>
  );
}

function StatCard({
  label,
  value,
  sub,
  tone = "default",
}: {
  label: string;
  value: string | number;
  sub?: string;
  tone?: "default" | "danger" | "warning" | "success" | "neutral";
}) {
  return (
    <article className={`admin-stat-card ${tone}`}>
      <span className="admin-stat-label">{label}</span>
      <strong className="admin-stat-value">{value}</strong>
      {sub && <span className="admin-stat-sub">{sub}</span>}
    </article>
  );
}

function getActionText(user: UserRiskRow): string {
  if (user.latest_risk_level === "critical") return "Contact immediately";
  if (user.latest_risk_level === "high") return "Call today";
  if (user.days_since_contact >= 3) return "Schedule check-in";
  if (user.latest_risk_level === "medium") return "Monitor this week";
  return "No action needed";
}

function formatContactDays(days: number): string {
  if (days === 999) return "Never";
  if (days === 0) return "Today";
  if (days === 1) return "1 day";
  return `${days} days`;
}

export default function AdminDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedUser, setExpandedUser] = useState<number | null>(null);
  const [filter, setFilter] = useState<FilterValue>("attention");

  const fetchDashboard = useCallback(async () => {
    setRefreshing(true);
    setError(null);

    try {
      const token = localStorage.getItem("access_token");

      const response = await fetch(`${API_BASE}/admin/dashboard?days=7`, {
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      });

      if (!response.ok) {
        throw new Error(`Dashboard request failed: ${response.status}`);
      }

      const json = (await response.json()) as DashboardData;
      setData(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void fetchDashboard();
  }, [fetchDashboard]);

  const alertUsers = useMemo(() => {
    return data?.users.filter((user) => user.alert) ?? [];
  }, [data]);

  const filteredUsers = useMemo(() => {
    if (!data) return [];

    const users = [...data.users];

    const filtered =
      filter === "all"
        ? users
        : filter === "attention"
          ? users.filter((user) => user.alert)
          : users.filter((user) => user.latest_risk_level === filter);

    return filtered.sort((a, b) => {
      const aPriority = RISK_CONFIG[a.latest_risk_level]?.priority ?? 5;
      const bPriority = RISK_CONFIG[b.latest_risk_level]?.priority ?? 5;

      if (a.alert !== b.alert) return a.alert ? -1 : 1;
      if (aPriority !== bPriority) return aPriority - bPriority;

      return b.days_since_contact - a.days_since_contact;
    });
  }, [data, filter]);

  if (loading) {
    return (
      <section className="admin-dashboard">
        <div className="admin-state-card">
          <div className="admin-loading-pulse" />
          <h2>Loading dashboard</h2>
          <p>Preparing population-level wellbeing overview...</p>
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="admin-dashboard">
        <div className="admin-state-card error">
          <h2>Could not load dashboard</h2>
          <p>{error}</p>
          <button type="button" className="admin-primary-btn" onClick={() => void fetchDashboard()}>
            Try again
          </button>
        </div>
      </section>
    );
  }

  if (!data) {
    return (
      <section className="admin-dashboard">
        <div className="admin-state-card">
          <h2>No dashboard data</h2>
          <p>No population-level data is available yet.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="admin-dashboard">
      <header className="admin-hero">
        <div>
          <span className="admin-kicker">Care team overview</span>
          <h1>Population wellbeing</h1>
          <p>
            Monitor risk levels, recent contact and users who may need human follow-up.
          </p>
        </div>

        <div className="admin-hero-actions">
          <span className="admin-updated">Updated {data.generated_at}</span>
          <button
            type="button"
            className="admin-secondary-btn"
            onClick={() => void fetchDashboard()}
            disabled={refreshing}
          >
            {refreshing ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </header>

      <div className="admin-stats-grid">
        <StatCard
          label="Total users"
          value={data.summary.total_users}
          sub={`${data.summary.active_today} active today`}
          tone="neutral"
        />
        <StatCard
          label="Need attention"
          value={data.summary.users_needing_attention}
          sub="Follow-up recommended"
          tone={data.summary.users_needing_attention > 0 ? "danger" : "success"}
        />
        <StatCard
          label="Critical"
          value={data.summary.critical_count}
          sub="Immediate priority"
          tone="danger"
        />
        <StatCard
          label="High risk"
          value={data.summary.high_count}
          sub="Call today"
          tone="warning"
        />
        <StatCard
          label="Medium risk"
          value={data.summary.medium_count}
          sub="Monitor this week"
          tone="neutral"
        />
        <StatCard
          label="Avg wellbeing"
          value={
            data.summary.avg_wellbeing_score !== null
              ? `${data.summary.avg_wellbeing_score}%`
              : "—"
          }
          sub="7-day average"
          tone="success"
        />
      </div>

      {alertUsers.length > 0 && (
        <section className="admin-section">
          <div className="admin-section-header">
            <div>
              <span className="admin-section-kicker">Priority queue</span>
              <h2>Needs attention</h2>
            </div>
            <span className="admin-count-pill">{alertUsers.length} users</span>
          </div>

          <div className="admin-alert-list">
            {alertUsers.map((user) => {
              const expanded = expandedUser === user.user_id;

              return (
                <article
                  key={user.user_id}
                  className={`admin-alert-card ${expanded ? "expanded" : ""}`}
                >
                  <button
                    type="button"
                    className="admin-alert-main"
                    onClick={() =>
                      setExpandedUser(expanded ? null : user.user_id)
                    }
                  >
                    <div className="admin-user-main">
                      <div className="admin-user-avatar">
                        {user.name.charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <strong>{user.name}</strong>
                        <span>{RISK_REASON[user.latest_risk_level]}</span>
                      </div>
                    </div>

                    <div className="admin-alert-meta">
                      <RiskBadge level={user.latest_risk_level} />
                      <span className={`admin-trend ${user.trend}`}>
                        {TREND_SYMBOL[user.trend]} {TREND_LABEL[user.trend]}
                      </span>
                      <span className="admin-last-active">
                        Last active: {user.last_active || "Never"}
                      </span>
                      <span
                        className={`admin-contact-days ${
                          user.days_since_contact >= 2 ? "late" : "ok"
                        }`}
                      >
                        {formatContactDays(user.days_since_contact)}
                      </span>
                      <span className="admin-chevron">{expanded ? "▲" : "▼"}</span>
                    </div>
                  </button>

                  {expanded && (
                    <div className="admin-alert-details">
                      <div>
                        <span>Risk score</span>
                        <strong>{user.latest_risk_score}/10</strong>
                      </div>
                      <div>
                        <span>Trend</span>
                        <strong>{TREND_LABEL[user.trend]}</strong>
                      </div>
                      <div>
                        <span>Recommended action</span>
                        <strong>{getActionText(user)}</strong>
                      </div>
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        </section>
      )}

      <section className="admin-section">
        <div className="admin-section-header">
          <div>
            <span className="admin-section-kicker">User monitoring</span>
            <h2>All users</h2>
          </div>

          <div className="admin-filter-row">
            {[
              ["attention", "Needs attention"],
              ["all", "All"],
              ["critical", "Critical"],
              ["high", "High"],
              ["medium", "Medium"],
              ["low", "Low"],
              ["no_data", "No data"],
            ].map(([value, label]) => (
              <button
                key={value}
                type="button"
                className={`admin-filter-btn ${filter === value ? "active" : ""}`}
                onClick={() => setFilter(value as FilterValue)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="admin-table-card">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Risk</th>
                <th>Reason</th>
                <th>Trend</th>
                <th>Last active</th>
                <th>Contact</th>
                <th>Action</th>
              </tr>
            </thead>

            <tbody>
              {filteredUsers.map((user) => (
                <tr key={user.user_id} className={user.alert ? "needs-attention" : ""}>
                  <td>
                    <div className="admin-table-user">
                      <div className="admin-table-avatar">
                        {user.name.charAt(0).toUpperCase()}
                      </div>
                      <strong>{user.name}</strong>
                    </div>
                  </td>

                  <td>
                    <RiskBadge level={user.latest_risk_level} />
                  </td>

                  <td className="admin-reason-cell">
                    {RISK_REASON[user.latest_risk_level]}
                  </td>

                  <td>
                    <span className={`admin-trend ${user.trend}`}>
                      {TREND_SYMBOL[user.trend]} {TREND_LABEL[user.trend]}
                    </span>
                  </td>

                  <td>{user.last_active || "Never"}</td>

                  <td>
                    <span
                      className={`admin-contact-days ${
                        user.days_since_contact >= 2 ? "late" : "ok"
                      }`}
                    >
                      {formatContactDays(user.days_since_contact)}
                    </span>
                  </td>

                  <td>
                    <span className="admin-action-pill">{getActionText(user)}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {filteredUsers.length === 0 && (
            <div className="admin-empty-table">
              No users match this filter.
            </div>
          )}
        </div>
      </section>
    </section>
  );
}