from __future__ import annotations

import logging
from datetime import datetime, timezone, date

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
from app.services.conversation_starter import get_opening_message, get_follow_up

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# GET /{user_id}/messages
# ---------------------------------------------------------------------------
@router.get(
    "/{user_id}/messages",
    response_model=List[ConversationMessageRead],
    summary="Get Messages",
)
def get_messages(user_id: int, db: Session = Depends(get_db)):
    return (
        db.query(ConversationMessage)
        .filter(ConversationMessage.user_id == user_id)
        .order_by(ConversationMessage.created_at)
        .all()
    )


# ---------------------------------------------------------------------------
# DELETE /{user_id}/messages
# ---------------------------------------------------------------------------
@router.delete("/{user_id}/messages", status_code=204, summary="Delete User Messages")
def delete_messages(user_id: int, db: Session = Depends(get_db)):
    db.query(ConversationMessage).filter(
        ConversationMessage.user_id == user_id
    ).delete()
    db.commit()


# ---------------------------------------------------------------------------
# GET /{user_id}/risk-analysis
# ---------------------------------------------------------------------------
@router.get(
    "/{user_id}/risk-analysis",
    response_model=List[RiskAnalysisResponse],
    summary="Get User Risk Analysis",
)
def get_user_risk(user_id: int, db: Session = Depends(get_db)):
    return (
        db.query(RiskAnalysis)
        .filter(RiskAnalysis.user_id == user_id)
        .order_by(RiskAnalysis.created_at.desc())
        .all()
    )


# ---------------------------------------------------------------------------
# GET /{user_id}/notifications
# ---------------------------------------------------------------------------
@router.get(
    "/{user_id}/notifications",
    response_model=List[NotificationRead],
    summary="Get User Notifications",
)
def get_user_notifications(user_id: int, db: Session = Depends(get_db)):
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .all()
    )


