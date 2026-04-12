from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationCreate(BaseModel):
    care_contact_id: int
    risk_analysis_id: int
    channel: str
    message: str
    status: str = "pending"


class NotificationUpdate(BaseModel):
    channel: str | None = None
    message: str | None = None
    status: str | None = None
    sent_at: datetime | None = None


class NotificationRead(BaseModel):
    id: int
    user_id: int
    care_contact_id: int
    risk_analysis_id: int
    channel: str
    message: str
    status: str
    sent_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)