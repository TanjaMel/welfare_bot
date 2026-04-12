from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RiskAnalysis(Base):
    __tablename__ = "risk_analyses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    conversation_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversation_messages.id"),
        nullable=True,
        index=True,
    )
    daily_checkin_id: Mapped[int | None] = mapped_column(
        ForeignKey("daily_checkins.id"),
        nullable=True,
        index=True,
    )

    category: Mapped[str] = mapped_column(String(50))
    risk_level: Mapped[str] = mapped_column(String(20))
    needs_family_notification: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str] = mapped_column(Text)
    suggested_action: Mapped[str] = mapped_column(String(50))
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="risk_analyses")
    conversation_message = relationship("ConversationMessage", back_populates="risk_analyses")
    daily_checkin = relationship("DailyCheckIn", back_populates="risk_analyses")
    notifications = relationship("Notification", back_populates="risk_analysis")