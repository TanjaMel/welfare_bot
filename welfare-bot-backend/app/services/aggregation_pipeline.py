from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models.conversation_message import ConversationMessage
from app.db.models.daily_checkin import DailyCheckIn
from app.db.models.risk_analysis import RiskAnalysis
from app.db.models.wellbeing_daily_metrics import WellbeingDailyMetrics
from app.services.aggregation_pipeline_class import AggregationPipeline  # noqa: F401

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# METRIC WEIGHTS — how much each metric
# contributes to the final wellbeing score.
# All weights add up to 1.0 (100%)
# ─────────────────────────────────────────────
WEIGHTS = {
    "mood": 0.25,       # Mood — highest weight, reflects overall state
    "sleep": 0.25,      # Sleep — equally important as mood
    "food": 0.20,       # Food — critical for physical wellbeing
    "hydration": 0.15,  # Hydration — often neglected by elderly users
    "medication": 0.10, # Medication — important but not always available
    "social": 0.05,     # Social activity — smallest weight, measured by message count
}

# How much risk signals affect the final score.
# 30% comes from risk analysis, 70% from check-in data.
RISK_PENALTY_WEIGHT = 0.30

# Score thresholds for determining user status (0–100 scale)
THRESHOLDS = {
    "stable": 70,           # 70+ = doing well
    "needs_attention": 50,  # 50–69 = needs monitoring
    "concerning": 30,       # 30–49 = concerning
    # below 30 = critical
}

# Soft messages shown to the user based on their status.
# Never clinical language — always warm and encouraging.
SOFT_MESSAGES = {
    "stable": "You seem to be doing well today. Keep taking care of yourself.",
    "needs_attention": "Today looks a little quieter than usual. Small steps help — a glass of water or a short walk can make a difference.",
    "concerning": "It seems like today has been harder. You don't have to manage alone — reaching out to someone you trust is always a good idea.",
    "critical": "We noticed some signs that today may be difficult. Please consider calling a family member or your care worker.",
}

# ─────────────────────────────────────────────
# HELPER FUNCTIONS — convert text-based data
# from the database into numeric scores (0–100)
# ─────────────────────────────────────────────

def _parse_quality(value: Optional[str]) -> Optional[float]:
    """
    Converts a text quality value into a numeric score from 0 to 100.

    Data in the database may be in text form like "good", "poor"
    or as numbers "1"–"5" because users respond in natural language.
    This function normalises all values to the same scale.

    Examples:
        "excellent" → 100.0
        "good"      → 75.0
        "poor"      → 25.0
        "3" (1–5)   → 50.0  (scaled)
        "yes"       → 100.0
        "no"        → 20.0
    """
    if value is None:
        return None
    v = value.strip().lower()
    mapping = {
        "excellent": 100.0,
        "very good": 85.0,
        "good": 75.0,
        "ok": 60.0,
        "okay": 60.0,
        "fair": 50.0,
        "poor": 25.0,
        "bad": 15.0,
        "very bad": 5.0,
        "yes": 100.0,
        "no": 20.0,
    }
    if v in mapping:
        return mapping[v]
    # Try numeric value on 1–5 scale
    try:
        n = float(v)
        if 1 <= n <= 5:
            return (n - 1) / 4 * 100  # scale to 0–100
        if 0 <= n <= 100:
            return n
    except ValueError:
        pass
    return None


def _sleep_score(checkin: Optional[DailyCheckIn]) -> Optional[float]:
    """
    Gets the sleep score from the daily check-in.
    Returns None if no check-in exists — missing data is different from bad sleep.
    """
    if checkin is None:
        return None
    return _parse_quality(checkin.sleep_quality)


def _food_score(checkin: Optional[DailyCheckIn]) -> Optional[float]:
    """
    Gets the food score from the daily check-in.
    """
    if checkin is None:
        return None
    return _parse_quality(checkin.food_intake)


def _hydration_score(checkin: Optional[DailyCheckIn]) -> Optional[float]:
    """
    Gets the hydration score from the daily check-in.
    """
    if checkin is None:
        return None
    return _parse_quality(checkin.hydration)


def _mood_score(
    checkin: Optional[DailyCheckIn],
    risk_signals: list[str],
) -> Optional[float]:
    """
    Calculates the mood score from two sources — this is an example
    of combining data from different sources:

    1. Primarily from check-in data if available
    2. If no check-in exists, inferred from risk signals:
       - If loneliness or sadness was detected in the conversation → 30 points
       - Otherwise None (no information available)
    """
    if checkin is not None and checkin.mood is not None:
        score = _parse_quality(checkin.mood)
        if score is not None:
            return score

    # Infer mood from risk signals when no check-in is available
    negative_signals = {"sadness_loneliness", "emotional", "loneliness"}
    if any(s in risk_signals for s in negative_signals):
        return 30.0

    return None


def _social_score(message_count: int) -> float:
    """
    Calculates social activity score based on the number of messages sent today.

    Logic: each message = 16 points, maximum 80 points.
    5 or more messages = full social activity score.

    The maximum is capped at 80 rather than 100 because chat activity
    alone does not tell the full story of someone's social life.
    """
    return min(80.0, message_count * 16.0)


def _risk_to_wellbeing(avg_risk_score: Optional[float]) -> float:
    """
    Converts risk score (0–10) to wellbeing score (0–100).

    Inverse relationship: high risk = low wellbeing.
    Formula: 100 - (risk * 10)

    Examples:
        risk 0  → wellbeing 100
        risk 5  → wellbeing 50
        risk 10 → wellbeing 0

    If no risk data is available, a neutral level (70) is assumed.
    """
    if avg_risk_score is None:
        return 70.0
    return max(0.0, min(100.0, 100 - (avg_risk_score * 10)))


