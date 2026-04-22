from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.db.models.conversation_message import ConversationMessage
from app.db.models.risk_analysis import RiskAnalysis
from app.db.models.notification import Notification
from app.schemas.conversation import (
    ConversationMessageRead,
    SendMessageRequest,
    SendMessageResponse,
)
from app.schemas.risk_analysis import RiskAnalysisResponse
from app.schemas.notification import NotificationRead
from app.services import risk_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{user_id}/messages", response_model=List[ConversationMessageRead], summary="Get Messages")
def get_messages(user_id: int, db: Session = Depends(get_db)):
    return (
        db.query(ConversationMessage)
        .filter(ConversationMessage.user_id == user_id)
        .order_by(ConversationMessage.created_at)
        .all()
    )


@router.delete("/{user_id}/messages", status_code=204, summary="Delete User Messages")
def delete_messages(user_id: int, db: Session = Depends(get_db)):
    db.query(ConversationMessage).filter(ConversationMessage.user_id == user_id).delete()
    db.commit()


@router.get("/{user_id}/risk-analysis", response_model=List[RiskAnalysisResponse], summary="Get User Risk Analysis")
def get_user_risk(user_id: int, db: Session = Depends(get_db)):
    return (
        db.query(RiskAnalysis)
        .filter(RiskAnalysis.user_id == user_id)
        .order_by(RiskAnalysis.created_at.desc())
        .all()
    )


@router.get("/{user_id}/notifications", response_model=List[NotificationRead], summary="Get User Notifications")
def get_user_notifications(user_id: int, db: Session = Depends(get_db)):
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .all()
    )


@router.post("/message", response_model=SendMessageResponse, status_code=201, summary="Send Message")
def send_message(payload: SendMessageRequest, db: Session = Depends(get_db)):
    # 1. Save user message
    user_msg = ConversationMessage(
        user_id=payload.user_id,
        role="user",
        content=payload.message,
        message_type="free_chat",
    )
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    # 2. Recent messages for risk context
    recent_msgs = (
        db.query(ConversationMessage)
        .filter(
            ConversationMessage.user_id == payload.user_id,
            ConversationMessage.role == "user",
            ConversationMessage.id != user_msg.id,
        )
        .order_by(ConversationMessage.created_at.desc())
        .limit(5)
        .all()
    )
    recent_texts = [m.content for m in reversed(recent_msgs)]

    # 3. Risk assessment
    result = risk_service.assess(
        current_message=payload.message,
        recent_user_messages=recent_texts,
        preferred_language=payload.language,
        elderly=True,
    )

    # 4. Update user message risk fields
    user_msg.risk_level = result["risk_level"]
    user_msg.risk_score = result["score"]
    user_msg.risk_category = result["category"]

    # 5. Save RiskAnalysis — using REAL DB column name: needs_family_notification
    risk = RiskAnalysis(
        user_id=payload.user_id,
        daily_checkin_id=None,
        conversation_message_id=user_msg.id,
        category=result["category"],
        risk_level=result["risk_level"],
        risk_score=result["score"],
        needs_family_notification=result["should_alert_family"],  # ← real DB column
        reason="; ".join(result["reasons"]) if result["reasons"] else None,
        suggested_action=result["suggested_action"],
        follow_up_question=result["follow_up_question"],
        signals_json=result["signals"],
        reasons_json=result["reasons"],
        model_version="rule_engine_v1",
    )
    db.add(risk)
    db.commit()
    db.refresh(risk)
    db.refresh(user_msg)

    # 6. Notification if needed
    notifications_out: list[dict] = []
    if result["should_alert_family"]:
        notif = Notification(
            user_id=payload.user_id,
            risk_analysis_id=risk.id,
            channel="sms",
            message=(
                f"Risk level '{result['risk_level']}' detected in chat. "
                f"{result['suggested_action']}"
            ),
            status="pending",
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)
        notifications_out.append(NotificationRead.model_validate(notif).model_dump())

    # 7. Generate AI reply
    ai_reply = _generate_reply(
        message=payload.message,
        language=result["language"],
        follow_up=result["follow_up_question"],
        db=db,
        user_id=payload.user_id,
    )

    # 8. Save assistant message
    assistant_msg = ConversationMessage(
        user_id=payload.user_id,
        role="assistant",
        content=ai_reply,
        message_type="free_chat",
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    return SendMessageResponse(
        reply=ai_reply,
        risk_analysis=RiskAnalysisResponse.model_validate(risk).model_dump(),
        notifications=notifications_out,
        mode="non_stream",
    )


@router.post("/message/stream", summary="Send Message Stream")
def send_message_stream(payload: SendMessageRequest):
    return {"detail": "Streaming not yet implemented"}


def _generate_reply(message: str, language: str, follow_up: str, db: Session, user_id: int) -> str:
    try:
        from app.integrations.openai_client import client

        history = (
            db.query(ConversationMessage)
            .filter(ConversationMessage.user_id == user_id)
            .order_by(ConversationMessage.created_at.desc())
            .limit(10)
            .all()
        )

        system_prompts = {
            "fi": "Olet ystävällinen hyvinvointiassistentti iäkkäille. Vastaa lyhyesti ja lämpimästi suomeksi.",
            "sv": "Du är en vänlig välfärdsassistent för äldre. Svara kort och varmt på svenska.",
            "en": "You are a friendly welfare assistant for elderly people. Respond briefly and warmly.",
        }
        system_prompt = system_prompts.get(language, system_prompts["en"])
        if follow_up:
            system_prompt += f" End your reply with this follow-up question: {follow_up}"

        messages = [{"role": "system", "content": system_prompt}]
        for msg in reversed(history):
            messages.append({"role": msg.role, "content": msg.content})

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=300,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"OpenAI call failed: {type(e).__name__}: {e}")
        fallback = {
            "fi": f"Kiitos viestistäsi. {follow_up}",
            "sv": f"Tack för ditt meddelande. {follow_up}",
            "en": f"Thank you for your message. {follow_up}",
        }
        return fallback.get(language, fallback["en"])