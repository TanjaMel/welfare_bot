import { useEffect, useState } from "react";
import type { WellbeingInsight, WellbeingSummary, WellbeingTrendPoint } from "../types";
import { getWellbeingInsights, getWellbeingSummary, getWellbeingTrends } from "../api";
import WellbeingScoreCard from "./WellbeingScoreCard";
import WellbeingTrendChart from "./WellbeingTrendChart";
import WellbeingInsights from "./WellbeingInsights";

type Props = { userId: number };
type Period = 7 | 14 | 30;

export default function WellbeingPanel({ userId }: Props) {
  const [summary, setSummary] = useState<WellbeingSummary | null>(null);
  const [trends, setTrends] = useState<WellbeingTrendPoint[]>([]);
  const [insights, setInsights] = useState<WellbeingInsight[]>([]);
  const [period, setPeriod] = useState<Period>(7);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadAll(days: Period) {
    setLoading(true);
    setError(null);
    try {
      const [s, t, i] = await Promise.all([
        getWellbeingSummary(userId),
        getWellbeingTrends(userId, days),
        getWellbeingInsights(userId),
      ]);
      setSummary(s);
      setTrends(t);
      setInsights(i);
    } catch {
      setError("We could not load your wellbeing data right now. Please try again shortly.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void loadAll(period); }, [userId]);

  async function handlePeriod(days: Period) {
    setPeriod(days);
    try {
      const t = await getWellbeingTrends(userId, days);
      setTrends(t);
    } catch { /* keep existing data */ }
  }

  return (
    <div className="wb-panel">
      <div className="wb-panel-header">
        <div>
          <h2 className="wb-panel-title">Your wellbeing trends</h2>
          <p className="wb-panel-subtitle">
            A gentle overview of how you have been doing recently.
          </p>
        </div>
        <div className="wb-period-selector" role="group" aria-label="Select time period">
          {([7, 14, 30] as Period[]).map((d) => (
            <button
              key={d}
              type="button"
              className={`wb-period-btn ${period === d ? "active" : ""}`}
              onClick={() => void handlePeriod(d)}
              aria-pressed={period === d}
            >
              {d} days
            </button>
          ))}
        </div>
      </div>

      {loading && (
        <div className="wb-loading">
          <div className="wb-loading-bar" />
          <p>Loading your wellbeing picture...</p>
        </div>
      )}

      {!loading && error && (
        <div className="wb-error">
          <p>{error}</p>
          <button type="button" className="wb-retry-btn" onClick={() => void loadAll(period)}>
            Try again
          </button>
        </div>
      )}

      {!loading && !error && (
        <div className="wb-content">
          {summary && <WellbeingScoreCard summary={summary} />}
          <WellbeingTrendChart data={trends} />
          <WellbeingInsights insights={insights} />
        </div>
      )}
    </div>
  );
}