from datetime import datetime

from pydantic import BaseModel, Field


class CallSessionCreate(BaseModel):
    user_id: int = Field(..., gt=0)


class CallSessionRead(BaseModel):
    id: int
    user_id: int
    status: str
    transcript: str | None
    summary: str | None
    mood_score: int | None
    escalation_level: str | None
    scheduled_at: datetime | None
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}