def _overall_score(
    mood: Optional[float],
    sleep: Optional[float],
    food: Optional[float],
    hydration: Optional[float],
    social: float,
    risk_wellbeing: float,
) -> tuple[float, float]:
    """
    Calculates the final wellbeing score by combining all metrics.

    Formula:
        final score = check_in_score * 0.70 + risk_score * 0.30

    Special case: if no check-in data is available at all, the score
    is calculated from social activity and risk signals only.

    Returns:
        (overall score 0–100, completeness 0–1)
        Completeness indicates what fraction of metrics had data.
        1.0 = all metrics present, 0.1 = no check-in data.
    """
    components = {
        "mood": mood,
        "sleep": sleep,
        "food": food,
        "hydration": hydration,
        "medication": None,  # not used in current model
        "social": social,
    }

    total_weight = 0.0
    weighted_sum = 0.0
    present = 0

    # Calculate weighted average only for metrics that have data
    for key, value in components.items():
        if value is not None:
            w = WEIGHTS[key]
            weighted_sum += value * w
            total_weight += w
            present += 1

    if total_weight == 0:
        # No check-in data — use only social activity and risk signal
        social_contribution = social / 100
        final = social_contribution * (1 - RISK_PENALTY_WEIGHT) + (risk_wellbeing / 100 * RISK_PENALTY_WEIGHT)
        return round(min(100.0, max(0.0, final * 100)), 1), 0.1

    # Normal calculation: combine check-in data (70%) and risk data (30%)
    checkin_score = weighted_sum / total_weight
    final = checkin_score * (1 - RISK_PENALTY_WEIGHT) + (risk_wellbeing / 100 * RISK_PENALTY_WEIGHT) * 100
    final_score = round(min(100.0, max(0.0, final)), 1)
    completeness = round(present / len(components), 2)

    return final_score, completeness


def _status_from_score(score: float) -> str:
    """
    Converts a numeric score into a text status label.
    Used for both database storage and UI display.
    """
    if score >= THRESHOLDS["stable"]:
        return "stable"
    if score >= THRESHOLDS["needs_attention"]:
        return "needs_attention"
    if score >= THRESHOLDS["concerning"]:
        return "concerning"
    return "critical"


# ─────────────────────────────────────────────
# MAIN FUNCTION — runs every night at 00:05 UTC
# scheduler.py calls this for each active user
# ─────────────────────────────────────────────

def aggregate_daily_wellbeing(
    user_id: int,
    target_date: date,
    db: Session,
) -> WellbeingDailyMetrics:
    """
    Calculates one user's wellbeing score for one day
    and saves the result to the wellbeing_daily_metrics table.

    This function is called in two contexts:
    1. From the scheduler automatically every night (for yesterday)
    2. From the wellbeing endpoint in real time when the user opens the trends view

    Upsert logic: if a row already exists for this user and date, update it.
    If not, create a new one. This prevents duplicate rows.
    """

    # ── STEP 1: Fetch the day's check-in data from the database ──────────
    # DailyCheckIn contains the user's answers to structured questions
    # (sleep, food, water, mood). May be None if the user did not fill it in.
    checkin = (
        db.query(DailyCheckIn)
        .filter(
            DailyCheckIn.user_id == user_id,
            DailyCheckIn.checkin_date == target_date,
        )
        .first()
    )

    # ── STEP 2: Fetch the day's risk analyses ────────────────────────────
    # RiskAnalysis contains the risk score and signals for each message.
    # Calculate the average daily risk and collect all signals.
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

    # Calculate average risk score for the day
    avg_risk = (
        sum(r.risk_score for r in risk_rows if r.risk_score is not None) / len(risk_rows)
        if risk_rows else None
    )

    # Collect all risk signals into a flat list (e.g. ["poor_sleep", "loneliness"])
    all_signals: list[str] = []
    for r in risk_rows:
        if r.signals_json:
            all_signals.extend(
                r.signals_json if isinstance(r.signals_json, list) else []
            )

    # ── STEP 3: Count messages for social activity score ─────────────────
    message_count = (
        db.query(ConversationMessage)
        .filter(
            ConversationMessage.user_id == user_id,
            ConversationMessage.created_at >= day_start,
            ConversationMessage.created_at <= day_end,
        )
        .count()
    )

    # ── STEP 4: Calculate individual metric scores ────────────────────────
    # Each helper function returns a value 0–100 or None if no data
    mood = _mood_score(checkin, all_signals)
    sleep = _sleep_score(checkin)
    food = _food_score(checkin)
    hydration = _hydration_score(checkin)
    social = _social_score(message_count)
    risk_wellbeing = _risk_to_wellbeing(avg_risk)

    # ── STEP 5: Calculate overall score and data completeness ─────────────
    # Combines all metrics using weighted average
    overall, completeness = _overall_score(mood, sleep, food, hydration, social, risk_wellbeing)

    # ── STEP 6: Determine status and soft message for the user ────────────
    status = _status_from_score(overall)
    soft_message = SOFT_MESSAGES[status]

    # ── STEP 7: Save result to database (upsert) ──────────────────────────
    # If a row already exists for today, update it.
    # If not, create a new row.
    existing = (
        db.query(WellbeingDailyMetrics)
        .filter(
            WellbeingDailyMetrics.user_id == user_id,
            WellbeingDailyMetrics.date == target_date,
        )
        .first()
    )

    row = existing if existing else WellbeingDailyMetrics(user_id=user_id, date=target_date)
    if not existing:
        db.add(row)

    # Update all fields with the newly calculated values
    row.mood_score = mood
    row.sleep_score = sleep
    row.food_score = food
    row.hydration_score = hydration
    row.medication_score = None
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