from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models.daily_checkin import DailyCheckIn
from app.db.models.notification import Notification
from app.db.models.risk_analysis import RiskAnalysis
from app.schemas.checkin import DailyCheckInCreate
from app.services.notification_service import create_notification_for_risk
from app.services.risk_analysis_service import analyze_checkin_answers


def run_checkin_pipeline(db: Session, payload: DailyCheckInCreate) -> tuple[DailyCheckIn, RiskAnalysis, list[Notification]]:
    checkin = DailyCheckIn(
        user_id=payload.user_id,
        checkin_date=payload.checkin_date,
        sleep_quality=payload.sleep_quality,
        food_intake=payload.food_intake,
        hydration=payload.hydration,
        mood=payload.mood,
        notes=payload.notes,
    )
    db.add(checkin)
    db.commit()
    db.refresh(checkin)

    analysis_result = analyze_checkin_answers(checkin)

    risk_analysis = RiskAnalysis(
        user_id=checkin.user_id,
        daily_checkin_id=checkin.id,
        category=analysis_result["category"],
        risk_level=analysis_result["risk_level"],
        risk_score=analysis_result["risk_score"],
        reason=analysis_result["reason"],
        suggested_action=analysis_result["suggested_action"],
        follow_up_question=analysis_result["follow_up_question"],
        signals_json=analysis_result["signals_json"],
        reasons_json=analysis_result["reasons_json"],
        should_alert_family=analysis_result["should_alert_family"],
        model_version=analysis_result["model_version"],
    )
    db.add(risk_analysis)
    db.commit()
    db.refresh(risk_analysis)

    notifications: list[Notification] = []
    if risk_analysis.should_alert_family or risk_analysis.risk_level in {"high", "critical"}:
        notifications.append(
            create_notification_for_risk(
                db,
                risk_analysis=risk_analysis,
            )
        )

    return checkin, risk_analysis, notifications