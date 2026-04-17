from __future__ import annotations
from datetime import datetime
from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    phone_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    language: Mapped[str] = mapped_column(String(10), default="en")
    timezone: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    memory_summary: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    memory_summary_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        default=None,
    )
    memory_summary_message_count: Mapped[int] = mapped_column(default=0)

    conversation_messages = relationship("ConversationMessage", back_populates="user")
    care_contacts = relationship("CareContact", back_populates="user")
    daily_checkins = relationship("DailyCheckIn", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    risk_analyses = relationship("RiskAnalysis", back_populates="user")
    risk_events = relationship("RiskEvent")