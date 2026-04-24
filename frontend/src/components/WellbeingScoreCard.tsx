import type { WellbeingSummary } from "../types";

type Props = { summary: WellbeingSummary };

const STATUS_LABELS: Record<string, string> = {
  stable: "Stable",
  needs_attention: "Needs a little attention",
  concerning: "Some concerns",
  critical: "Needs support soon",
};

const STATUS_CLASS: Record<string, string> = {
  stable: "wb-score-stable",
  needs_attention: "wb-score-attention",
  concerning: "wb-score-concerning",
  critical: "wb-score-critical",
};

function ScoreRing({ score }: { score: number }) {
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.min(100, Math.max(0, score));
  const offset = circumference - (clamped / 100) * circumference;

  return (
    <div className="wb-ring-wrap" aria-hidden="true">
      <svg width="128" height="128" viewBox="0 0 128 128">
        <circle cx="64" cy="64" r={radius} fill="none" stroke="#EDF2FB" strokeWidth="10" />
        <circle
          cx="64" cy="64" r={radius}
          fill="none"
          stroke="url(#ringGrad)"
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform="rotate(-90 64 64)"
          style={{ transition: "stroke-dashoffset 0.8s ease" }}
        />
        <defs>
          <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#4F7DF3" />
            <stop offset="100%" stopColor="#6A8BFF" />
          </linearGradient>
        </defs>
      </svg>
      <div className="wb-ring-score">{Math.round(clamped)}</div>
    </div>
  );
}

export default function WellbeingScoreCard({ summary }: Props) {
  const label = STATUS_LABELS[summary.status] ?? "No data";
  const cls = STATUS_CLASS[summary.status] ?? "";

  const dateStr = (() => {
    try {
      return new Date(summary.date ?? summary.checked_at).toLocaleDateString(undefined, {
        weekday: "long", month: "long", day: "numeric",
      });
    } catch { return ""; }
  })();

  return (
    <div className={`wb-score-card ${cls}`}>
      <ScoreRing score={summary.overall_score} />
      <div className="wb-score-copy">
        <div className="wb-score-label">{label}</div>
        <p className="wb-score-message">{summary.soft_message ?? summary.message}</p>
        <div className="wb-score-date">{dateStr}</div>
      </div>
    </div>
  );
}