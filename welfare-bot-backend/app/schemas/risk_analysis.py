from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

class RiskAnalysisResponse(BaseModel):
    id: int
    user_id: int
    daily_checkin_id: int | None = None
    conversation_message_id: int | None = None
    category: str
    risk_level: str
    risk_score: int = 0
    needs_family_notification: bool = False
    reason: str | None = None
    suggested_action: str | None = None
    follow_up_question: str | None = None
    signals_json: list[str] = []
    reasons_json: list[str] = []
    should_alert_family: bool | None = None
    model_version: str | None = None
    created_at: datetime | None = None

    @field_validator("signals_json", "reasons_json", mode="before")
    @classmethod
    def coerce_null_to_list(cls, v: Any) -> list:
        if v is None:
            return []
        return v

    model_config = ConfigDict(from_attributes=True)


# Alias
RiskAnalysisRead = RiskAnalysisResponse


class RiskAnalysisCreate(BaseModel):
    user_id: int
    daily_checkin_id: int | None = None
    conversation_message_id: int | None = None
    category: str
    risk_level: str
    risk_score: int = 0
    needs_family_notification: bool = False
    reason: str | None = None
    suggested_action: str | None = None
    follow_up_question: str | None = None
    signals_json: list[str] = []
    reasons_json: list[str] = []
    model_version: str = "rule_engine_v1"


class RiskAnalysisUpdate(BaseModel):
    category: str | None = None
    risk_level: str | None = None
    risk_score: int | None = None
    needs_family_notification: bool | None = None
    reason: str | None = None
    suggested_action: str | None = None
    follow_up_question: str | None = None
    signals_json: list[str] | None = None
    reasons_json: list[str] | None = None