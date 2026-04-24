"""
Daily aggregation pipeline for wellbeing_daily_metrics.

Run once per day per user, ideally at midnight or after the last
conversation of the day. Can be triggered by:
  - FastAPI BackgroundTasks (simplest, already available)
  - APScheduler (lightweight cron inside the app)
  - Celery beat (if you need distributed scheduling later)

For MVP: trigger as a FastAPI background task after each message send,
but only recompute if the existing row is older than 1 hour.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models.conversation_message import ConversationMessage
from app.db.models.daily_checkin import DailyCheckIn
from app.db.models.risk_analysis import RiskAnalysis
from app.db.models.wellbeing_daily_metrics import WellbeingDailyMetrics

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# SCORING CONSTANTS
# ─────────────────────────────────────────────

WEIGHTS = {
    "mood": 0.25,
    "sleep": 0.25,
    "food": 0.20,
    "hydration": 0.15,
    "medication": 0.10,
    "social": 0.05,
}

# Risk score from risk_analyses is inverted and capped:
# risk_score 0 → wellbeing contribution 100
# risk_score 10+ → wellbeing contribution 0
RISK_PENALTY_WEIGHT = 0.30  # risk reduces overall score

THRESHOLDS = {
    "stable": 70,           # >= 70 → stable
    "needs_attention": 50,  # 50–69 → needs attention
    "concerning": 30,       # 30–49 → concerning
    # < 30 → critical
}

# Soft messages by status — never expose raw numbers
SOFT_MESSAGES = {
    "stable": "You seem to be doing well today. Keep taking care of yourself.",
    "needs_attention": "Today looks a little quieter than usual. Small steps help — a glass of water or a short walk can make a difference.",
    "concerning": "It seems like today has been harder. You don't have to manage alone — reaching out to someone you trust is always a good idea.",
    "critical": "We noticed some signs that today may be difficult. Please consider calling a family member or your care worker.",
}


# ─────────────────────────────────────────────
# SCORE COMPUTATION
# ─────────────────────────────────────────────

def _sleep_score(checkin: Optional[DailyCheckIn]) -> Optional[float]:
    """
    Maps sleep_quality (1–5 Likert) to 0–100.
    Missing → None (excluded from composite).
    """
    if checkin is None or checkin.sleep_quality is None:
        return None
    return min(100.0, max(0.0, (checkin.sleep_quality - 1) / 4 * 100))


def _food_score(checkin: Optional[DailyCheckIn]) -> Optional[float]:
    """
    ate_breakfast + ate_lunch + ate_dinner = 3 meals possible.
    Each present meal = 33.3 points.
    Missing checkin → None.
    """
    if checkin is None:
        return None
    meals = [checkin.ate_breakfast, checkin.ate_lunch, checkin.ate_dinner]
    known = [m for m in meals if m is not None]
    if not known:
        return None
    return round(sum(1 for m in known if m) / len(known) * 100, 1)


def _hydration_score(checkin: Optional[DailyCheckIn]) -> Optional[float]:
    """
    drank_enough_water: bool or None.
    True → 100, False → 20 (not 0, to avoid harsh penalty for one missed day).
    """
    if checkin is None or checkin.drank_enough_water is None:
        return None
    return 100.0 if checkin.drank_enough_water else 20.0


def _medication_score(checkin: Optional[DailyCheckIn]) -> Optional[float]:
    """
    took_medication: bool or None.
    True → 100, False → 0.
    If not applicable (user has no medication), return None to exclude.
    """
    if checkin is None or checkin.took_medication is None:
        return None
    return 100.0 if checkin.took_medication else 0.0


def _mood_score(
    checkin: Optional[DailyCheckIn],
    risk_signals: list[str],
) -> Optional[float]:
    """
    Primary source: mood_rating from checkin (1–5).
    Fallback: infer from risk signals (loneliness, sadness → lower score).
    """
    if checkin is not None and checkin.mood_rating is not None:
        return min(100.0, max(0.0, (checkin.mood_rating - 1) / 4 * 100))

    # Signal-based inference when no checkin
    negative_signals = {"sadness_loneliness", "emotional", "loneliness"}
    if any(s in risk_signals for s in negative_signals):
        return 30.0  # soft penalty, not zero

    return None


def _social_score(message_count_today: int) -> float:
    """
    Proxy for social activity: number of messages exchanged today.
    0 messages → 0, 5+ messages → 80 (cap at 80, not 100, to avoid gaming).
    """
    return min(80.0, message_count_today * 16.0)


def _risk_to_wellbeing(avg_risk_score: Optional[float]) -> float:
    """
    Inverts the risk score for use in overall wellbeing composite.
    risk 0 → 100, risk 10 → 0. Clamped.
    """
    if avg_risk_score is None:
        return 70.0  # neutral when no data
    return max(0.0, min(100.0, 100 - (avg_risk_score * 10)))


def _overall_score(
    mood: Optional[float],
    sleep: Optional[float],
    food: Optional[float],
    hydration: Optional[float],
    medication: Optional[float],
    social: Optional[float],
    risk_wellbeing: float,
) -> tuple[float, float]:
    """
    Weighted composite score.
    Returns (overall_score, data_completeness).
    Excludes None components but adjusts weights proportionally.
    """
    components = {
        "mood": mood,
        "sleep": sleep,
        "food": food,
        "hydration": hydration,
        "medication": medication,
        "social": social,
    }

    total_weight = 0.0
    weighted_sum = 0.0
    present = 0

    for key, value in components.items():
        if value is not None:
            w = WEIGHTS[key]
            weighted_sum += value * w
            total_weight += w
            present += 1

    if total_weight == 0:
        # No check-in data at all — use risk signal only
        return round(risk_wellbeing, 1), 0.0

    # Normalize to account for missing components
    checkin_score = weighted_sum / total_weight * 100 / 100
    # Blend with risk signal
    final = (checkin_score * (1 - RISK_PENALTY_WEIGHT)) + (risk_wellbeing / 100 * RISK_PENALTY_WEIGHT)
    final_score = round(min(100.0, max(0.0, final * 100)), 1)
    completeness = round(present / len(components), 2)

    return final_score, completeness


def _status_from_score(score: float) -> str:
    if score >= THRESHOLDS["stable"]:
        return "stable"
    if score >= THRESHOLDS["needs_attention"]:
        return "needs_attention"
    if score >= THRESHOLDS["concerning"]:
        return "concerning"
    return "critical"


# ─────────────────────────────────────────────
# MAIN PIPELINE FUNCTION
# ─────────────────────────────────────────────

def aggregate_daily_wellbeing(
    user_id: int,
    target_date: date,
    db: Session,
) -> WellbeingDailyMetrics:
    """
    Computes or updates the wellbeing_daily_metrics row for a given user and date.
    Safe to call multiple times — uses upsert pattern.
    """
    # 1. Fetch today's check-in (may be None)
    checkin = (
        db.query(DailyCheckIn)
        .filter(
            DailyCheckIn.user_id == user_id,
            DailyCheckIn.date == target_date,
        )
        .first()
    )

    # 2. Fetch today's risk analyses
    day_start = datetime.combine(target_date, datetime.min.time())
    day_end = datetime.combine(target_date, datetime.max.time())

    risk_rows = (
        db.query(RiskAnalysis)
        .filter(
            RiskAnalysis.user_id == user_id,
            RiskAnalysis.created_at >= day_start,
            RiskAnalysis.created_at <= day_end,
        )
        .all()
    )

    avg_risk = (
        sum(r.risk_score for r in risk_rows if r.risk_score is not None) / len(risk_rows)
        if risk_rows else None
    )

    # Flatten all signal strings for mood inference
    all_signals: list[str] = []
    for r in risk_rows:
        if r.signals_json:
            all_signals.extend(r.signals_json if isinstance(r.signals_json, list) else [])

    # 3. Fetch today's message count
    message_count = (
        db.query(ConversationMessage)
        .filter(
            ConversationMessage.user_id == user_id,
            ConversationMessage.created_at >= day_start,
            ConversationMessage.created_at <= day_end,
        )
        .count()
    )

    # 4. Compute component scores
    mood = _mood_score(checkin, all_signals)
    sleep = _sleep_score(checkin)
    food = _food_score(checkin)
    hydration = _hydration_score(checkin)
    medication = _medication_score(checkin)
    social = _social_score(message_count)
    risk_wellbeing = _risk_to_wellbeing(avg_risk)

    # 5. Compute overall
    overall, completeness = _overall_score(mood, sleep, food, hydration, medication, social, risk_wellbeing)

    # 6. Determine status and message
    status = _status_from_score(overall)
    soft_message = SOFT_MESSAGES[status]

    # 7. Upsert
    existing = (
        db.query(WellbeingDailyMetrics)
        .filter(
            WellbeingDailyMetrics.user_id == user_id,
            WellbeingDailyMetrics.date == target_date,
        )
        .first()
    )

    if existing:
        row = existing
    else:
        row = WellbeingDailyMetrics(user_id=user_id, date=target_date)
        db.add(row)

    row.mood_score = mood
    row.sleep_score = sleep
    row.food_score = food
    row.hydration_score = hydration
    row.medication_score = medication
    row.social_activity_score = social
    row.risk_score = avg_risk
    row.overall_wellbeing_score = overall
    row.status = status
    row.soft_message = soft_message
    row.data_completeness = completeness
    row.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(row)

    logger.info(f"Aggregated wellbeing for user {user_id} on {target_date}: {overall} ({status})")
    return row