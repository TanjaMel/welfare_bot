from __future__ import annotations
from datetime import datetime
from typing import Any
from openai import OpenAI
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.db.models.conversation_message import ConversationMessage
from app.db.models.risk_event import RiskEvent
from app.db.models.user import User

settings = get_settings()
client = OpenAI(api_key=settings.openai_api_key)


def should_refresh_memory(user: User, total_user_messages: int) -> bool:
    """
    Refresh memory if enough new user messages appeared since last summary.
    """
    last_count = user.memory_summary_message_count or 0
    return (total_user_messages - last_count) >= 8


def get_total_user_message_count(db: Session, user_id: int) -> int:
    return (
        db.query(ConversationMessage)
        .filter(
            ConversationMessage.user_id == user_id,
            ConversationMessage.role == "user",
        )
        .count()
    )


def get_messages_for_summary(db: Session, user_id: int, limit: int = 20) -> list[ConversationMessage]:
    return (
        db.query(ConversationMessage)
        .filter(ConversationMessage.user_id == user_id)
        .order_by(ConversationMessage.id.desc())
        .limit(limit)
        .all()[::-1]
    )


def get_recent_risk_events_for_summary(db: Session, user_id: int, limit: int = 10) -> list[RiskEvent]:
    return (
        db.query(RiskEvent)
        .filter(RiskEvent.user_id == user_id)
        .order_by(RiskEvent.id.desc())
        .limit(limit)
        .all()[::-1]
    )


def build_rule_based_memory_block(
    user: User,
    risk_events: list[RiskEvent],
) -> str:
    if not risk_events:
        return ""

    lines: list[str] = []
    lines.append(f"Preferred language: {user.language or 'en'}.")

    repeated_categories: dict[str, int] = {}
    repeated_levels: dict[str, int] = {}

    for event in risk_events:
        repeated_categories[event.risk_category] = repeated_categories.get(event.risk_category, 0) + 1
        repeated_levels[event.risk_level] = repeated_levels.get(event.risk_level, 0) + 1

    if repeated_categories:
        top_categories = sorted(repeated_categories.items(), key=lambda x: x[1], reverse=True)[:3]
        lines.append(
            "Recent recurring risk categories: "
            + ", ".join(f"{category} ({count})" for category, count in top_categories)
            + "."
        )

    if repeated_levels:
        top_levels = sorted(repeated_levels.items(), key=lambda x: x[1], reverse=True)
        lines.append(
            "Recent risk levels seen: "
            + ", ".join(f"{level} ({count})" for level, count in top_levels)
            + "."
        )

    family_alerts = [event for event in risk_events if event.should_alert_family]
    if family_alerts:
        lines.append("There have been recent events where family alert may be needed.")

    return " ".join(lines).strip()


def build_summary_input(messages: list[ConversationMessage]) -> str:
    lines: list[str] = []

    for msg in messages:
        role = msg.role.upper()
        content = msg.content.strip().replace("\n", " ")
        lines.append(f"{role}: {content}")

    return "\n".join(lines)


def generate_memory_summary_with_llm(
    user: User,
    old_memory_summary: str | None,
    recent_messages: list[ConversationMessage],
    rule_based_memory_block: str,
) -> str:
    chat_history = build_summary_input(recent_messages)

    developer_prompt = f"""
You are creating a compact long-term conversation memory for a welfare support chatbot.

IMPORTANT:
- Write the summary in English only for internal system memory.
- Keep it concise, factual, and useful for future assistant responses.
- Do NOT write a conversation reply.
- Do NOT add empathy phrases.
- Do NOT include unnecessary details.
- Do NOT include greetings.

KEEP ONLY:
- preferred language
- recurring symptoms or wellbeing concerns
- repeated emotional patterns
- repeated safety concerns
- useful ongoing context for future replies

REMOVE:
- one-off casual details
- repetition
- wording that sounds like a response to the user

Current user preferred language: {user.language or 'en'}

Existing memory summary:
{old_memory_summary or "None"}

Structured risk memory:
{rule_based_memory_block or "None"}

Recent messages:
{chat_history}
"""

    response = client.responses.create(
        model=settings.openai_model,
        input=[
            {
                "role": "developer",
                "content": developer_prompt.strip(),
            }
        ],
    )

    summary = (response.output_text or "").strip()

    if not summary:
        summary = old_memory_summary or ""

    return summary


def refresh_user_memory_summary(db: Session, user: User) -> None:
    total_user_messages = get_total_user_message_count(db, user.id)

    if not should_refresh_memory(user, total_user_messages):
        return

    recent_messages = get_messages_for_summary(db, user.id, limit=20)
    recent_risk_events = get_recent_risk_events_for_summary(db, user.id, limit=10)

    rule_based_memory_block = build_rule_based_memory_block(
        user=user,
        risk_events=recent_risk_events,
    )

    summary = generate_memory_summary_with_llm(
        user=user,
        old_memory_summary=user.memory_summary,
        recent_messages=recent_messages,
        rule_based_memory_block=rule_based_memory_block,
    )

    user.memory_summary = summary
    user.memory_summary_updated_at = datetime.utcnow()
    user.memory_summary_message_count = total_user_messages

    db.add(user)
    db.commit()
    db.refresh(user)