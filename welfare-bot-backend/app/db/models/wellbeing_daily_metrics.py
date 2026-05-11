from datetime import date, datetime
from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class WellbeingDailyMetrics(Base):
    """
    Pre-aggregated daily wellbeing snapshot per user.

    This table is the central output of the data pipeline.
    It is computed once per day by aggregation_pipeline.py
    from three data sources:
        - daily_checkins      (structured answers: sleep, food, water, mood)
        - conversation_messages (message count → social activity)
        - risk_analyses       (risk signals and scores from conversations)

    Design principle: never expose raw risk scores to the user.
    Only soft_message and status are shown in the UI.
    Raw scores are used internally by ML models and the admin dashboard.
    """
    __tablename__ = "wellbeing_daily_metrics"

    # ── Primary key ───────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # ── Foreign key — links this row to a specific user ───────────────────
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # ── Date — one row per user per day ───────────────────────────────────
    # The unique index below enforces this constraint at the database level.
    date: Mapped[date] = mapped_column(Date, nullable=False)

    # ── Individual metric scores (0–100 each) ─────────────────────────────
    # None means no data was available for that metric on that day.
    # Missing data is treated differently from a score of 0.
    # These are computed by the helper functions in aggregation_pipeline.py.
    mood_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    food_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    hydration_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    medication_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    social_activity_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Risk score — derived from risk_analyses table ─────────────────────
    # Average of all risk scores from conversations on this day (0–10 scale).
    # Converted to 0–100 scale before being used in the overall score.
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Overall wellbeing score (0–100) ───────────────────────────────────
    # Weighted composite of all metric scores.
    # Formula: check_in_score * 0.70 + risk_score * 0.30
    # Computed by _overall_score() in aggregation_pipeline.py
    overall_wellbeing_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Human-readable status label ───────────────────────────────────────
    # Derived from overall_wellbeing_score using fixed thresholds:
    #   stable          → score >= 70
    #   needs_attention → score >= 50
    #   concerning      → score >= 30
    #   critical        → score < 30
    # This label is used in the UI and admin dashboard — never raw numbers.
    status: Mapped[str] = mapped_column(String(20), default="stable")

    # ── Soft message shown to the user ────────────────────────────────────
    # Always warm and encouraging language — never clinical terms.
    # One of four fixed messages mapped from status in SOFT_MESSAGES dict.
    soft_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Data completeness (0.0–1.0) ───────────────────────────────────────
    # Fraction of expected metrics that had actual data on this day.
    # Examples:
    #   1.0 = all 6 metrics present (sleep, food, water, mood, medication, social)
    #   0.5 = 3 out of 6 metrics present
    #   0.1 = no check-in data, only social activity and risk signals
    # Used by data_quality.py to flag users with poor data coverage.
    data_completeness: Mapped[float] = mapped_column(Float, default=0.0)

    # ── Timestamps ────────────────────────────────────────────────────────
    # created_at: when the row was first inserted
    # updated_at: when the row was last recalculated
    # A row can be recalculated multiple times in a day if the user
    # keeps chatting — the scheduler updates it each night.
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # ── Database indexes ──────────────────────────────────────────────────
    __table_args__ = (
        # Composite index for the most common query pattern:
        # "get all rows for this user ordered by date"
        # Used by ML models, trend charts, and the aggregation pipeline.
        Index("ix_wellbeing_user_date", "user_id", "date"),

        # Unique constraint: enforces one row per user per day at DB level.
        # The aggregation pipeline uses upsert logic to respect this constraint.
        Index("uq_wellbeing_user_date", "user_id", "date", unique=True),
    )