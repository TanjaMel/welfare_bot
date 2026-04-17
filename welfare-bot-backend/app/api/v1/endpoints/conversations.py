from __future__ import annotations
from typing import Iterator
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.core.config import get_settings
from app.db.models.conversation_message import ConversationMessage as ConversationMessageDB
from app.db.models.notification import Notification
from app.db.models.risk_event import RiskEvent
from app.db.models.user import User
from app.services.memory_service import refresh_user_memory_summary
from app.services.response_guard_service import (
    fallback_message_for_language,
    is_mixed_language,
)
from app.services.risk_service import SUPPORTED_LANGUAGES, assess, detect_language
from app.services.token_service import trim_input_items_to_token_budget
from app.services.validation_service import validate_user_message

router = APIRouter(prefix="/conversations", tags=["conversations"])

settings = get_settings()
client = OpenAI(api_key=settings.openai_api_key)


class ConversationMessageRead(BaseModel):
    id: int
    role: str
    content: str
    created_at: str | None = None
    risk_level: str | None = None
    risk_score: int | None = None
    risk_category: str | None = None


class SendMessageRequest(BaseModel):
    user_id: int
    message: str
    language: str | None = None


class SendMessageResponse(BaseModel):
    reply: str
    risk_analysis: dict | None = None
    notifications: list[dict] = []
    mode: str = "non_stream"


def to_message_read(message: ConversationMessageDB) -> ConversationMessageRead:
    return ConversationMessageRead(
        id=message.id,
        role=message.role,
        content=message.content,
        created_at=message.created_at.isoformat() if message.created_at else None,
        risk_level=message.risk_level,
        risk_score=message.risk_score,
        risk_category=message.risk_category,
    )


def resolve_language(user: User, payload_language: str | None, text: str) -> str:
    if payload_language and payload_language in SUPPORTED_LANGUAGES:
        return payload_language

    user_language = getattr(user, "language", None)
    if user_language and user_language in SUPPORTED_LANGUAGES:
        return user_language

    return detect_language(text)


def language_label(language_code: str) -> str:
    normalized = (language_code or "en").lower()

    if normalized.startswith("fi"):
        return "Finnish"
    if normalized.startswith("sv"):
        return "Swedish"
    return "English"


def get_max_input_tokens() -> int:
    return 6000


def get_recent_user_messages(
    db: Session,
    user_id: int,
    current_message_id: int | None = None,
) -> list[str]:
    messages = (
        db.query(ConversationMessageDB)
        .filter(
            ConversationMessageDB.user_id == user_id,
            ConversationMessageDB.role == "user",
        )
        .order_by(ConversationMessageDB.id.desc())
        .limit(5)
        .all()
    )

    texts: list[str] = []
    for msg in messages:
        if current_message_id is not None and msg.id == current_message_id:
            continue
        texts.append(msg.content)

    return list(reversed(texts))


def build_input_items(
    db: Session,
    user: User,
    language: str,
    risk_assessment: dict,
) -> list[dict]:
    messages = (
        db.query(ConversationMessageDB)
        .filter(ConversationMessageDB.user_id == user.id)
        .order_by(ConversationMessageDB.id.asc())
        .all()
    )

    target_language = language_label(language)

    developer_prompt = f"""
You are a supportive welfare assistant for older adults.

LANGUAGE RULES:
- You MUST reply ONLY in {target_language}.
- Never mix languages in the same reply.
- Never add translations.
- Never switch language mid-response.
- If the user's message is in another language, still reply only in {target_language}.

ROLE:
- You are supportive, calm, practical, and human.
- Keep replies clear, warm, and not overly long.
- Do not sound robotic.
- Do not diagnose medical conditions.

RISK CONTEXT (already decided by backend):
- risk_level: {risk_assessment["risk_level"]}
- risk_category: {risk_assessment["category"]}
- detected_signals: {", ".join(risk_assessment["signals"]) if risk_assessment["signals"] else "none"}
- follow_up_question: {risk_assessment["follow_up_question"]}
- suggested_action: {risk_assessment["suggested_action"]}
- should_alert_family: {risk_assessment["should_alert_family"]}

SAFETY RULES:
- You must NOT decide or change the risk level.
- You only generate the response text.
- LOW:
  - give a gentle supportive response
  - follow-up question is optional
- MEDIUM:
  - mention that the symptoms may affect wellbeing
  - ask exactly one follow-up question
- HIGH:
  - express stronger concern
  - encourage immediate support / check-in
  - ask exactly one safety-oriented follow-up question
- CRITICAL:
  - clearly recommend urgent help immediately
  - be calm but direct
  - tell the user to contact emergency help / urgent care / trusted person now

STYLE:
- calm
- human
- non-alarmist unless risk_level is CRITICAL
- practical
- short paragraphs
- no bullet points in the reply

OUTPUT RULES:
- Return plain text only.
- No headings.
- No translations.
- No language mixing.
""".strip()

    items: list[dict] = [
        {
            "role": "developer",
            "content": developer_prompt,
        }
    ]

    if user.memory_summary:
        items.append(
            {
                "role": "developer",
                "content": f"Long-term memory summary:\n{user.memory_summary}",
            }
        )

    for msg in messages:
        if msg.role in ("user", "assistant"):
            items.append(
                {
                    "role": msg.role,
                    "content": msg.content,
                }
            )

    return trim_input_items_to_token_budget(
        items=items,
        model_name=settings.openai_model,
        max_input_tokens=get_max_input_tokens(),
    )


