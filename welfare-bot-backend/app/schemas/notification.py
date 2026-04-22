from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class NotificationRead(BaseModel):
    id: int
    user_id: int
    care_contact_id: int | None = None
    risk_analysis_id: int | None = None
    channel: str
    message: str
    status: str
    sent_at: datetime | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class NotificationCreate(BaseModel):
    user_id: int
    care_contact_id: int | None = None
    risk_analysis_id: int | None = None
    channel: str = "sms"
    message: str
    status: str = "pending"


class NotificationUpdate(BaseModel):
    channel: str | None = None
    message: str | None = None
    status: str | None = None
    sent_at: datetime | None = None