from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    message_type: Mapped[str] = mapped_column(String(30), default="free_chat")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # NEW risk metadata on each user message
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True, default=None)
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    risk_category: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)

    user = relationship("User", back_populates="conversation_messages")
    risk_analyses = relationship("RiskAnalysis", back_populates="conversation_message")