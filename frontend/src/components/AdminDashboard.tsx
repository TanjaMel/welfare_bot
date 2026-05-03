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

const RISK_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  critical: { label: "Critical", color: "#dc2626", bg: "#fef2f2" },
  high:     { label: "High",     color: "#ea580c", bg: "#fff7ed" },
  medium:   { label: "Medium",   color: "#ca8a04", bg: "#fefce8" },
  low:      { label: "Low",      color: "#16a34a", bg: "#f0fdf4" },
  no_data:  { label: "No data",  color: "#6b7280", bg: "#f9fafb" },
};

const TREND_ICON: Record<string, string> = {
  improving: "↑", worsening: "↓", stable: "→", no_data: "—",
};

const TREND_COLOR: Record<string, string> = {
  improving: "#16a34a", worsening: "#dc2626", stable: "#6b7280", no_data: "#9ca3af",
};

const RISK_REASON: Record<string, string> = {
  critical: "Immediate action required — critical signals detected in conversation",
  high: "High risk signals detected — possible pain, loneliness or safety concern",
  medium: "Some concerns noticed — follow up recommended this week",
  low: "No immediate concerns",
  no_data: "No conversation data available yet",
};

function RiskBadge({ level }: { level: string }) {
  const cfg = RISK_CONFIG[level] || RISK_CONFIG.no_data;
  return (
    <span style={{
      background: cfg.bg, color: cfg.color,
      padding: "3px 10px", borderRadius: 20,
      fontSize: 12, fontWeight: 600,
      border: `1px solid ${cfg.color}30`,
    }}>
      {cfg.label}
    </span>
  );
}

