from datetime import date, datetime
from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class WellbeingDailyMetrics(Base):
    """
    Pre-aggregated daily wellbeing snapshot per user.
    Computed once per day from daily_checkins, conversation_messages, risk_analyses.
    Never expose raw risk scores to the user — use soft_message and status only.
    """
    __tablename__ = "wellbeing_daily_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)

    # Component scores (0–100, None = no data for that day)
    mood_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    food_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    hydration_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    medication_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    social_activity_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Derived from risk_analyses
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Weighted composite (see scoring logic below)
    overall_wellbeing_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Human-readable output — never raw numbers
    status: Mapped[str] = mapped_column(String(20), default="stable")
    # stable | needs_attention | concerning | critical
    soft_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Data quality: how many signals contributed to this row
    data_completeness: Mapped[float] = mapped_column(Float, default=0.0)
    # 0.0–1.0, e.g. 0.5 = half the expected signals were present

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        # Primary access pattern: get all rows for a user ordered by date
        Index("ix_wellbeing_user_date", "user_id", "date"),
        # Uniqueness: one row per user per day
        Index("uq_wellbeing_user_date", "user_id", "date", unique=True),
    )