def maybe_create_risk_event(
    db: Session,
    user_id: int,
    message_id: int,
    risk_assessment: dict,
) -> RiskEvent | None:
    should_create = (
        risk_assessment["risk_level"] in {"medium", "high", "critical"}
        or risk_assessment["should_alert_family"]
    )

    if not should_create:
        return None

    event = RiskEvent(
        conversation_id=user_id,
        message_id=message_id,
        user_id=user_id,
        risk_level=risk_assessment["risk_level"],
        risk_score=risk_assessment["score"],
        risk_category=risk_assessment["category"],
        signals_json=risk_assessment["signals"],
        reasons_json=risk_assessment["reasons"],
        suggested_action=risk_assessment["suggested_action"],
        should_alert_family=risk_assessment["should_alert_family"],
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def should_stream_reply(risk_level: str) -> bool:
    return risk_level in {"low", "medium"}


def generate_non_stream_reply(
    db: Session,
    user: User,
    language: str,
    risk_assessment: dict,
) -> str:
    response = client.responses.create(
        model=settings.openai_model,
        input=build_input_items(
            db=db,
            user=user,
            language=language,
            risk_assessment=risk_assessment,
        ),
    )

    assistant_text = response.output_text or "Sorry, I could not generate a reply."

    if is_mixed_language(assistant_text, language):
        assistant_text = fallback_message_for_language(
            language=language,
            risk_level=risk_assessment["risk_level"],
            follow_up_question=risk_assessment["follow_up_question"],
        )

    return assistant_text


@router.get("/{user_id}/messages", response_model=list[ConversationMessageRead])
def get_messages(user_id: int, db: Session = Depends(get_db)) -> list[ConversationMessageRead]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    messages = (
        db.query(ConversationMessageDB)
        .filter(ConversationMessageDB.user_id == user_id)
        .order_by(ConversationMessageDB.id.asc())
        .all()
    )

    return [to_message_read(msg) for msg in messages]


@router.get("/{user_id}/risk-analysis")
def get_user_risk_analysis(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    events = (
        db.query(RiskEvent)
        .filter(RiskEvent.user_id == user_id)
        .order_by(RiskEvent.id.desc())
        .all()
    )

    return [
        {
            "id": e.id,
            "user_id": e.user_id,
            "conversation_message_id": e.message_id,
            "category": e.risk_category,
            "risk_level": e.risk_level,
            "needs_family_notification": e.should_alert_family,
            "reason": " | ".join(e.reasons_json) if e.reasons_json else "",
            "suggested_action": e.suggested_action,
            "model_version": "risk_engine_v1",
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in events
    ]


@router.get("/{user_id}/notifications")
def get_user_notifications(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.id.desc())
        .all()
    )

    return [
        {
            "id": n.id,
            "user_id": n.user_id,
            "care_contact_id": n.care_contact_id,
            "risk_analysis_id": n.risk_analysis_id,
            "channel": n.channel,
            "message": n.message,
            "status": n.status,
            "sent_at": n.sent_at.isoformat() if n.sent_at else None,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in notifications
    ]


@router.post("/message", response_model=SendMessageResponse)
def send_message(
    payload: SendMessageRequest,
    db: Session = Depends(get_db),
) -> SendMessageResponse:
    raw_text = payload.message

    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    recent_user_messages = get_recent_user_messages(
        db=db,
        user_id=payload.user_id,
        current_message_id=None,
    )

    validation = validate_user_message(
        text=raw_text,
        recent_user_messages=recent_user_messages,
    )

    if not validation.is_valid:
        raise HTTPException(status_code=400, detail=validation.error)

    user_text = validation.cleaned_text
    language = resolve_language(user, payload.language, user_text)

    user_message = ConversationMessageDB(
        user_id=payload.user_id,
        role="user",
        content=user_text,
        message_type="free_chat",
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    recent_user_messages = get_recent_user_messages(
        db=db,
        user_id=payload.user_id,
        current_message_id=user_message.id,
    )

    risk_assessment = assess(
        current_message=user_text,
        recent_user_messages=recent_user_messages,
        preferred_language=language,
        elderly=True,
    )

    user_message.risk_level = risk_assessment["risk_level"]
    user_message.risk_score = risk_assessment["score"]
    user_message.risk_category = risk_assessment["category"]
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    maybe_create_risk_event(
        db=db,
        user_id=payload.user_id,
        message_id=user_message.id,
        risk_assessment=risk_assessment,
    )

    try:
        assistant_text = generate_non_stream_reply(
            db=db,
            user=user,
            language=language,
            risk_assessment=risk_assessment,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI error: {str(e)}")

    assistant_message = ConversationMessageDB(
        user_id=payload.user_id,
        role="assistant",
        content=assistant_text,
        message_type="free_chat",
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    refresh_user_memory_summary(db=db, user=user)

    return SendMessageResponse(
        reply=assistant_text,
        risk_analysis=risk_assessment,
        notifications=[],
        mode="non_stream",
    )


@router.post("/message/stream")
def send_message_stream(
    payload: SendMessageRequest,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    raw_text = payload.message

    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    recent_user_messages = get_recent_user_messages(
        db=db,
        user_id=payload.user_id,
        current_message_id=None,
    )

    validation = validate_user_message(
        text=raw_text,
        recent_user_messages=recent_user_messages,
    )

    if not validation.is_valid:
        raise HTTPException(status_code=400, detail=validation.error)

    user_text = validation.cleaned_text
    language = resolve_language(user, payload.language, user_text)

    user_message = ConversationMessageDB(
        user_id=payload.user_id,
        role="user",
        content=user_text,
        message_type="free_chat",
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    recent_user_messages = get_recent_user_messages(
        db=db,
        user_id=payload.user_id,
        current_message_id=user_message.id,
    )

    risk_assessment = assess(
        current_message=user_text,
        recent_user_messages=recent_user_messages,
        preferred_language=language,
        elderly=True,
    )

    user_message.risk_level = risk_assessment["risk_level"]
    user_message.risk_score = risk_assessment["score"]
    user_message.risk_category = risk_assessment["category"]
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    maybe_create_risk_event(
        db=db,
        user_id=payload.user_id,
        message_id=user_message.id,
        risk_assessment=risk_assessment,
    )

    if not should_stream_reply(risk_assessment["risk_level"]):
        raise HTTPException(
            status_code=400,
            detail="Streaming is disabled for high and critical risk messages. Use /message instead.",
        )

    input_items = build_input_items(
        db=db,
        user=user,
        language=language,
        risk_assessment=risk_assessment,
    )

    def generate() -> Iterator[str]:
        collected: list[str] = []

        try:
            stream = client.responses.create(
                model=settings.openai_model,
                input=input_items,
                stream=True,
            )

            for event in stream:
                event_type = getattr(event, "type", "")

                if event_type == "response.output_text.delta":
                    delta = getattr(event, "delta", "")
                    if delta:
                        collected.append(delta)
                        yield delta
                elif event_type == "error":
                    message = getattr(event, "message", "Streaming error")
                    raise RuntimeError(message)

            assistant_text = "".join(collected).strip()
            if not assistant_text:
                assistant_text = "Sorry, I could not generate a reply."

            if is_mixed_language(assistant_text, language):
                assistant_text = fallback_message_for_language(
                    language=language,
                    risk_level=risk_assessment["risk_level"],
                    follow_up_question=risk_assessment["follow_up_question"],
                )

            assistant_message = ConversationMessageDB(
                user_id=payload.user_id,
                role="assistant",
                content=assistant_text,
                message_type="free_chat",
            )
            db.add(assistant_message)
            db.commit()
            db.refresh(assistant_message)

            refresh_user_memory_summary(db=db, user=user)

        except Exception as e:
            yield f"\n[OpenAI error: {str(e)}]"

    return StreamingResponse(
        generate(),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )