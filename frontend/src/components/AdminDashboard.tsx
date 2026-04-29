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

interface HeatmapPoint {
  date: string;
  critical: number;
  high: number;
  medium: number;
  low: number;
}

interface DashboardData {
  generated_at: string;
  summary: PopulationSummary;
  users: UserRiskRow[];
  heatmap: HeatmapPoint[];
}

const API_BASE =
  typeof window !== "undefined" && window.location.hostname !== "localhost"
    ? "/api/v1"
    : "http://127.0.0.1:8000/api/v1";

const RISK_CONFIG: Record<string, { label: string; color: string; bg: string; dot: string }> = {
  critical: { label: "Critical", color: "#dc2626", bg: "#fef2f2", dot: "#dc2626" },
  high:     { label: "High",     color: "#ea580c", bg: "#fff7ed", dot: "#ea580c" },
  medium:   { label: "Medium",   color: "#ca8a04", bg: "#fefce8", dot: "#ca8a04" },
  low:      { label: "Low",      color: "#16a34a", bg: "#f0fdf4", dot: "#16a34a" },
  no_data:  { label: "No data",  color: "#6b7280", bg: "#f9fafb", dot: "#d1d5db" },
};

const TREND_ICON: Record<string, string> = {
  improving: "↑",
  worsening: "↓",
  stable: "→",
  no_data: "—",
};

const TREND_COLOR: Record<string, string> = {
  improving: "#16a34a",
  worsening: "#dc2626",
  stable: "#6b7280",
  no_data: "#9ca3af",
};

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 12, padding: 20 }}>
      <div style={{ fontSize: 13, color: "#6b7280" }}>{label}</div>
      <div style={{ fontSize: 26, fontWeight: 700 }}>{value}</div>
    </div>
  );
}

function RiskBadge({ level }: { level: string }) {
  const cfg = RISK_CONFIG[level] || RISK_CONFIG.no_data;
  return (
    <span style={{ background: cfg.bg, color: cfg.color, padding: "4px 10px", borderRadius: 20 }}>
      {cfg.label}
    </span>
  );
}

export default function AdminDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchDashboard = useCallback(async () => {
    setLoading(true);

    const token = localStorage.getItem("access_token");

    const res = await fetch(`${API_BASE}/admin/dashboard?days=7`, {
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });

    const json = await res.json();
    setData(json);
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  if (loading) return <div style={{ padding: 40 }}>Loading dashboard...</div>;

  if (!data) return <div>No data</div>;

  return (
    <div style={{ padding: 32 }}>
      <h1>Admin Dashboard</h1>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
        <StatCard label="Total users" value={data.summary.total_users} />
        <StatCard label="Critical" value={data.summary.critical_count} />
        <StatCard label="Need attention" value={data.summary.users_needing_attention} />
      </div>

      <table style={{ width: "100%", marginTop: 30 }}>
        <thead>
          <tr>
            <th>Name</th>
            <th>Risk</th>
            <th>Trend</th>
          </tr>
        </thead>
        <tbody>
          {data.users.map((u) => (
            <tr key={u.user_id}>
              <td>{u.name}</td>
              <td><RiskBadge level={u.latest_risk_level} /></td>
              <td style={{ color: TREND_COLOR[u.trend] }}>
                {TREND_ICON[u.trend]}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}