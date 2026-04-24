import type { WellbeingInsight } from "../types";

type Props = { insights: WellbeingInsight[] };

const TYPE_CLASS: Record<string, string> = {
  positive: "wb-insight-positive",
  neutral: "wb-insight-neutral",
  attention: "wb-insight-attention",
};

const TYPE_INDICATOR: Record<string, string> = {
  positive: "wb-indicator-positive",
  neutral: "wb-indicator-neutral",
  attention: "wb-indicator-attention",
};

export default function WellbeingInsights({ insights }: Props) {
  if (!insights || insights.length === 0) {
    return (
      <div className="wb-insights-empty">
        <p>No strong patterns yet. Keep checking in regularly and we will share more over time.</p>
      </div>
    );
  }

  return (
    <div className="wb-insights">
      <h3 className="wb-insights-title">What we noticed</h3>
      <div className="wb-insights-list">
        {insights.map((insight, i) => (
          <div key={i} className={`wb-insight-card ${TYPE_CLASS[insight.type] ?? ""}`}>
            <div className={`wb-insight-indicator ${TYPE_INDICATOR[insight.type] ?? ""}`} aria-hidden="true" />
            <div className="wb-insight-copy">
              <div className="wb-insight-title">{insight.title}</div>
              <p className="wb-insight-message">{insight.message}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}