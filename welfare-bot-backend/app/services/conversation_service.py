from __future__ import annotations

from typing import Any

from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.conversation_message import ConversationMessage
from app.db.models.notification import Notification
from app.db.models.risk_analysis import RiskAnalysis
from app.db.models.user import User
from app.services.memory_service import refresh_user_memory_summary
from app.services.notification_service import create_notification_for_risk
from app.services.risk_analysis_service import analyze_chat_message
from app.services.token_service import trim_input_items_to_token_budget
from app.services.validation_service import validate_user_message


settings = get_settings()
client = OpenAI(api_key=settings.openai_api_key)


SUPPORTED_LANGUAGES = {"en", "fi", "sv"}


def resolve_language(user: User, payload_language: str | None, text: str) -> str:
    if payload_language and payload_language in SUPPORTED_LANGUAGES:
        return payload_language

    if user.language and user.language in SUPPORTED_LANGUAGES:
        return user.language

    text_lower = f" {text.lower()} "

    if any(word in text_lower for word in [" minä ", " olen ", " huimaa ", " yksinäinen ", " rintakipu "]):
        return "fi"
    if any(word in text_lower for word in [" jag ", " trött ", " ensam ", " bröstsmärta "]):
        return "sv"

    return "en"


def language_label(code: str) -> str:
    if code == "fi":
        return "Finnish"
    if code == "sv":
        return "Swedish"
    return "English"


def get_recent_user_messages(db: Session, user_id: int, limit: int = 5) -> list[str]:
    messages = (
        db.query(ConversationMessage)
        .filter(
            ConversationMessage.user_id == user_id,
            ConversationMessage.role == "user",
        )
        .order_by(ConversationMessage.created_at.desc())
        .limit(limit)
        .all()
    )

    return list(reversed([m.content for m in messages]))


