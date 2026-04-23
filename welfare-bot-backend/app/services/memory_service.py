from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models.conversation_message import ConversationMessage
from app.db.models.user import User


def build_memory_summary(messages: list[ConversationMessage], max_items: int = 6) -> str:
    recent = messages[-max_items:]

    summary_lines: list[str] = []
    for msg in recent:
        role = "User" if msg.role == "user" else "Assistant"
        content = (msg.content or "").strip().replace("\n", " ")
        if len(content) > 120:
            content = content[:117] + "..."
        summary_lines.append(f"{role}: {content}")

    return "\n".join(summary_lines)


def refresh_user_memory_summary(db: Session, user: User) -> None:
    messages = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.user_id == user.id)
        .order_by(ConversationMessage.created_at.asc())
        .all()
    )

    if not messages:
        return

    user.memory_summary = build_memory_summary(messages)
    user.memory_summary_updated_at = datetime.utcnow()
    user.memory_summary_message_count = len(messages)

    db.add(user)
    db.commit()
    db.refresh(user)