from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models.notification import Notification
from app.db.models.risk_analysis import RiskAnalysis


def build_notification_message(risk_analysis: RiskAnalysis) -> str:
    base = (
        f"User {risk_analysis.user_id} has {risk_analysis.risk_level} risk "
        f"in category '{risk_analysis.category}'."
    )

    if risk_analysis.suggested_action:
        base += f" Suggested action: {risk_analysis.suggested_action}"

    return base


def create_notification_for_risk(
    db: Session,
    *,
    risk_analysis: RiskAnalysis,
    care_contact_id: int | None = None,
    channel: str = "sms",
) -> Notification:
    notification = Notification(
        user_id=risk_analysis.user_id,
        care_contact_id=care_contact_id,
        risk_analysis_id=risk_analysis.id,
        channel=channel,
        message=build_notification_message(risk_analysis),
        status="pending",
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification