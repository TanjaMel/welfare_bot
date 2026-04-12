from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CareContactCreate(BaseModel):
    name: str
    relationship_type: str
    phone_number: str | None = None
    email: str | None = None
    preferred_notification_method: str = "sms"
    is_primary: bool = False
    notes: str | None = None


class CareContactUpdate(BaseModel):
    name: str | None = None
    relationship_type: str | None = None
    phone_number: str | None = None
    email: str | None = None
    preferred_notification_method: str | None = None
    is_primary: bool | None = None
    notes: str | None = None


class CareContactRead(BaseModel):
    id: int
    user_id: int
    name: str
    relationship_type: str
    phone_number: str | None = None
    email: str | None = None
    preferred_notification_method: str
    is_primary: bool
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)