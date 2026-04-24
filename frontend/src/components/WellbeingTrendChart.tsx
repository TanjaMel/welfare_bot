import type { WellbeingTrendPoint } from "../types";

type Props = { data: WellbeingTrendPoint[] };

export default function WellbeingTrendChart({ data }: Props) {
  if (!data || data.length === 0) {
    return (
      <div className="wb-chart-empty">
        <p>No trend data available yet. Keep checking in and your picture will build over time.</p>
      </div>
    );
  }

  const scores = data.map((d) => d.overall ?? d.overall_wellbeing_score ?? 0);
  const max = Math.max(...scores, 1);

  return (
    <div className="wb-chart-card">
      <div className="wb-chart-header">
        <span className="wb-chart-title">Overall wellbeing</span>
        <span className="wb-chart-legend">
          <span className="wb-legend-dot" /> Daily score
        </span>
      </div>

      <div className="wb-bars" role="img" aria-label="Wellbeing trend bar chart">
        {data.map((point, i) => {
          const score = point.overall ?? point.overall_wellbeing_score ?? 0;
          const height = Math.round((score / max) * 100);
          const dateLabel = (() => {
            try {
              return new Date(point.date).toLocaleDateString(undefined, {
                month: "short", day: "numeric",
              });
            } catch { return point.date; }
          })();

          return (
            <div key={i} className="wb-bar-col">
              <div className="wb-bar-tooltip">{Math.round(score)}</div>
              <div className="wb-bar-track">
                <div className="wb-bar-fill" style={{ height: `${height}%` }} />
              </div>
              <div className="wb-bar-label">{dateLabel}</div>
            </div>
          );
        })}
      </div>

      <div className="wb-chart-footer">
        Scores reflect your daily conversations and check-ins.
      </div>
    </div>
  );
}