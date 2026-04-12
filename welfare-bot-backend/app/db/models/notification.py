from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    care_contact_id: Mapped[int] = mapped_column(ForeignKey("care_contacts.id"), index=True)
    risk_analysis_id: Mapped[int] = mapped_column(ForeignKey("risk_analyses.id"), index=True)

    channel: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="notifications")
    care_contact = relationship("CareContact", back_populates="notifications")
    risk_analysis = relationship("RiskAnalysis", back_populates="notifications")