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

const RISK_CONFIG: Record<string, { label: string; color: string; bg: string; border: string }> = {
  critical: { label: "Critical",  color: "#dc2626", bg: "#fef2f2", border: "#fca5a5" },
  high:     { label: "High",      color: "#ea580c", bg: "#fff7ed", border: "#fdba74" },
  medium:   { label: "Medium",    color: "#ca8a04", bg: "#fefce8", border: "#fde047" },
  low:      { label: "Low",       color: "#16a34a", bg: "#f0fdf4", border: "#86efac" },
  no_data:  { label: "No data",   color: "#6b7280", bg: "#f9fafb", border: "#d1d5db" },
};

const TREND_CONFIG: Record<string, { icon: string; label: string; color: string }> = {
  improving: { icon: "↑", label: "Improving", color: "#16a34a" },
  worsening: { icon: "↓", label: "Worsening", color: "#dc2626" },
  stable:    { icon: "→", label: "Stable",    color: "#6b7280" },
  no_data:   { icon: "—", label: "No trend",  color: "#9ca3af" },
};

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
  const initial = name.charAt(0).toUpperCase();
  return (
    <div style={{
      width: 40, height: 40, borderRadius: "50%",
      background: color, color: "#fff",
      display: "flex", alignItems: "center", justifyContent: "center",
      fontSize: 16, fontWeight: 700, flexShrink: 0,
    }}>
      {initial}
    </div>
  );
}