function StatCard({ label, value, sub, accent }: {
  label: string; value: string | number; sub?: string; accent?: string
}) {
  return (
    <div style={{
      background: "#fff", border: "1px solid #e5e7eb", borderRadius: 12,
      padding: "20px 24px", borderTop: accent ? `3px solid ${accent}` : "1px solid #e5e7eb",
    }}>
      <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 700, color: accent || "#111827" }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

export default function AdminDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedUser, setExpandedUser] = useState<number | null>(null);

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem("access_token");
      const res = await fetch(`${API_BASE}/admin/dashboard?days=7`, {
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      });
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const json = await res.json();
      setData(json);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void fetchDashboard(); }, [fetchDashboard]);

  if (loading) return <div style={{ padding: 40, color: "#6b7280" }}>Loading dashboard...</div>;
  if (error) return <div style={{ padding: 40, color: "#dc2626" }}>{error}</div>;
  if (!data) return <div style={{ padding: 40 }}>No data</div>;

  const alertUsers = data.users.filter(u => u.alert);
  return (
    <div style={{ padding: "24px 32px", maxWidth: 1100, margin: "0 auto", fontFamily: "'DM Sans', 'Segoe UI', sans-serif" }}>

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0, color: "#111827" }}>Population overview</h1>
          <p style={{ fontSize: 13, color: "#6b7280", margin: "4px 0 0" }}>
            Updated {data.generated_at}
          </p>
        </div>
        <button onClick={fetchDashboard} style={{
          padding: "6px 14px", borderRadius: 8, border: "1px solid #e5e7eb",
          background: "#fff", fontSize: 13, cursor: "pointer", color: "#374151",
        }}>
          ↻ Refresh
        </button>
      </div>

      {/* Summary cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 16, marginBottom: 28 }}>
        <StatCard label="Total users" value={data.summary.total_users} sub={`${data.summary.active_today} active today`} />
        <StatCard label="Need attention" value={data.summary.users_needing_attention} accent={data.summary.users_needing_attention > 0 ? "#dc2626" : undefined} />
        <StatCard label="Critical" value={data.summary.critical_count} accent="#dc2626" />
        <StatCard label="High risk" value={data.summary.high_count} accent="#ea580c" />
        <StatCard label="Medium risk" value={data.summary.medium_count} accent="#ca8a04" />
        <StatCard label="Avg wellbeing" value={data.summary.avg_wellbeing_score !== null ? `${data.summary.avg_wellbeing_score}%` : "—"} accent="#16a34a" />
      </div>

      {/* Users needing attention */}
      {alertUsers.length > 0 && (
        <div style={{ marginBottom: 28 }}>
          <h2 style={{ fontSize: 15, fontWeight: 600, color: "#dc2626", marginBottom: 12 }}>
            ⚠ Needs attention ({alertUsers.length})
          </h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {alertUsers.map(u => (
              <div key={u.user_id} style={{
                background: "#fffbeb", border: "1px solid #fcd34d",
                borderRadius: 10, padding: "14px 18px",
                cursor: "pointer",
              }} onClick={() => setExpandedUser(expandedUser === u.user_id ? null : u.user_id)}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <span style={{ fontWeight: 600, color: "#111827" }}>{u.name}</span>
                    <RiskBadge level={u.latest_risk_level} />
                    <span style={{ color: TREND_COLOR[u.trend], fontWeight: 600, fontSize: 16 }}>
                      {TREND_ICON[u.trend]}
                    </span>
                  </div>
                  <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
                    <span style={{ fontSize: 12, color: "#9ca3af" }}>
                      Last active: {u.last_active || "Never"}
                    </span>
                    <span style={{
                      fontSize: 12, color: u.days_since_contact >= 2 ? "#dc2626" : "#16a34a",
                      fontWeight: u.days_since_contact >= 2 ? 600 : 400,
                    }}>
                      {u.days_since_contact === 999 ? "Never contacted" : `${u.days_since_contact}d ago`}
                    </span>
                    <span style={{ fontSize: 13, color: "#9ca3af" }}>{expandedUser === u.user_id ? "▲" : "▼"}</span>
                  </div>
                </div>

                {expandedUser === u.user_id && (
                  <div style={{ marginTop: 12, padding: "10px 14px", background: "#fff", borderRadius: 8, border: "1px solid #e5e7eb" }}>
                    <div style={{ fontSize: 13, color: "#374151", marginBottom: 6 }}>
                      <strong>Why flagged:</strong> {RISK_REASON[u.latest_risk_level] || "Unknown reason"}
                    </div>
                    <div style={{ fontSize: 13, color: "#374151", marginBottom: 6 }}>
                      <strong>Risk score:</strong> {u.latest_risk_score}/10
                    </div>
                    <div style={{ fontSize: 13, color: "#374151", marginBottom: 6 }}>
                      <strong>Trend:</strong> {u.trend}
                    </div>
                    <div style={{ fontSize: 13, color: "#374151" }}>
                      <strong>Recommended action:</strong>{" "}
                      {u.latest_risk_level === "critical" ? "Contact immediately" :
                       u.latest_risk_level === "high" ? "Call today" :
                       u.days_since_contact >= 3 ? "Schedule a check-in call" :
                       "Monitor closely"}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* All users table */}
      <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 12, overflow: "hidden" }}>
        <div style={{ padding: "14px 20px", borderBottom: "1px solid #f3f4f6" }}>
          <span style={{ fontWeight: 600, fontSize: 14, color: "#111827" }}>
            All users ({data.users.length})
          </span>
        </div>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: "2px solid #e5e7eb" }}>
              {["Name", "Risk level", "Why flagged", "Trend", "Last active", "Days since contact"].map(h => (
                <th key={h} style={{
                  padding: "10px 16px", textAlign: "left",
                  fontSize: 11, fontWeight: 600, color: "#6b7280",
                  letterSpacing: "0.06em", textTransform: "uppercase",
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.users.map(u => (
              <tr key={u.user_id} style={{
                borderBottom: "1px solid #f3f4f6",
                background: u.alert ? "#fffbeb" : "transparent",
              }}>
                <td style={{ padding: "12px 16px", fontWeight: 600, color: "#111827" }}>
                  {u.alert && <span style={{ marginRight: 6 }}>⚠️</span>}
                  {u.name}
                </td>
                <td style={{ padding: "12px 16px" }}>
                  <RiskBadge level={u.latest_risk_level} />
                </td>
                <td style={{ padding: "12px 16px", color: "#4b5563", fontSize: 12, maxWidth: 250 }}>
                  {RISK_REASON[u.latest_risk_level]}
                </td>
                <td style={{ padding: "12px 16px" }}>
                  <span style={{ color: TREND_COLOR[u.trend], fontWeight: 600, fontSize: 16 }}>
                    {TREND_ICON[u.trend]}
                  </span>
                  <span style={{ fontSize: 11, color: "#9ca3af", marginLeft: 4 }}>
                    {u.trend !== "no_data" ? u.trend : ""}
                  </span>
                </td>
                <td style={{ padding: "12px 16px", color: "#4b5563" }}>
                  {u.last_active || "—"}
                </td>
                <td style={{ padding: "12px 16px" }}>
                  <span style={{
                    color: u.days_since_contact >= 2 ? "#dc2626" : "#16a34a",
                    fontWeight: u.days_since_contact >= 2 ? 600 : 400,
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
  );
}
