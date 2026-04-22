from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RiskAnalysis(Base):
    __tablename__ = "risk_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    conversation_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    daily_checkin_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    category: Mapped[str] = mapped_column(String(50))
    risk_level: Mapped[str] = mapped_column(String(20))
    risk_score: Mapped[int] = mapped_column(Integer, default=0)

    # Real DB column name is needs_family_notification
    needs_family_notification: Mapped[bool] = mapped_column(Boolean, default=False)

    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    follow_up_question: Mapped[str | None] = mapped_column(Text, nullable=True)

    signals_json: Mapped[list] = mapped_column(JSONB, default=list)
    reasons_json: Mapped[list] = mapped_column(JSONB, default=list)

    # Added by migration — nullable to not break old rows
    should_alert_family: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)

    model_version: Mapped[str | None] = mapped_column(String(50), default="rule_engine_v1")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)