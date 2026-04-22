from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class DailyCheckInCreate(BaseModel):
    user_id: int
    checkin_date: date
    sleep_quality: str | None = None
    food_intake: str | None = None
    hydration: str | None = None
    mood: str | None = None
    notes: str | None = None


class DailyCheckInRead(BaseModel):
    id: int
    user_id: int
    checkin_date: date
    sleep_quality: str | None = None
    food_intake: str | None = None
    hydration: str | None = None
    mood: str | None = None
    notes: str | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class DailyCheckInUpdate(BaseModel):
    checkin_date: date | None = None
    sleep_quality: str | None = None
    food_intake: str | None = None
    hydration: str | None = None
    mood: str | None = None
    notes: str | None = None