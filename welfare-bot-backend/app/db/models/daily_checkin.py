from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DailyCheckIn(Base):
    __tablename__ = "daily_checkins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)

    checkin_date: Mapped[date] = mapped_column(Date)

    sleep_quality: Mapped[str | None] = mapped_column(String(50), nullable=True)
    food_intake: Mapped[str | None] = mapped_column(String(50), nullable=True)
    hydration: Mapped[str | None] = mapped_column(String(50), nullable=True)
    mood: Mapped[str | None] = mapped_column(String(50), nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)