# ---------------------------------------------------------------------------
# POST /start
# ---------------------------------------------------------------------------
@router.post(
    "/start",
    response_model=ConversationMessageRead,
    status_code=201,
    summary="Start conversation — bot sends opening message",
)
def start_conversation(
    user_id: int,
    language: str = "fi",
    db: Session = Depends(get_db),
):
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    existing_today = (
        db.query(ConversationMessage)
        .filter(
            ConversationMessage.user_id == user_id,
            ConversationMessage.role == "assistant",
            ConversationMessage.created_at >= today_start,
        )
        .first()
    )

    if existing_today:
        return existing_today

    opening_text = get_opening_message(language)

    msg = ConversationMessage(
        user_id=user_id,
        role="assistant",
        content=opening_text,
        message_type="checkin_start",
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


# ---------------------------------------------------------------------------
# POST /message
# ---------------------------------------------------------------------------
@router.post(
    "/message",
    response_model=SendMessageResponse,
    status_code=201,
    summary="Send Message",
)
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
        preferred_language=None,
        elderly=True,
    )

    # 4. Update user message risk fields
    user_msg.risk_level = result["risk_level"]
    user_msg.risk_score = result["score"]
    user_msg.risk_category = result["category"]

    # 5. Save RiskAnalysis
    risk = RiskAnalysis(
        user_id=payload.user_id,
        daily_checkin_id=None,
        conversation_message_id=user_msg.id,
        category=result["category"],
        risk_level=result["risk_level"],
        risk_score=result["score"],
        needs_family_notification=result["should_alert_family"],
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

    # 7. Count total messages today (user + assistant) for daily limit
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    total_messages_today = (
        db.query(ConversationMessage)
        .filter(
            ConversationMessage.user_id == payload.user_id,
            ConversationMessage.created_at >= today_start,
        )
        .count()
    )

    # 8. Daily message limit — 20 messages per day
    if total_messages_today > 20:
        detected_lang = result.get("language", "fi")
        closing_messages = {
            "fi": "Olemme jutelleet paljon tänään. Olen iloinen, että jaoit ajatuksesi kanssani. Jatketaan huomenna. Pidä huolta itsestäsi.",
            "en": "We have talked a lot today. I am glad you shared with me. Let's continue tomorrow. Take care.",
            "sv": "Vi har pratat mycket idag. Jag är glad att du delade med mig. Vi fortsätter imorgon. Ta hand om dig.",
        }
        closing = closing_messages.get(detected_lang, closing_messages["en"])

        assistant_msg = ConversationMessage(
            user_id=payload.user_id,
            role="assistant",
            content=closing,
            message_type="free_chat",
        )
        db.add(assistant_msg)
        db.commit()
        db.refresh(assistant_msg)

        return SendMessageResponse(
            reply=closing,
            risk_analysis=RiskAnalysisResponse.model_validate(risk).model_dump(),
            notifications=notifications_out,
            mode="non_stream",
        )

    # 9. Count user messages today for reply style
    user_messages_today = (
        db.query(ConversationMessage)
        .filter(
            ConversationMessage.user_id == payload.user_id,
            ConversationMessage.role == "user",
            ConversationMessage.created_at >= today_start,
        )
        .count()
    )

    # 10. Generate reply
    ai_reply = _generate_reply(
        message=payload.message,
        language=result["language"],
        follow_up=result["follow_up_question"],
        risk_level=result["risk_level"],
        user_messages_today=user_messages_today,
        db=db,
        user_id=payload.user_id,
    )

    # 11. Save assistant message
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


# ---------------------------------------------------------------------------
# POST /message/stream
# ---------------------------------------------------------------------------
@router.post("/message/stream", summary="Send Message Stream")
def send_message_stream(payload: SendMessageRequest):
    return {"detail": "Streaming not yet implemented"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _generate_reply(
    message: str,
    language: str,
    follow_up: str,
    risk_level: str,
    user_messages_today: int,
    db: Session,
    user_id: int,
) -> str:
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
            "fi": (
                "Olet lämminhenkinen hyvinvointiassistentti iäkkäille ihmisille. "
                "Tehtäväsi on selvittää, miten henkilö voi: uni, ruoka, juominen, kipu ja mieliala. "
                "Kysy yksi asia kerrallaan. Älä listaa kysymyksiä. "
                "Vastaa lyhyesti ja lämpimästi. "
                "Jos henkilö mainitsee kipua tai huolia, kysy tarkentava kysymys. "
                "Jos riski on korkea, ilmaise huolesi rauhallisesti ja suosittele yhteydenottoa läheiseen."
            ),
            "en": (
                "You are a warm welfare assistant for elderly people. "
                "Your job is to understand how the person is doing: sleep, food, hydration, pain, mood. "
                "Ask one thing at a time. Never list questions. "
                "Respond briefly and warmly. "
                "If they mention pain or worry, ask a follow-up. "
                "If risk is high, calmly express concern and suggest contacting a trusted person."
            ),
            "sv": (
                "Du är en varm välfärdsassistent för äldre. "
                "Ditt jobb är att förstå hur personen mår: sömn, mat, dryck, smärta, humör. "
                "Ställ en fråga i taget. Lista aldrig frågor. "
                "Svara kort och varmt. "
                "Om de nämner smärta eller oro, ställ en följdfråga. "
                "Om risken är hög, uttryck lugnt din oro och föreslå kontakt med en närstående."
            ),
        }

        # Override for high/critical risk
        if risk_level in ("high", "critical"):
            high_risk_prompts = {
                "fi": (
                    "Olet hyvinvointiassistentti. Henkilöllä on korkea riskitaso. "
                    "Vastaa lyhyesti, lämpimästi ja suoraan. "
                    "Kysy yksi tarkka kysymys: onko hän turvassa juuri nyt ja onko joku lähellä. "
                    "Suosittele selkeästi ottamaan yhteyttä läheiseen tai hoitajaan tänään. "
                    "Älä jatka normaalia keskustelua — keskity turvallisuuteen."
                ),
                "en": (
                    "You are a welfare assistant. This person has a high risk level. "
                    "Respond briefly, warmly and directly. "
                    "Ask one specific question: are they safe right now and is anyone nearby. "
                    "Clearly recommend they contact a trusted person or care worker today. "
                    "Do not continue normal conversation — focus on their safety."
                ),
                "sv": (
                    "Du är en välfärdsassistent. Denna person har hög risknivå. "
                    "Svara kort, varmt och direkt. "
                    "Ställ en specifik fråga: är de trygga just nu och finns någon i närheten. "
                    "Rekommendera tydligt att de kontaktar en närstående eller vårdare idag. "
                    "Fortsätt inte normalt samtal — fokusera på deras säkerhet."
                ),
            }
            system_prompt = high_risk_prompts.get(language, high_risk_prompts["en"])
        else:
            system_prompt = system_prompts.get(language, system_prompts["en"])

        # Add follow-up instruction if early in conversation
        if user_messages_today <= 2 and follow_up and risk_level not in ("high", "critical"):
            follow_up_instructions = {
                "fi": f" Kun olet vastannut, kysy luonnollisesti: {follow_up}",
                "en": f" After responding, naturally ask: {follow_up}",
                "sv": f" Efter att ha svarat, fråga naturligt: {follow_up}",
            }
            system_prompt += follow_up_instructions.get(language, follow_up_instructions["en"])

        messages = [{"role": "system", "content": system_prompt}]
        for msg in reversed(history):
            messages.append({"role": msg.role, "content": msg.content})

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=200,
            temperature=0.6,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"OpenAI call failed: {type(e).__name__}: {e}")
        if user_messages_today <= 2 and follow_up:
            fallback = {
                "fi": f"Kiitos vastauksestasi. {follow_up}",
                "sv": f"Tack för ditt svar. {follow_up}",
                "en": f"Thank you for sharing. {follow_up}",
            }
        else:
            fallback = {
                "fi": "Kiitos. Pidän sinut mielessäni.",
                "sv": "Tack. Jag tänker på dig.",
                "en": "Thank you. I'm keeping you in mind.",
            }
        return fallback.get(language, fallback["en"])