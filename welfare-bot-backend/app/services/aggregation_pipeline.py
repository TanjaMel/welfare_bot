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

WEIGHTS = {
    "mood": 0.25,
    "sleep": 0.25,
    "food": 0.20,
    "hydration": 0.15,
    "medication": 0.10,
    "social": 0.05,
}

RISK_PENALTY_WEIGHT = 0.30

THRESHOLDS = {
    "stable": 70,
    "needs_attention": 50,
    "concerning": 30,
}

SOFT_MESSAGES = {
    "stable": "You seem to be doing well today. Keep taking care of yourself.",
    "needs_attention": "Today looks a little quieter than usual. Small steps help — a glass of water or a short walk can make a difference.",
    "concerning": "It seems like today has been harder. You don't have to manage alone — reaching out to someone you trust is always a good idea.",
    "critical": "We noticed some signs that today may be difficult. Please consider calling a family member or your care worker.",
}

# ─────────────────────────────────────────────
# SCORE HELPERS — handle string fields from DB
# ─────────────────────────────────────────────

def _parse_quality(value: Optional[str]) -> Optional[float]:
    """
    Converts string quality values to 0–100 score.
    Supports: 'good'/'excellent' → high, 'poor'/'bad' → low,
    numeric strings '1'–'5' → scaled.
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
    # Try numeric 1–5
    try:
        n = float(v)
        if 1 <= n <= 5:
            return (n - 1) / 4 * 100
        if 0 <= n <= 100:
            return n
    except ValueError:
        pass
    return None


def _sleep_score(checkin: Optional[DailyCheckIn]) -> Optional[float]:
    if checkin is None:
        return None
    return _parse_quality(checkin.sleep_quality)


def _food_score(checkin: Optional[DailyCheckIn]) -> Optional[float]:
    if checkin is None:
        return None
    return _parse_quality(checkin.food_intake)


def _hydration_score(checkin: Optional[DailyCheckIn]) -> Optional[float]:
    if checkin is None:
        return None
    return _parse_quality(checkin.hydration)


def _mood_score(
    checkin: Optional[DailyCheckIn],
    risk_signals: list[str],
) -> Optional[float]:
    if checkin is not None and checkin.mood is not None:
        score = _parse_quality(checkin.mood)
        if score is not None:
            return score

    # Infer from risk signals when no checkin
    negative_signals = {"sadness_loneliness", "emotional", "loneliness"}
    if any(s in risk_signals for s in negative_signals):
        return 30.0

    return None


def _social_score(message_count: int) -> float:
    return min(80.0, message_count * 16.0)


def _risk_to_wellbeing(avg_risk_score: Optional[float]) -> float:
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
    components = {
        "mood": mood,
        "sleep": sleep,
        "food": food,
        "hydration": hydration,
        "medication": None,  # not in current model
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
        # No checkin data — use risk signal and social only
        social_contribution = social / 100
        final = social_contribution * (1 - RISK_PENALTY_WEIGHT) + (risk_wellbeing / 100 * RISK_PENALTY_WEIGHT)
        return round(min(100.0, max(0.0, final * 100)), 1), 0.1

    checkin_score = weighted_sum / total_weight
    final = checkin_score * (1 - RISK_PENALTY_WEIGHT) + (risk_wellbeing / 100 * RISK_PENALTY_WEIGHT) * 100
    final_score = round(min(100.0, max(0.0, final)), 1)
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
# MAIN PIPELINE
# ─────────────────────────────────────────────

def aggregate_daily_wellbeing(
    user_id: int,
    target_date: date,
    db: Session,
) -> WellbeingDailyMetrics:
    # 1. Fetch today's check-in using correct field name
    checkin = (
        db.query(DailyCheckIn)
        .filter(
            DailyCheckIn.user_id == user_id,
            DailyCheckIn.checkin_date == target_date,
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

    all_signals: list[str] = []
    for r in risk_rows:
        if r.signals_json:
            all_signals.extend(
                r.signals_json if isinstance(r.signals_json, list) else []
            )

    # 3. Message count today
    message_count = (
        db.query(ConversationMessage)
        .filter(
            ConversationMessage.user_id == user_id,
            ConversationMessage.created_at >= day_start,
            ConversationMessage.created_at <= day_end,
        )
        .count()
    )

    # 4. Compute scores
    mood = _mood_score(checkin, all_signals)
    sleep = _sleep_score(checkin)
    food = _food_score(checkin)
    hydration = _hydration_score(checkin)
    social = _social_score(message_count)
    risk_wellbeing = _risk_to_wellbeing(avg_risk)

    # 5. Overall score
    overall, completeness = _overall_score(mood, sleep, food, hydration, social, risk_wellbeing)

    # 6. Status and message
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

    row = existing if existing else WellbeingDailyMetrics(user_id=user_id, date=target_date)
    if not existing:
        db.add(row)

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