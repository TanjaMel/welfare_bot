from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class DailyCheckInCreate(BaseModel):
    checkin_date: date
    period: str
    sleep_answer: str | None = None
    food_answer: str | None = None
    medication_answer: str | None = None
    mood_answer: str | None = None
    extra_notes: str | None = None


class DailyCheckInUpdate(BaseModel):
    period: str | None = None
    sleep_answer: str | None = None
    food_answer: str | None = None
    medication_answer: str | None = None
    mood_answer: str | None = None
    extra_notes: str | None = None
    completed_at: datetime | None = None


class DailyCheckInRead(BaseModel):
    id: int
    user_id: int
    checkin_date: date
    period: str
    sleep_answer: str | None = None
    food_answer: str | None = None
    medication_answer: str | None = None
    mood_answer: str | None = None
    extra_notes: str | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)