function RiskBadge({ level }: { level: string }) {
  const cfg = RISK_CONFIG[level] || RISK_CONFIG.no_data;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      padding: "2px 10px", borderRadius: 20, fontSize: 12, fontWeight: 600,
      background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.border}`,
    }}>
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: cfg.color }} />
      {cfg.label}
    </span>
  );
}

function TrendBadge({ trend }: { trend: string }) {
  const cfg = TREND_CONFIG[trend] || TREND_CONFIG.no_data;
  return (
    <span style={{ color: cfg.color, fontWeight: 600, fontSize: 13, display: "flex", alignItems: "center", gap: 4 }}>
      <span style={{ fontSize: 16 }}>{cfg.icon}</span>
      <span style={{ fontSize: 11, color: "#9ca3af" }}>{cfg.label}</span>
    </span>
  );
}

function StatCard({ label: title, value, sub, accent }: {
  label: string; value: string | number; sub?: string; accent?: string
}) {
  return (
    <div style={{
      background: "#fff", borderRadius: 12, padding: "18px 20px",
      border: "1px solid #e5e7eb",
      borderTop: `3px solid ${accent || "#e5e7eb"}`,
    }}>
      <div style={{ fontSize: 12, color: "#6b7280", fontWeight: 500, marginBottom: 4 }}>{title}</div>
      <div style={{ fontSize: 26, fontWeight: 700, color: accent || "#111827", lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 4 }}>{sub}</div>}
    </div>
  );
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

  return (
    <div style={{ padding: "24px 28px", maxWidth: 1100, margin: "0 auto", fontFamily: "'DM Sans', 'Segoe UI', sans-serif", background: "#f8fafc", minHeight: "100vh" }}>

      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: "#6b7280", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 4 }}>
          Care Team Overview
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: 12 }}>
          <div>
            <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0, color: "#111827" }}>Population wellbeing</h1>
            <p style={{ fontSize: 13, color: "#6b7280", margin: "4px 0 0" }}>
              Monitor risk levels, recent contact and users who may need human follow-up.
            </p>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span style={{ fontSize: 11, color: "#9ca3af" }}>Updated {data?.generated_at}</span>
            {[7, 14, 30].map(d => (
              <button key={d} onClick={() => setPeriod(d)} style={{
                padding: "4px 12px", borderRadius: 6, border: "none",
                background: period === d ? "#111827" : "#e5e7eb",
                color: period === d ? "#fff" : "#6b7280",
                fontSize: 12, fontWeight: period === d ? 600 : 400, cursor: "pointer",
              }}>{d}d</button>
            ))}
            <button onClick={fetchDashboard} disabled={loading} style={{
              padding: "6px 14px", borderRadius: 8, border: "1px solid #e5e7eb",
              background: "#fff", fontSize: 12, cursor: "pointer", color: "#374151",
            }}>
              {loading ? "Loading…" : "↻ Refresh"}
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div style={{ background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: 8, padding: "12px 16px", color: "#dc2626", fontSize: 13, marginBottom: 20 }}>
          {error}
        </div>
      )}

      {data && (
        <>
          {/* Summary cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 12, marginBottom: 24 }}>
            <StatCard label="Total users" value={data.summary.total_users} sub={`${data.summary.active_today} active today`} />
            <StatCard label="Need attention" value={data.summary.users_needing_attention}
              accent={data.summary.users_needing_attention > 0 ? "#dc2626" : "#16a34a"}
              sub={data.summary.users_needing_attention > 0 ? "Follow-up recommended" : "All clear"} />
            <StatCard label="Critical" value={data.summary.critical_count} accent="#dc2626" sub="Immediate priority" />
            <StatCard label="High risk" value={data.summary.high_count} accent="#ea580c" sub="Call today" />
            <StatCard label="Medium risk" value={data.summary.medium_count} accent="#ca8a04" sub="Monitor this week" />
            <StatCard label="Avg wellbeing" value={data.summary.avg_wellbeing_score !== null ? `${data.summary.avg_wellbeing_score}%` : "—"}
              accent="#16a34a" sub="7-day average" />
          </div>

          {/* Priority queue */}
          {alertUsers.length > 0 && (
            <div style={{ marginBottom: 28 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <div>
                  <div style={{ fontSize: 11, fontWeight: 600, color: "#dc2626", letterSpacing: "0.1em", textTransform: "uppercase" }}>Priority Queue</div>
                  <h2 style={{ fontSize: 18, fontWeight: 700, color: "#111827", margin: "2px 0 0" }}>Needs attention</h2>
                </div>
                <span style={{ background: "#fef2f2", color: "#dc2626", border: "1px solid #fca5a5", padding: "2px 10px", borderRadius: 20, fontSize: 12, fontWeight: 600 }}>
                  {alertUsers.length} users
                </span>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {alertUsers.map(u => (
                  <div key={u.user_id}
                    onClick={() => setExpandedUser(expandedUser === u.user_id ? null : u.user_id)}
                    style={{
                      background: "#fff", border: "1px solid #e5e7eb",
                      borderLeft: "3px solid #ea580c",
                      borderRadius: 10, padding: "14px 16px", cursor: "pointer",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                      <Avatar name={u.name} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontWeight: 600, color: "#111827", fontSize: 14 }}>{u.name}</div>
                        <div style={{ fontSize: 12, color: "#6b7280", marginTop: 2 }}>{u.alert_reason}</div>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
                        <RiskBadge level={u.latest_risk_level} />
                        <TrendBadge trend={u.trend} />
                        <span style={{ fontSize: 12, color: "#9ca3af" }}>Last active: {u.last_active || "Never"}</span>
                        <span style={{
                          fontSize: 12, fontWeight: 600,
                          color: u.days_since_contact >= 5 ? "#dc2626" : u.days_since_contact >= 3 ? "#ea580c" : "#6b7280",
                        }}>
                          {u.days_since_contact === 999 ? "Never" : `${u.days_since_contact}d ago`}
                        </span>
                        <span style={{ color: "#9ca3af", fontSize: 12 }}>{expandedUser === u.user_id ? "▲" : "▼"}</span>
                      </div>
                    </div>

                    {expandedUser === u.user_id && (
                      <div style={{ marginTop: 12, padding: "12px 14px", background: "#f8fafc", borderRadius: 8, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                        <div style={{ fontSize: 13, color: "#374151" }}>
                          <strong>Risk level:</strong> <RiskBadge level={u.latest_risk_level} />
                        </div>
                        <div style={{ fontSize: 13, color: "#374151" }}>
                          <strong>Trend:</strong> <TrendBadge trend={u.trend} />
                        </div>
                        <div style={{ fontSize: 13, color: "#374151" }}>
                          <strong>Days since contact:</strong>{" "}
                          {u.days_since_contact === 999 ? "Never contacted" : `${u.days_since_contact} days`}
                        </div>
                        <div style={{ fontSize: 13, color: "#374151" }}>
                          <strong>Recommended action:</strong>{" "}
                          {u.latest_risk_level === "critical" ? "Contact immediately" :
                           u.latest_risk_level === "high" ? "Call today" :
                           u.days_since_contact >= 5 ? "Schedule check-in call" :
                           "Monitor closely"}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {alertUsers.length === 0 && (
            <div style={{ background: "#f0fdf4", border: "1px solid #86efac", borderRadius: 10, padding: "16px 20px", marginBottom: 24, display: "flex", alignItems: "center", gap: 12 }}>
              <span style={{ fontSize: 20 }}>✓</span>
              <div>
                <div style={{ fontWeight: 600, color: "#16a34a" }}>All users within normal parameters</div>
                <div style={{ fontSize: 13, color: "#6b7280" }}>No urgent follow-ups needed today.</div>
              </div>
            </div>
          )}

          {/* All users table */}
          <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 12, overflow: "hidden" }}>
            <div style={{ padding: "14px 20px", borderBottom: "1px solid #f3f4f6", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10 }}>
              <div>
                <div style={{ fontSize: 11, fontWeight: 600, color: "#6b7280", letterSpacing: "0.1em", textTransform: "uppercase" }}>User Monitoring</div>
                <span style={{ fontWeight: 700, fontSize: 16, color: "#111827" }}>All users</span>
              </div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {["all", "alert", "critical", "high", "medium", "low", "no_data"].map(f => (
                  <button key={f} onClick={() => setFilter(f)} style={{
                    padding: "3px 12px", borderRadius: 20,
                    border: `1px solid ${filter === f ? "#111827" : "#e5e7eb"}`,
                    background: filter === f ? "#111827" : "#fff",
                    color: filter === f ? "#fff" : "#6b7280",
                    fontSize: 11, fontWeight: 500, cursor: "pointer", textTransform: "capitalize",
                  }}>
                    {f === "alert" ? "Needs attention" : f === "no_data" ? "No data" : f}
                  </button>
                ))}
              </div>
            </div>

            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid #f3f4f6", background: "#f9fafb" }}>
                    {["Name", "Risk", "Reason", "Trend", "Last active", "Days"].map(h => (
                      <th key={h} style={{
                        padding: "10px 16px", textAlign: "left",
                        fontSize: 11, fontWeight: 600, color: "#6b7280",
                        letterSpacing: "0.06em", textTransform: "uppercase",
                      }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredUsers.map(u => (
                    <tr key={u.user_id} style={{
                      borderBottom: "1px solid #f3f4f6",
                      background: u.alert ? "#fffbeb" : "transparent",
                    }}>
                      <td style={{ padding: "12px 16px" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                          <Avatar name={u.name} />
                          <span style={{ fontWeight: 600, color: "#111827" }}>{u.name}</span>
                        </div>
                      </td>
                      <td style={{ padding: "12px 16px" }}><RiskBadge level={u.latest_risk_level} /></td>
                      <td style={{ padding: "12px 16px", color: "#4b5563", fontSize: 12, maxWidth: 220 }}>
                        {u.alert_reason || (
                          <span style={{ color: "#9ca3af" }}>No immediate concerns detected.</span>
                        )}
                      </td>
                      <td style={{ padding: "12px 16px" }}><TrendBadge trend={u.trend} /></td>
                      <td style={{ padding: "12px 16px", color: "#4b5563", fontSize: 12 }}>{u.last_active || "—"}</td>
                      <td style={{ padding: "12px 16px" }}>
                        <span style={{
                          fontWeight: 600, fontSize: 12,
                          color: u.days_since_contact >= 5 ? "#dc2626" :
                                 u.days_since_contact >= 3 ? "#ea580c" : "#16a34a",
                        }}>
                          {u.days_since_contact === 999 ? "Never" : `${u.days_since_contact}d`}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
