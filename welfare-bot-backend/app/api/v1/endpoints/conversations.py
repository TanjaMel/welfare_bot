from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
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
from app.services.conversation_starter import get_opening_message
from app.services.memory_service import (
    get_memory_context,
    summarize_session,
)

logger = logging.getLogger(__name__)
router = APIRouter()


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


@router.delete("/{user_id}/messages", status_code=204, summary="Delete User Messages")
def delete_messages(user_id: int, db: Session = Depends(get_db)):
    db.query(ConversationMessage).filter(
        ConversationMessage.user_id == user_id
    ).delete()
    db.commit()


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
        model_version="llm+rules_v2",
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

    # 7. Count today's messages
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

    # 8. Daily limit
    if total_messages_today > 20:
        detected_lang = result.get("language", "fi")
        closing_messages = {
            "fi": "Olemme jutelleet paljon tänään. Olen iloinen, että jaoit ajatuksesi kanssani. Jatketaan huomenna. Pidä huolta itsestäsi.",
            "en": "We have talked a lot today. I am glad you shared with me. Let us continue tomorrow. Take care.",
            "sv": "Vi har pratat mycket idag. Jag ar glad att du delade med mig. Vi fortsatter imorgon. Ta hand om dig.",
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

        _trigger_session_summary(
            user_id=payload.user_id,
            db=db,
            today_start=today_start,
        )

        return SendMessageResponse(
            reply=closing,
            risk_analysis=RiskAnalysisResponse.model_validate(risk).model_dump(),
            notifications=notifications_out,
            mode="non_stream",
        )

    # 9. Count user messages today
    user_messages_today = (
        db.query(ConversationMessage)
        .filter(
            ConversationMessage.user_id == payload.user_id,
            ConversationMessage.role == "user",
            ConversationMessage.created_at >= today_start,
        )
        .count()
    )

    # 10. Generate AI reply
    ai_reply = _generate_reply(
        message=payload.message,
        language=result["language"],
        follow_up=result["follow_up_question"],
        risk_level=result["risk_level"],
        user_messages_today=user_messages_today,
        db=db,
        user_id=payload.user_id,
        today_start=today_start,
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


@router.post("/message/stream", summary="Send Message Stream")
def send_message_stream(payload: SendMessageRequest):
    return {"detail": "Streaming not yet implemented"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_todays_topics(
    user_id: int,
    db: Session,
    today_start: datetime,
) -> list[str]:
    """
    Scan today's user messages for topics already discussed.
    Used to prevent the bot from asking the same question twice.
    """
    today_user_msgs = (
        db.query(ConversationMessage)
        .filter(
            ConversationMessage.user_id == user_id,
            ConversationMessage.role == "user",
            ConversationMessage.created_at >= today_start,
        )
        .all()
    )

    combined = " ".join(m.content.lower() for m in today_user_msgs)

    keywords = {
        "sleep":      ["uni", "nukku", "yö", "sleep", "slept", "sov", "natt"],
        "food":       ["syö", "ruoka", "lounas", "aamupala", "ate", "eat", "food", "lunch", "mat", "aten"],
        "hydration":  ["juo", "vesi", "nestey", "drink", "water", "drick", "vatten"],
        "pain":       ["kipu", "sarky", "sattuu", "pain", "ache", "hurt", "smarta", "ont"],
        "mood":       ["mieli", "tunne", "vointi", "mood", "feel", "humör", "mar"],
        "medication": ["laake", "tabletti", "medicine", "pill", "medicin", "tablet"],
    }

    covered = []
    for topic, words in keywords.items():
        if any(w in combined for w in words):
            covered.append(topic)

    return covered


def _trigger_session_summary(
    user_id: int,
    db: Session,
    today_start: datetime,
) -> None:
    try:
        from app.db.models.user import User

        today_msgs = (
            db.query(ConversationMessage)
            .filter(
                ConversationMessage.user_id == user_id,
                ConversationMessage.created_at >= today_start,
            )
            .order_by(ConversationMessage.created_at)
            .all()
        )

        messages = [{"role": m.role, "content": m.content} for m in today_msgs]
        user = db.query(User).filter(User.id == user_id).first()
        previous_summary = user.memory_summary if user else None

        summarize_session(
            user_id=user_id,
            messages=messages,
            db=db,
            previous_summary=previous_summary,
        )
    except Exception as e:
        logger.warning("Session summary trigger failed for user %d: %s", user_id, e)


def _generate_reply(
    message: str,
    language: str,
    follow_up: str,
    risk_level: str,
    user_messages_today: int,
    db: Session,
    user_id: int,
    today_start: datetime,
) -> str:
    try:
        from app.integrations.openai_client import client
        from app.db.models.user import User

        # Get user's first name for personalisation
        user = db.query(User).filter(User.id == user_id).first()
        first_name = user.first_name if user and user.first_name else ""

        # Topics already discussed today — prevents repetition
        covered_topics = _get_todays_topics(user_id, db, today_start)
        covered_str = ", ".join(covered_topics) if covered_topics else "none yet"

        # Name instruction — use name occasionally, not every message
        name_instruction = ""
        if first_name:
            name_instruction = (
                f"\nThe user's name is {first_name}. "
                "Use their name occasionally to make the conversation personal, but not in every message.\n"
            )

        base_rules = {
            "fi": (
                f"Olet rauhallinen ja lämmin hyvinvointiassistentti iäkkäälle ihmiselle.{name_instruction}"
                f"Tänään on jo käsitelty: {covered_str}. Älä toista näitä aiheita ellei käyttäjä itse ota niitä uudelleen esiin.\n\n"
                "Tärkeät säännöt:\n"
                "- Vastaa lyhyesti, selkeästi ja ystävällisesti.\n"
                "- Kysy vain YKSI kysymys kerrallaan.\n"
                "- Älä koskaan listaa monta kysymystä samassa vastauksessa.\n"
                "- Jos käyttäjä vastaa lyhyesti, jatka lempeästi yhdellä uudella aiheella.\n"
                "- Älä ylikuormita käyttäjää.\n"
                "- Älä esitä diagnooseja.\n"
                "- Jos huomaat huolestuttavan oireen, keskity turvallisuuteen ja yhteen tarkentavaan kysymykseen.\n\n"
                "Tavoite on ymmärtää vähitellen: uni, ruoka, juominen, kipu, mieliala ja turvallisuus."
            ),
            "en": (
                f"You are a calm, warm wellbeing assistant for an elderly person.{name_instruction}"
                f"Already discussed today: {covered_str}. Do not repeat these topics unless the user brings them up again.\n\n"
                "Important rules:\n"
                "- Reply briefly, clearly and kindly.\n"
                "- Ask only ONE question at a time.\n"
                "- Never list multiple questions in one reply.\n"
                "- If the user gives a short answer, gently continue with one new topic.\n"
                "- Do not overwhelm the user.\n"
                "- Do not provide medical diagnosis.\n"
                "- If there is a concerning symptom, focus on safety and ask one specific follow-up question.\n\n"
                "The goal is to gradually understand: sleep, food, hydration, pain, mood and safety."
            ),
            "sv": (
                f"Du ar en lugn och varm valfärdsassistent for en aldre person.{name_instruction}"
                f"Redan diskuterat idag: {covered_str}. Upprepa inte dessa amnen om inte anvandaren tar upp dem igen.\n\n"
                "Viktiga regler:\n"
                "- Svara kort, tydligt och vanligt.\n"
                "- Stall bara EN fraga at gangen.\n"
                "- Lista aldrig flera fragor i samma svar.\n"
                "- Om anvandaren svarar kort, fortsatt mjukt med ett nytt amne.\n"
                "- Overbelasta inte anvandaren.\n"
                "- Ge inte medicinska diagnoser.\n"
                "- Om det finns ett oroande symtom, fokusera pa sakerhet och stall en specifik foljdfraga.\n\n"
                "Malet ar att gradvis forstå: somn, mat, vatska, smarta, humor och sakerhet."
            ),
        }

        high_risk_rules = {
            "fi": (
                f"Olet hyvinvointiassistentti. Käyttäjän viestissä on korkea tai kriittinen riskitaso.{name_instruction}\n"
                "Toimi näin:\n"
                "- Vastaa lyhyesti, lämpimästi ja suoraan.\n"
                "- Keskity turvallisuuteen, älä jatka normaalia jutustelua.\n"
                "- Kysy vain yksi kysymys: onko käyttäjä turvassa juuri nyt ja onko joku lähellä.\n"
                "- Suosittele ottamaan yhteyttä läheiseen, hoitajaan tai hätäpalveluun tilanteen vakavuuden mukaan.\n"
                "- Älä tee diagnoosia.\n"
                "- Älä käytä pelottelevaa kieltä."
            ),
            "en": (
                f"You are a wellbeing assistant. The user message has a high or critical risk level.{name_instruction}\n"
                "Do this:\n"
                "- Reply briefly, warmly and directly.\n"
                "- Focus on safety, not normal conversation.\n"
                "- Ask only one question: are they safe right now and is someone nearby.\n"
                "- Recommend contacting a trusted person, care worker or emergency services depending on severity.\n"
                "- Do not diagnose.\n"
                "- Do not use frightening language."
            ),
            "sv": (
                f"Du ar en valfärdsassistent. Användarens meddelande har hog eller kritisk riskniva.{name_instruction}\n"
                "Gor sa har:\n"
                "- Svara kort, varmt och direkt.\n"
                "- Fokusera pa sakerhet, inte vanligt samtal.\n"
                "- Stall bara en fraga: ar anvandaren trygg just nu och finns nagon i narheten.\n"
                "- Rekommendera kontakt med en narstående, vardare eller larmtjanst beroende pa allvarlighetsgrad.\n"
                "- Ge ingen diagnos.\n"
                "- Anvand inte skrammande sprak."
            ),
        }

        if risk_level in ("high", "critical"):
            system_prompt = high_risk_rules.get(language, high_risk_rules["en"])
        else:
            system_prompt = base_rules.get(language, base_rules["en"])

        # Inject memory from previous sessions
        memory_context = get_memory_context(user_id=user_id, db=db, language=language)
        if memory_context:
            system_prompt = memory_context + "\n\n" + system_prompt

        # Follow-up hint only early in conversation and for new topics
        if (
            user_messages_today <= 2
            and follow_up
            and risk_level not in ("high", "critical")
        ):
            follow_up_instructions = {
                "fi": f"\n\nJos tämä aihe ei ole jo tullut esiin tänään, voit kysyä: {follow_up}",
                "en": f"\n\nIf this topic has not already been covered today, you may ask: {follow_up}",
                "sv": f"\n\nOm detta amne inte redan tagits upp idag kan du fraga: {follow_up}",
            }
            system_prompt += follow_up_instructions.get(language, follow_up_instructions["en"])

        # Build message list from today's history in chronological order.
        # The current message is already saved to DB and included in history —
        # do NOT append it again to avoid sending it twice to the model.
        history = (
            db.query(ConversationMessage)
            .filter(
                ConversationMessage.user_id == user_id,
                ConversationMessage.created_at >= today_start,
            )
            .order_by(ConversationMessage.created_at)
            .limit(20)
            .all()
        )

        chat_messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            chat_messages.append({"role": msg.role, "content": msg.content})

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=chat_messages,
            max_tokens=180,
            temperature=0.4,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error("OpenAI call failed: %s: %s", type(e).__name__, e)

        if user_messages_today <= 2 and follow_up:
            fallback = {
                "fi": f"Kiitos vastauksestasi. {follow_up}",
                "sv": f"Tack for ditt svar. {follow_up}",
                "en": f"Thank you for sharing. {follow_up}",
            }
        else:
            fallback = {
                "fi": "Kiitos, etta kerroit. Olen tassa kanssasi.",
                "sv": "Tack for att du berattade. Jag ar har med dig.",
                "en": "Thank you for sharing. I am here with you.",
            }

        return fallback.get(language, fallback["en"])