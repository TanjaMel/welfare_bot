from __future__ import annotations

from pydantic import BaseModel

from app.schemas.checkin import DailyCheckInRead
from app.schemas.notification import NotificationRead
from app.schemas.risk_analysis import RiskAnalysisResponse


class CheckinAnalysisResponse(BaseModel):
    checkin: DailyCheckInRead
    risk_analysis: RiskAnalysisResponse | None = None
    notifications: list[NotificationRead] = []