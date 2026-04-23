from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.checkin import DailyCheckInRead
from app.schemas.notification import NotificationRead
from app.schemas.risk_analysis import RiskAnalysisRead


class DailyCheckInPipelineResponse(BaseModel):
    checkin: DailyCheckInRead
    risk_analysis: RiskAnalysisRead
    notifications: List[NotificationRead]
    display_reason: Optional[str] = None
    display_action: Optional[str] = None
    followup_questions: List[str] = Field(default_factory=list)
    closing: Optional[str] = None
    matched_signals: Dict[str, List[str]] = Field(default_factory=dict)