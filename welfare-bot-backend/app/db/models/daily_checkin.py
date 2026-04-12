from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DailyCheckIn(Base):
    __tablename__ = "daily_checkins"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    checkin_date: Mapped[date] = mapped_column(Date, index=True)
    period: Mapped[str] = mapped_column(String(20))

    sleep_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    food_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    medication_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    mood_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    user = relationship("User", back_populates="daily_checkins")
    risk_analyses = relationship("RiskAnalysis", back_populates="daily_checkin")