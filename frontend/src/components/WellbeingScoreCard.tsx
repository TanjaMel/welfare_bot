import type { WellbeingSummary } from "../types";

type Props = { summary: WellbeingSummary };

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string; border: string }> = {
  stable:          { label: "You are doing well today",        color: "#16a34a", bg: "#f0fdf4", border: "#bbf7d0" },
  needs_attention: { label: "A little quieter than usual",     color: "#92400e", bg: "#fffbeb", border: "#fde68a" },
  concerning:      { label: "Some concerns noticed",           color: "#9a3412", bg: "#fff7ed", border: "#fed7aa" },
  critical:        { label: "You may need some support today", color: "#991b1b", bg: "#fef2f2", border: "#fecaca" },
};

const STATUS_INDICATOR: Record<string, string> = {
  stable:          "●",
  needs_attention: "●",
  concerning:      "●",
  critical:        "●",
};

export default function WellbeingScoreCard({ summary }: Props) {
  const cfg = STATUS_CONFIG[summary.status] ?? {
    label: "Checking in...", color: "#6b7280", bg: "#f9fafb", border: "#e5e7eb"
  };

  const dateStr = (() => {
    try {
      return new Date(summary.checked_at).toLocaleDateString(undefined, {
        weekday: "long", month: "long", day: "numeric",
      });
    } catch { return ""; }
  })();

  return (
    <div style={{
      background: cfg.bg,
      border: `1px solid ${cfg.border}`,
      borderLeft: `4px solid ${cfg.color}`,
      borderRadius: 12,
      padding: "20px 24px",
      marginBottom: 20,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
        <span style={{ color: cfg.color, fontSize: 10 }}>
          {STATUS_INDICATOR[summary.status] ?? "●"}
        </span>
        <span style={{ fontSize: 17, fontWeight: 700, color: cfg.color }}>
          {cfg.label}
        </span>
      </div>
      <p style={{ fontSize: 14, color: "#374151", margin: "0 0 10px", lineHeight: 1.6 }}>
        {summary.soft_message ?? summary.message}
      </p>
      {dateStr && (
        <div style={{ fontSize: 12, color: "#9ca3af" }}>{dateStr}</div>
      )}
    </div>
  );
}
