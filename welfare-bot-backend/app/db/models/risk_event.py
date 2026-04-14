from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class RiskEvent(Base):
    __tablename__ = "risk_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Current app model = one conversation thread per user.
    # For now this stores user_id as the active thread identifier.
    conversation_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    message_id: Mapped[int] = mapped_column(ForeignKey("conversation_messages.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    risk_level: Mapped[str] = mapped_column(String(20), index=True)
    risk_score: Mapped[int] = mapped_column(Integer)
    risk_category: Mapped[str] = mapped_column(String(50), index=True)

    signals_json: Mapped[list] = mapped_column(JSON, default=list)
    reasons_json: Mapped[list] = mapped_column(JSON, default=list)
    suggested_action: Mapped[str] = mapped_column(Text)
    should_alert_family: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)