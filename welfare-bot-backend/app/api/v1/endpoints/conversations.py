from datetime import datetime
from typing import Iterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.db.models.care_contact import CareContact
from app.db.models.conversation_message import ConversationMessage as ConversationMessageDB
from app.db.models.notification import Notification
from app.db.models.risk_analysis import RiskAnalysis
from app.db.models.user import User
from app.services.risk_analysis_service import (
    analyze_chat_message,
    build_notification_message,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])

settings = get_settings()
client = OpenAI(api_key=settings.openai_api_key)


class ConversationMessageRead(BaseModel):
    id: int
    role: str
    content: str
    created_at: str | None = None


class SendMessageRequest(BaseModel):
    user_id: int
    message: str


class SendMessageResponse(BaseModel):
    reply: str
    risk_analysis: dict | None = None
    notifications: list[dict] = []


def to_message_read(message: ConversationMessageDB) -> ConversationMessageRead:
    return ConversationMessageRead(
        id=message.id,
        role=message.role,
        content=message.content,
        created_at=message.created_at.isoformat() if message.created_at else None,
    )


def build_input_items(db: Session, user_id: int) -> list[dict]:
    messages = (
        db.query(ConversationMessageDB)
        .filter(ConversationMessageDB.user_id == user_id)
        .order_by(ConversationMessageDB.id.asc())
        .all()
    )

    items: list[dict] = [
        {
            "role": "developer",
            "content": (
                "You are a supportive welfare assistant for older people. "
                "Reply clearly, warmly, and briefly. "
                "Use simple language and a calm tone."
            ),
        }
    ]

    for msg in messages:
        if msg.role in ("user", "assistant"):
            items.append(
                {
                    "role": msg.role,
                    "content": msg.content,
                }
            )

    return items


def save_auto_risk_and_notifications(
    db: Session,
    user: User,
    message: ConversationMessageDB,
) -> tuple[RiskAnalysis, list[Notification]]:
    analysis_data = analyze_chat_message(message.content)

    risk_analysis = RiskAnalysis(
        user_id=user.id,
        conversation_message_id=message.id,
        daily_checkin_id=None,
        category=analysis_data["category"],
        risk_level=analysis_data["risk_level"],
        needs_family_notification=analysis_data["needs_family_notification"],
        reason=analysis_data["reason"],
        suggested_action=analysis_data["suggested_action"],
        model_version=analysis_data["model_version"],
    )
    db.add(risk_analysis)
    db.commit()
    db.refresh(risk_analysis)

    created_notifications: list[Notification] = []

    if risk_analysis.needs_family_notification:
        contacts = (
            db.query(CareContact)
            .filter(CareContact.user_id == user.id, CareContact.is_primary.is_(True))
            .all()
        )

        if not contacts:
            contacts = db.query(CareContact).filter(CareContact.user_id == user.id).all()

        for contact in contacts:
            notification = Notification(
                user_id=user.id,
                care_contact_id=contact.id,
                risk_analysis_id=risk_analysis.id,
                channel=contact.preferred_notification_method,
                message=build_notification_message(
                    first_name=user.first_name,
                    last_name=user.last_name,
                    category=risk_analysis.category,
                    risk_level=risk_analysis.risk_level,
                    reason=risk_analysis.reason,
                ),
                status="pending",
            )
            db.add(notification)
            created_notifications.append(notification)

        db.commit()

        for notification in created_notifications:
            db.refresh(notification)

    return risk_analysis, created_notifications


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

    analyses = (
        db.query(RiskAnalysis)
        .filter(RiskAnalysis.user_id == user_id, RiskAnalysis.conversation_message_id.is_not(None))
        .order_by(RiskAnalysis.id.desc())
        .all()
    )

    return [
        {
            "id": a.id,
            "user_id": a.user_id,
            "conversation_message_id": a.conversation_message_id,
            "category": a.category,
            "risk_level": a.risk_level,
            "needs_family_notification": a.needs_family_notification,
            "reason": a.reason,
            "suggested_action": a.suggested_action,
            "model_version": a.model_version,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in analyses
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
    user_text = payload.message.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_message = ConversationMessageDB(
        user_id=payload.user_id,
        role="user",
        content=user_text,
        message_type="free_chat",
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    risk_analysis, notifications = save_auto_risk_and_notifications(
        db=db,
        user=user,
        message=user_message,
    )

    try:
        response = client.responses.create(
            model=settings.openai_model,
            input=build_input_items(db, payload.user_id),
        )
        assistant_text = response.output_text or "Sorry, I could not generate a reply."
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

    return SendMessageResponse(
        reply=assistant_text,
        risk_analysis={
            "id": risk_analysis.id,
            "user_id": risk_analysis.user_id,
            "conversation_message_id": risk_analysis.conversation_message_id,
            "category": risk_analysis.category,
            "risk_level": risk_analysis.risk_level,
            "needs_family_notification": risk_analysis.needs_family_notification,
            "reason": risk_analysis.reason,
            "suggested_action": risk_analysis.suggested_action,
            "model_version": risk_analysis.model_version,
            "created_at": risk_analysis.created_at.isoformat() if risk_analysis.created_at else None,
        },
        notifications=[
            {
                "id": n.id,
                "care_contact_id": n.care_contact_id,
                "risk_analysis_id": n.risk_analysis_id,
                "channel": n.channel,
                "message": n.message,
                "status": n.status,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in notifications
        ],
    )


@router.post("/message/stream")
def send_message_stream(
    payload: SendMessageRequest,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    user_text = payload.message.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_message = ConversationMessageDB(
        user_id=payload.user_id,
        role="user",
        content=user_text,
        message_type="free_chat",
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    save_auto_risk_and_notifications(
        db=db,
        user=user,
        message=user_message,
    )

    input_items = build_input_items(db, payload.user_id)

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

            assistant_message = ConversationMessageDB(
                user_id=payload.user_id,
                role="assistant",
                content=assistant_text,
                message_type="free_chat",
            )
            db.add(assistant_message)
            db.commit()

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