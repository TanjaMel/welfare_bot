from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RiskAnalysisCreate(BaseModel):
    conversation_message_id: int | None = None
    daily_checkin_id: int | None = None
    category: str
    risk_level: str
    needs_family_notification: bool = False
    reason: str
    suggested_action: str
    model_version: str | None = None


class RiskAnalysisUpdate(BaseModel):
    conversation_message_id: int | None = None
    daily_checkin_id: int | None = None
    category: str | None = None
    risk_level: str | None = None
    needs_family_notification: bool | None = None
    reason: str | None = None
    suggested_action: str | None = None
    model_version: str | None = None


class RiskAnalysisRead(BaseModel):
    id: int
    user_id: int
    conversation_message_id: int | None = None
    daily_checkin_id: int | None = None
    category: str
    risk_level: str
    needs_family_notification: bool
    reason: str
    suggested_action: str
    model_version: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)