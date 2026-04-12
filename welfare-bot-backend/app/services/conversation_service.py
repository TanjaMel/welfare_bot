import json

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.conversation_message import ConversationMessage
from app.db.models.conversation_session import ConversationSession
from app.db.models.user import User
from app.integrations.openai_client import client
from app.schemas.conversation import (
    ConversationMessageRead,
    ConversationMessageRequest,
    ConversationMessageResponse,
    ConversationSummary,
)

settings = get_settings()

SYSTEM_PROMPT = """
You are a warm, calm, safe AI wellbeing assistant for elderly users.
You speak clearly and simply.
You never claim to be human.
You do not diagnose illnesses.
You ask at most one follow-up question at a time.
You answer in Finnish unless the user profile clearly suggests another language.

Return JSON with this exact shape:
{
  "assistant_message": "string",
  "summary": {
    "mood": "string or null",
    "concern_level": "low | medium | high | null",
    "suggested_next_action": "string or null"
  },
  "risk_flags": ["string"]
}
"""


def _get_or_create_active_session(db: Session, user_id: int) -> ConversationSession:
    session = (
        db.query(ConversationSession)
        .filter(
            ConversationSession.user_id == user_id,
            ConversationSession.status == "active",
            ConversationSession.channel == "chat",
        )
        .order_by(ConversationSession.id.desc())
        .first()
    )

    if session:
        return session

    session = ConversationSession(
        user_id=user_id,
        channel="chat",
        status="active",
    )
    db.add(session)
    db.flush()
    return session


def _call_openai(user: User, message: str) -> tuple[str, ConversationSummary, list[str]]:
    user_context = {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "language": user.language,
        "is_active": user.is_active,
    }

    prompt = f"""
User profile:
{json.dumps(user_context, ensure_ascii=False)}

User message:
{message}

Respond only with valid JSON.
"""

    response = client.responses.create(
        model=settings.openai_model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )

    text_output = getattr(response, "output_text", None)
    if not text_output:
        raise ValueError("OpenAI response was empty")

    try:
        parsed = json.loads(text_output)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON returned by OpenAI: {text_output}") from exc

    summary_data = parsed.get("summary", {})
    summary = ConversationSummary(
        mood=summary_data.get("mood"),
        concern_level=summary_data.get("concern_level"),
        suggested_next_action=summary_data.get("suggested_next_action"),
    )
    risk_flags = parsed.get("risk_flags", [])

    return parsed["assistant_message"], summary, risk_flags


def create_conversation_message(
    db: Session,
    payload: ConversationMessageRequest,
) -> ConversationMessageResponse:
    user = db.query(User).filter(User.id == payload.user_id).first()
    if user is None:
        raise ValueError("User not found")

    session = _get_or_create_active_session(db, payload.user_id)

    user_message = ConversationMessage(
        session_id=session.id,
        user_id=payload.user_id,
        role="user",
        message_text=payload.message,
        message_type="text",
        source="app",
    )
    db.add(user_message)
    db.flush()

    assistant_message_text, summary, risk_flags = _call_openai(user, payload.message)

    assistant_message = ConversationMessage(
        session_id=session.id,
        user_id=payload.user_id,
        role="assistant",
        message_text=assistant_message_text,
        message_type="text",
        source="app",
        mood=summary.mood,
        concern_level=summary.concern_level,
        suggested_next_action=summary.suggested_next_action,
        risk_flags_json=json.dumps(risk_flags, ensure_ascii=False),
    )
    db.add(assistant_message)

    db.commit()
    db.refresh(user_message)
    db.refresh(assistant_message)
    db.refresh(session)

    return ConversationMessageResponse(
        assistant_message=assistant_message_text,
        summary=summary,
        risk_flags=risk_flags,
        session_id=session.id,
        user_message_id=user_message.id,
        assistant_message_id=assistant_message.id,
    )


def list_conversation_messages(db: Session, user_id: int) -> list[ConversationMessageRead]:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise ValueError("User not found")

    messages = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.user_id == user_id)
        .order_by(ConversationMessage.id.asc())
        .all()
    )

    result: list[ConversationMessageRead] = []
    for msg in messages:
        risk_flags: list[str] = []
        if msg.risk_flags_json:
            try:
                risk_flags = json.loads(msg.risk_flags_json)
            except json.JSONDecodeError:
                risk_flags = []

        result.append(
            ConversationMessageRead(
                id=msg.id,
                session_id=msg.session_id,
                user_id=msg.user_id,
                role=msg.role,
                message_text=msg.message_text,
                message_type=msg.message_type,
                source=msg.source,
                mood=msg.mood,
                concern_level=msg.concern_level,
                suggested_next_action=msg.suggested_next_action,
                risk_flags=risk_flags,
                created_at=msg.created_at,
            )
        )

    return result