def build_input_items(
    *,
    db: Session,
    user: User,
    language: str,
    risk_analysis: dict[str, Any],
) -> list[dict[str, str]]:
    messages = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.user_id == user.id)
        .order_by(ConversationMessage.created_at.asc())
        .all()
    )

    target_language = language_label(language)

    developer_prompt = f"""
You are a supportive welfare assistant for older adults.

LANGUAGE RULES:
- You MUST reply ONLY in {target_language}.
- Never mix languages.
- Never add translations.
- Never switch language mid-response.

ROLE:
- Calm, human, warm, practical.
- Short and clear.
- Do not diagnose.

RISK CONTEXT:
- risk_level: {risk_analysis["risk_level"]}
- category: {risk_analysis["category"]}
- signals: {", ".join(risk_analysis["signals_json"]) if risk_analysis["signals_json"] else "none"}
- follow_up_question: {risk_analysis["follow_up_question"]}
- suggested_action: {risk_analysis["suggested_action"]}
- should_alert_family: {risk_analysis["should_alert_family"]}

RULES:
- LOW: supportive and simple
- MEDIUM: mention wellbeing impact and ask one follow-up question
- HIGH: stronger concern and one safety-oriented follow-up
- CRITICAL: recommend urgent help now

OUTPUT:
- plain text only
- no bullet points
- no headings
- no translations
""".strip()

    items: list[dict[str, str]] = [
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
        if msg.role in {"user", "assistant"}:
            items.append(
                {
                    "role": msg.role,
                    "content": msg.content,
                }
            )

    return trim_input_items_to_token_budget(
        items=items,
        model_name=settings.openai_model,
        max_input_tokens=6000,
    )


def should_stream_reply(risk_level: str) -> bool:
    return risk_level in {"low", "medium"}


def generate_non_stream_reply(
    *,
    db: Session,
    user: User,
    language: str,
    risk_analysis: dict[str, Any],
) -> str:
    response = client.responses.create(
        model=settings.openai_model,
        input=build_input_items(
            db=db,
            user=user,
            language=language,
            risk_analysis=risk_analysis,
        ),
    )

    return response.output_text or "Sorry, I could not generate a reply."


def save_user_message(
    *,
    db: Session,
    user_id: int,
    text: str,
) -> ConversationMessage:
    message = ConversationMessage(
        user_id=user_id,
        role="user",
        content=text,
        message_type="free_chat",
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def save_assistant_message(
    *,
    db: Session,
    user_id: int,
    text: str,
) -> ConversationMessage:
    message = ConversationMessage(
        user_id=user_id,
        role="assistant",
        content=text,
        message_type="free_chat",
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def save_risk_analysis_for_message(
    *,
    db: Session,
    user_id: int,
    conversation_message_id: int,
    risk_result: dict[str, Any],
) -> RiskAnalysis:
    risk_analysis = RiskAnalysis(
        user_id=user_id,
        conversation_message_id=conversation_message_id,
        category=risk_result["category"],
        risk_level=risk_result["risk_level"],
        risk_score=risk_result["risk_score"],
        reason=risk_result["reason"],
        suggested_action=risk_result["suggested_action"],
        follow_up_question=risk_result["follow_up_question"],
        signals_json=risk_result["signals_json"],
        reasons_json=risk_result["reasons_json"],
        should_alert_family=risk_result["should_alert_family"],
        model_version=risk_result["model_version"],
    )
    db.add(risk_analysis)
    db.commit()
    db.refresh(risk_analysis)
    return risk_analysis


def update_message_risk_fields(
    *,
    db: Session,
    message: ConversationMessage,
    risk_analysis: RiskAnalysis,
) -> None:
    message.risk_level = risk_analysis.risk_level
    message.risk_score = risk_analysis.risk_score
    message.risk_category = risk_analysis.category
    db.add(message)
    db.commit()
    db.refresh(message)


def maybe_create_notifications(
    *,
    db: Session,
    risk_analysis: RiskAnalysis,
) -> list[Notification]:
    notifications: list[Notification] = []

    if risk_analysis.should_alert_family or risk_analysis.risk_level in {"high", "critical"}:
        notifications.append(
            create_notification_for_risk(
                db,
                risk_analysis=risk_analysis,
            )
        )

    return notifications


def handle_message(
    *,
    db: Session,
    user: User,
    raw_text: str,
    payload_language: str | None = None,
) -> dict[str, Any]:
    recent_user_messages = get_recent_user_messages(db, user.id)

    validation = validate_user_message(
        text=raw_text,
        recent_user_messages=recent_user_messages,
    )

    if not validation.is_valid:
        raise ValueError(validation.error or "Invalid message")

    cleaned_text = validation.cleaned_text
    language = resolve_language(user, payload_language, cleaned_text)

    user_message = save_user_message(
        db=db,
        user_id=user.id,
        text=cleaned_text,
    )

    risk_result = analyze_chat_message(
        user_id=user.id,
        message=cleaned_text,
        language=language,
    )

    risk_analysis = save_risk_analysis_for_message(
        db=db,
        user_id=user.id,
        conversation_message_id=user_message.id,
        risk_result=risk_result,
    )

    update_message_risk_fields(
        db=db,
        message=user_message,
        risk_analysis=risk_analysis,
    )

    notifications = maybe_create_notifications(
        db=db,
        risk_analysis=risk_analysis,
    )

    reply = generate_non_stream_reply(
        db=db,
        user=user,
        language=language,
        risk_analysis=risk_result,
    )

    assistant_message = save_assistant_message(
        db=db,
        user_id=user.id,
        text=reply,
    )

    refresh_user_memory_summary(db=db, user=user)

    return {
        "reply": assistant_message.content,
        "risk_analysis": {
            "id": risk_analysis.id,
            "user_id": risk_analysis.user_id,
            "category": risk_analysis.category,
            "risk_level": risk_analysis.risk_level,
            "risk_score": risk_analysis.risk_score,
            "reason": risk_analysis.reason,
            "suggested_action": risk_analysis.suggested_action,
            "follow_up_question": risk_analysis.follow_up_question,
            "should_alert_family": risk_analysis.should_alert_family,
            "signals_json": risk_analysis.signals_json,
            "reasons_json": risk_analysis.reasons_json,
            "model_version": risk_analysis.model_version,
        },
        "notifications": [
            {
                "id": n.id,
                "channel": n.channel,
                "message": n.message,
                "status": n.status,
            }
            for n in notifications
        ],
        "mode": "non_stream",
    }