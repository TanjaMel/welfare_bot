from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.conversation_message import ConversationMessage
from app.db.models.risk_analysis import RiskAnalysis


def _date_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _time_segment(dt: datetime) -> str:
    hour = dt.hour
    if 6 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "afternoon"
    if 18 <= hour < 24:
        return "evening"
    return "night"


def get_user_analytics_summary(db: Session, user_id: int) -> dict[str, Any]:
    since_14 = datetime.utcnow() - timedelta(days=14)
    since_30 = datetime.utcnow() - timedelta(days=30)

    risks = (
        db.query(RiskAnalysis)
        .filter(RiskAnalysis.user_id == user_id, RiskAnalysis.created_at >= since_30)
        .order_by(RiskAnalysis.created_at.asc())
        .all()
    )

    messages = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.user_id == user_id, ConversationMessage.created_at >= since_14)
        .all()
    )

    by_day_scores: dict[str, list[int]] = defaultdict(list)
    level_counter: Counter[str] = Counter()
    category_counter: Counter[str] = Counter()

    for risk in risks:
        key = _date_key(risk.created_at)
        by_day_scores[key].append(risk.risk_score)
        level_counter[risk.risk_level] += 1
        category_counter[risk.category] += 1

    trend = []
    for key in sorted(by_day_scores.keys()):
        scores = by_day_scores[key]
        trend.append(
            {
                "date": key,
                "avg_score": round(sum(scores) / len(scores), 2),
                "count": len(scores),
            }
        )

    time_of_day: Counter[str] = Counter()
    weekday_vs_weekend = {"weekday": 0, "weekend": 0}
    messages_by_date: Counter[str] = Counter()
    messages_by_language: Counter[str] = Counter()

    for msg in messages:
        time_of_day[_time_segment(msg.created_at)] += 1
        messages_by_date[_date_key(msg.created_at)] += 1

        if msg.created_at.weekday() < 5:
            weekday_vs_weekend["weekday"] += 1
        else:
            weekday_vs_weekend["weekend"] += 1

        text = (msg.content or "").lower()
        if any(word in text for word in [" minä ", " olen ", " huimaa ", " yksinäinen "]):
            messages_by_language["fi"] += 1
        elif any(word in text for word in [" jag ", " trött ", " ensam "]):
            messages_by_language["sv"] += 1
        else:
            messages_by_language["en"] += 1

    repeated_loneliness_streak = sum(1 for r in reversed(risks[-7:]) if r.category == "emotional")
    nutrition_hydration_streak = sum(1 for r in reversed(risks[-7:]) if r.category == "nutrition_hydration")
    consecutive_high_risk_days = len({k for k, v in by_day_scores.items() if max(v) >= 7})

    risk_increasing = False
    if len(trend) >= 3:
        last = trend[-3:]
        risk_increasing = last[0]["avg_score"] < last[1]["avg_score"] < last[2]["avg_score"]

    top_categories = [
        {"category": cat, "count": count}
        for cat, count in category_counter.most_common(5)
    ]

    return {
        "trend": trend,
        "risk_increasing": risk_increasing,
        "consecutive_high_risk_days": consecutive_high_risk_days,
        "repeated_loneliness_streak": repeated_loneliness_streak,
        "nutrition_hydration_streak": nutrition_hydration_streak,
        "distributions": {
            "risk_levels": dict(level_counter),
            "risk_categories": dict(category_counter),
        },
        "segmentation": {
            "time_of_day": dict(time_of_day),
            "weekday_vs_weekend": weekday_vs_weekend,
            "messages_by_date": dict(messages_by_date),
            "messages_by_language": dict(messages_by_language),
        },
        "top_categories": top_categories,
    }