from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.db.models.conversation_message import ConversationMessage
from app.db.models.daily_checkin import DailyCheckIn
from app.db.models.notification import Notification
from app.db.models.risk_analysis import RiskAnalysis
from app.db.models.user import User
from app.db.session import SessionLocal


def risk_score_for_level(level: str) -> int:
    mapping = {
        "low": 1,
        "medium": 4,
        "high": 7,
        "critical": 10,
    }
    return mapping[level]


def create_or_get_user(
    db: Session,
    *,
    first_name: str,
    last_name: str,
    phone_number: str,
    language: str,
) -> User:
    existing = db.query(User).filter(User.phone_number == phone_number).first()
    if existing:
        return existing

    user = User(
        first_name=first_name,
        last_name=last_name,
        phone_number=phone_number,
        language=language,
        timezone="Europe/Helsinki",
        notes="Demo user for analytics and dashboard testing",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def add_conversation(
    db: Session,
    *,
    user_id: int,
    role: str,
    content: str,
    created_at: datetime,
    risk_level: str | None = None,
    risk_score: int | None = None,
    risk_category: str | None = None,
) -> ConversationMessage:
    message = ConversationMessage(
        user_id=user_id,
        role=role,
        content=content,
        message_type="free_chat",
        created_at=created_at,
        risk_level=risk_level,
        risk_score=risk_score,
        risk_category=risk_category,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def add_risk_analysis(
    db: Session,
    *,
    user_id: int,
    category: str,
    risk_level: str,
    created_at: datetime,
    daily_checkin_id: int | None = None,
    conversation_message_id: int | None = None,
    reason: str | None = None,
    suggested_action: str | None = None,
    follow_up_question: str | None = None,
    signals_json: list[str] | None = None,
    reasons_json: list[str] | None = None,
    should_alert_family: bool = False,
) -> RiskAnalysis:
    risk = RiskAnalysis(
        user_id=user_id,
        daily_checkin_id=daily_checkin_id,
        conversation_message_id=conversation_message_id,
        category=category,
        risk_level=risk_level,
        risk_score=risk_score_for_level(risk_level),
        reason=reason,
        suggested_action=suggested_action,
        follow_up_question=follow_up_question,
        signals_json=signals_json or [],
        reasons_json=reasons_json or [],
        should_alert_family=should_alert_family,
        model_version="rule_engine_v1",
        created_at=created_at,
    )
    db.add(risk)
    db.commit()
    db.refresh(risk)
    return risk


def add_notification(
    db: Session,
    *,
    user_id: int,
    risk_analysis_id: int,
    message: str,
    created_at: datetime,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        care_contact_id=None,
        risk_analysis_id=risk_analysis_id,
        channel="sms",
        message=message,
        status="pending",
        created_at=created_at,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def add_checkin(
    db: Session,
    *,
    user_id: int,
    checkin_date: date,
    sleep_quality: str | None,
    food_intake: str | None,
    hydration: str | None,
    mood: str | None,
    notes: str | None,
    created_at: datetime,
) -> DailyCheckIn:
    checkin = DailyCheckIn(
        user_id=user_id,
        checkin_date=checkin_date,
        sleep_quality=sleep_quality,
        food_intake=food_intake,
        hydration=hydration,
        mood=mood,
        notes=notes,
        created_at=created_at,
    )
    db.add(checkin)
    db.commit()
    db.refresh(checkin)
    return checkin


def seed_user_dataset(db: Session, user: User, language: str) -> None:
    start = datetime.utcnow() - timedelta(days=13)

    if db.query(ConversationMessage).filter(ConversationMessage.user_id == user.id).first():
        return

    if language == "fi":
        entries = [
            ("Nukuin huonosti viime yönä.", "fatigue", "medium"),
            ("Olen tänään väsynyt ja vähän yksinäinen.", "emotional", "high"),
            ("En ole juonut tarpeeksi vettä.", "nutrition_hydration", "medium"),
            ("Rintaan sattuu vähän.", "safety", "critical"),
        ]
    elif language == "sv":
        entries = [
            ("Jag sov dåligt i natt.", "fatigue", "medium"),
            ("Jag känner mig ensam idag.", "emotional", "high"),
            ("Jag drack för lite vatten.", "nutrition_hydration", "medium"),
            ("Jag mår lite bättre idag.", "general", "low"),
        ]
    else:
        entries = [
            ("I did not sleep well last night.", "fatigue", "medium"),
            ("I feel lonely today.", "emotional", "high"),
            ("I forgot to drink enough water.", "nutrition_hydration", "medium"),
            ("I feel calmer today.", "general", "low"),
        ]

    for i in range(10):
        created_at = start + timedelta(days=i, hours=8 if i % 2 == 0 else 18)

        text, category, risk_level = entries[i % len(entries)]

        user_message = add_conversation(
            db,
            user_id=user.id,
            role="user",
            content=text,
            created_at=created_at,
            risk_level=risk_level,
            risk_score=risk_score_for_level(risk_level),
            risk_category=category,
        )

        risk = add_risk_analysis(
            db,
            user_id=user.id,
            category=category,
            risk_level=risk_level,
            created_at=created_at,
            conversation_message_id=user_message.id,
            reason=f"Detected {category} pattern in chat message",
            suggested_action="Follow up and monitor wellbeing",
            follow_up_question="How are you feeling now?",
            signals_json=[category],
            reasons_json=[f"Pattern matched: {category}"],
            should_alert_family=risk_level in {"high", "critical"},
        )

        if risk_level in {"high", "critical"}:
            add_notification(
                db,
                user_id=user.id,
                risk_analysis_id=risk.id,
                message=f"User {user.id} has {risk_level} risk in category {category}.",
                created_at=created_at + timedelta(minutes=1),
            )

        add_conversation(
            db,
            user_id=user.id,
            role="assistant",
            content="Thank you for sharing. I am here to support you.",
            created_at=created_at + timedelta(minutes=2),
        )

        checkin_date = (created_at.date() - timedelta(days=0))
        checkin = add_checkin(
            db,
            user_id=user.id,
            checkin_date=checkin_date,
            sleep_quality="poor" if category == "fatigue" else "ok",
            food_intake="low" if category == "nutrition_hydration" else "ok",
            hydration="low" if category == "nutrition_hydration" else "ok",
            mood="low" if category == "emotional" else "stable",
            notes=text,
            created_at=created_at,
        )

        add_risk_analysis(
            db,
            user_id=user.id,
            category=category,
            risk_level=risk_level,
            created_at=created_at + timedelta(minutes=3),
            daily_checkin_id=checkin.id,
            reason=f"Detected {category} pattern in daily check-in",
            suggested_action="Check user condition and continue monitoring",
            follow_up_question="Would you like to tell me more?",
            signals_json=[category],
            reasons_json=[f"Check-in pattern matched: {category}"],
            should_alert_family=risk_level in {"high", "critical"},
        )


def main() -> None:
    db: Session = SessionLocal()

    users = [
        create_or_get_user(
            db,
            first_name="Maija",
            last_name="Demo",
            phone_number="+358000000101",
            language="fi",
        ),
        create_or_get_user(
            db,
            first_name="John",
            last_name="Demo",
            phone_number="+358000000102",
            language="en",
        ),
        create_or_get_user(
            db,
            first_name="Anna",
            last_name="Demo",
            phone_number="+358000000103",
            language="sv",
        ),
    ]

    for user in users:
        seed_user_dataset(db, user, user.language)

    print("Demo data created successfully.")
    for user in users:
        print(f"- {user.id}: {user.first_name} {user.last_name} ({user.language})")


if __name__ == "__main__":
    main()