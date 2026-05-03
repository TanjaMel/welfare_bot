"""
Wellbeing analytics endpoints.
IMPORTANT: Never return raw risk scores or clinical language to users.
All output is soft, supportive, and human-readable.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.wellbeing_daily_metrics import WellbeingDailyMetrics
from app.services.aggregation_pipeline import aggregate_daily_wellbeing

router = APIRouter()


# ─────────────────────────────────────────────
# RESPONSE SCHEMAS
# ─────────────────────────────────────────────

class WellbeingSummaryResponse(BaseModel):
    status: str
    overall_score: float
    soft_message: str
    data_completeness: float
    checked_at: str  # human-readable time, not ISO

    model_config = ConfigDict(from_attributes=True)


class DailyScorePoint(BaseModel):
    date: str
    overall: Optional[float]
    mood: Optional[float]
    sleep: Optional[float]
    food: Optional[float]
    hydration: Optional[float]
    status: str


class TrendsResponse(BaseModel):
    days: int
    points: list[DailyScorePoint]
    trend_message: str  # e.g. "You've been doing well this week"


class InsightItem(BaseModel):
    area: str          # "sleep", "hydration", etc.
    message: str       # soft human-readable insight
    direction: str     # "improving", "stable", "declining"


class InsightsResponse(BaseModel):
    insights: list[InsightItem]
    summary: str


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _human_time(dt: datetime) -> str:
    return dt.strftime("%I:%M %p").lstrip("0")


def _trend_message(points: list[WellbeingDailyMetrics]) -> str:
    """Generates a soft trend summary from recent rows."""
    if not points:
        return "No recent data yet. Keep chatting and we'll build your picture."

    scores = [p.overall_wellbeing_score for p in points if p.overall_wellbeing_score is not None]
    if not scores:
        return "We're still learning about your wellbeing. Keep going."

    avg = sum(scores) / len(scores)
    recent_avg = sum(scores[-3:]) / len(scores[-3:]) if len(scores) >= 3 else avg

    if recent_avg > avg + 5:
        return "Things seem to be looking up recently. That's great to see."
    if recent_avg < avg - 5:
        return "The last few days have been a little quieter. Small things help — fresh air, water, a kind word."
    return "Your wellbeing has been fairly steady. Keep taking care of yourself."


def _generate_insights(rows: list[WellbeingDailyMetrics]) -> list[InsightItem]:
    """
    Generates human-readable insights from trend data.
    Only includes insights where there is enough data to be meaningful.
    """
    insights = []

    def avg_field(field: str) -> Optional[float]:
        vals = [getattr(r, field) for r in rows if getattr(r, field) is not None]
        return sum(vals) / len(vals) if vals else None

    def recent_avg(field: str, n: int = 3) -> Optional[float]:
        vals = [getattr(r, field) for r in rows[-n:] if getattr(r, field) is not None]
        return sum(vals) / len(vals) if vals else None

    # Sleep
    sleep_all = avg_field("sleep_score")
    sleep_recent = recent_avg("sleep_score")
    if sleep_all is not None and sleep_recent is not None:
        if sleep_recent > sleep_all + 8:
            insights.append(InsightItem(area="sleep", message="You seem to be sleeping better lately.", direction="improving"))
        elif sleep_recent < sleep_all - 8:
            insights.append(InsightItem(area="sleep", message="Your sleep has been a little more restless recently. A calm evening routine can help.", direction="declining"))
        elif sleep_all >= 70:
            insights.append(InsightItem(area="sleep", message="Your sleep has been good this period.", direction="stable"))

    # Hydration
    hydration = avg_field("hydration_score")
    if hydration is not None and hydration < 60:
        insights.append(InsightItem(area="hydration", message="You may need to drink a little more water throughout the day.", direction="declining"))
    elif hydration is not None and hydration >= 80:
        insights.append(InsightItem(area="hydration", message="You've been staying well hydrated. Keep it up.", direction="stable"))

    # Food
    food = avg_field("food_score")
    if food is not None and food < 55:
        insights.append(InsightItem(area="food", message="Some days it looks like meals were skipped. Even small snacks help keep your energy up.", direction="declining"))
    elif food is not None and food >= 80:
        insights.append(InsightItem(area="food", message="Your eating has been regular and consistent.", direction="stable"))

    # Mood
    mood_all = avg_field("mood_score")
    mood_recent = recent_avg("mood_score")
    if mood_all is not None and mood_recent is not None:
        if mood_recent > mood_all + 8:
            insights.append(InsightItem(area="mood", message="You've seemed a bit brighter recently. That's wonderful.", direction="improving"))
        elif mood_recent < mood_all - 8:
            insights.append(InsightItem(area="mood", message="Your mood has been a little lower lately. Talking to someone you trust can really help.", direction="declining"))

    # Social
    social = avg_field("social_activity_score")
    if social is not None and social < 30:
        insights.append(InsightItem(area="social", message="You've been quieter than usual lately. We're always here when you want to chat.", direction="declining"))

    return insights


# ─────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────

@router.get(
    "/summary/{user_id}",
    response_model=WellbeingSummaryResponse,
    summary="Today's wellbeing summary",
)
def get_summary(
    user_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Returns today's wellbeing status.
    Triggers a background recompute if no row exists for today.
    """
    today = date.today()

    row = (
        db.query(WellbeingDailyMetrics)
        .filter(
            WellbeingDailyMetrics.user_id == user_id,
            WellbeingDailyMetrics.date == today,
        )
        .first()
    )

    if row is None:
        # Compute synchronously on first request — acceptable latency for summary
        row = aggregate_daily_wellbeing(user_id, today, db)

    # Schedule a background refresh so the next request is fast
    background_tasks.add_task(aggregate_daily_wellbeing, user_id, today, db)

    return WellbeingSummaryResponse(
        status=row.status,
        overall_score=row.overall_wellbeing_score or 0.0,
        soft_message=row.soft_message or "We're still getting to know you. Keep chatting.",
        data_completeness=row.data_completeness,
        checked_at=_human_time(row.updated_at),
    )


@router.get(
    "/trends/{user_id}",
    response_model=TrendsResponse,
    summary="Wellbeing trends over time",
)
def get_trends(
    user_id: int,
    days: int = Query(default=7, ge=7, le=30),
    db: Session = Depends(get_db),
):
    """
    Returns daily wellbeing scores for the last N days.
    Missing days are filled with nulls — never fabricate data.
    """
    end = date.today()
    start = end - timedelta(days=days - 1)

    rows = (
        db.query(WellbeingDailyMetrics)
        .filter(
            WellbeingDailyMetrics.user_id == user_id,
            WellbeingDailyMetrics.date >= start,
            WellbeingDailyMetrics.date <= end,
        )
        .order_by(WellbeingDailyMetrics.date)
        .all()
    )

    # Build a complete date range — fill gaps with nulls
    row_by_date = {r.date: r for r in rows}
    points = []
    for i in range(days):
        d = start + timedelta(days=i)
        r = row_by_date.get(d)
        points.append(DailyScorePoint(
            date=d.strftime("%b %d"),
            overall=r.overall_wellbeing_score if r else None,
            mood=r.mood_score if r else None,
            sleep=r.sleep_score if r else None,
            food=r.food_score if r else None,
            hydration=r.hydration_score if r else None,
            status=r.status if r else "no_data",
        ))

    return TrendsResponse(
        days=days,
        points=points,
        trend_message=_trend_message(rows),
    )


@router.get(
    "/insights/{user_id}",
    response_model=InsightsResponse,
    summary="Human-readable wellbeing insights",
)
def get_insights(
    user_id: int,
    days: int = Query(default=14, ge=7, le=30),
    db: Session = Depends(get_db),
):
    """
    Returns soft, actionable insights based on recent trends.
    Language is always supportive — no clinical or alarming terms.
    """
    end = date.today()
    start = end - timedelta(days=days - 1)

    rows = (
        db.query(WellbeingDailyMetrics)
        .filter(
            WellbeingDailyMetrics.user_id == user_id,
            WellbeingDailyMetrics.date >= start,
        )
        .order_by(WellbeingDailyMetrics.date)
        .all()
    )

    if not rows:
        return InsightsResponse(
            insights=[],
            summary="We don't have enough information yet. Keep chatting each day and we'll share more.",
        )

    insights = _generate_insights(rows)

    if not insights:
        summary = "Everything looks balanced recently. You're doing well."
    elif len(insights) == 1:
        summary = "We noticed one area worth a little attention."
    else:
        summary = f"We noticed a few things worth a little attention across the last {days} days."

    return InsightsResponse(insights=
                            insights, summary=summary)