from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models.conversation_message import ConversationMessage
from app.db.models.daily_checkin import DailyCheckIn
from app.db.models.risk_analysis import RiskAnalysis
from app.db.models.user import User
from app.schemas.risk_analysis import (
    RiskAnalysisCreate,
    RiskAnalysisRead,
    RiskAnalysisUpdate,
)

router = APIRouter(prefix="/risk-analysis", tags=["risk-analysis"])


@router.get("/", response_model=list[RiskAnalysisRead])
def list_risk_analyses(db: Session = Depends(get_db)) -> list[RiskAnalysisRead]:
    return db.query(RiskAnalysis).order_by(RiskAnalysis.id.desc()).all()


@router.get("/{risk_analysis_id}", response_model=RiskAnalysisRead)
def get_risk_analysis(
    risk_analysis_id: int,
    db: Session = Depends(get_db),
) -> RiskAnalysisRead:
    analysis = db.query(RiskAnalysis).filter(RiskAnalysis.id == risk_analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Risk analysis not found")
    return analysis


@router.get("/user/{user_id}", response_model=list[RiskAnalysisRead])
def list_user_risk_analyses(
    user_id: int,
    db: Session = Depends(get_db),
) -> list[RiskAnalysisRead]:
    return (
        db.query(RiskAnalysis)
        .filter(RiskAnalysis.user_id == user_id)
        .order_by(RiskAnalysis.id.desc())
        .all()
    )


@router.post("", response_model=RiskAnalysisRead, status_code=status.HTTP_201_CREATED)
def create_risk_analysis(
    payload: RiskAnalysisCreate,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
) -> RiskAnalysisRead:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.conversation_message_id is None and payload.daily_checkin_id is None:
        raise HTTPException(
            status_code=400,
            detail="conversation_message_id or daily_checkin_id is required",
        )

    if payload.conversation_message_id is not None:
        message = (
            db.query(ConversationMessage)
            .filter(ConversationMessage.id == payload.conversation_message_id)
            .first()
        )
        if not message:
            raise HTTPException(status_code=404, detail="Conversation message not found")

    if payload.daily_checkin_id is not None:
        checkin = (
            db.query(DailyCheckIn)
            .filter(DailyCheckIn.id == payload.daily_checkin_id)
            .first()
        )
        if not checkin:
            raise HTTPException(status_code=404, detail="Daily check-in not found")

    analysis = RiskAnalysis(
        user_id=user_id,
        **payload.model_dump(),
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


@router.put("/{risk_analysis_id}", response_model=RiskAnalysisRead)
def update_risk_analysis(
    risk_analysis_id: int,
    payload: RiskAnalysisUpdate,
    db: Session = Depends(get_db),
) -> RiskAnalysisRead:
    analysis = db.query(RiskAnalysis).filter(RiskAnalysis.id == risk_analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Risk analysis not found")

    data = payload.model_dump(exclude_unset=True)

    if "conversation_message_id" in data and data["conversation_message_id"] is not None:
        message = (
            db.query(ConversationMessage)
            .filter(ConversationMessage.id == data["conversation_message_id"])
            .first()
        )
        if not message:
            raise HTTPException(status_code=404, detail="Conversation message not found")

    if "daily_checkin_id" in data and data["daily_checkin_id"] is not None:
        checkin = (
            db.query(DailyCheckIn)
            .filter(DailyCheckIn.id == data["daily_checkin_id"])
            .first()
        )
        if not checkin:
            raise HTTPException(status_code=404, detail="Daily check-in not found")

    for key, value in data.items():
        setattr(analysis, key, value)

    db.commit()
    db.refresh(analysis)
    return analysis


@router.post("/analyze-message")
def analyze_message(payload: dict):
    text = str(payload.get("message", "")).lower().strip()

    result = {
        "category": "normal",
        "risk_level": "low",
        "needs_family_notification": False,
        "reason": "No immediate risk detected.",
        "suggested_action": "none",
    }

    if any(phrase in text for phrase in [
        "fell",
        "fall",
        "cannot get up",
        "can't get up",
        "ambulance",
        "help me",
        "i need help",
    ]):
        result = {
            "category": "fall_or_injury",
            "risk_level": "urgent",
            "needs_family_notification": True,
            "reason": "Possible fall or urgent physical emergency detected.",
            "suggested_action": "urgent_alert",
        }

    elif any(phrase in text for phrase in [
        "forgot medicine",
        "forgot my medicine",
        "missed medicine",
        "missed my medicine",
        "did not take my medicine",
        "didn't take my medicine",
        "did not take medicine",
        "didn't take medicine",
    ]):
        result = {
            "category": "medication_issue",
            "risk_level": "medium",
            "needs_family_notification": True,
            "reason": "Possible missed medication detected.",
            "suggested_action": "notify_family",
        }

    elif any(phrase in text for phrase in [
        "dizzy",
        "weak",
        "confused",
        "pain",
        "i feel unwell",
        "i don't feel well",
    ]):
        result = {
            "category": "health_issue",
            "risk_level": "medium",
            "needs_family_notification": True,
            "reason": "Possible health-related issue detected.",
            "suggested_action": "notify_family",
        }

    elif any(phrase in text for phrase in [
        "lonely",
        "sad",
        "depressed",
        "anxious",
        "worried",
    ]):
        result = {
            "category": "emotional_support",
            "risk_level": "low",
            "needs_family_notification": False,
            "reason": "The message suggests emotional support may be needed.",
            "suggested_action": "follow_up_question",
        }

    return result


@router.post("/analyze-checkin")
def analyze_checkin(payload: dict):
    sleep_answer = str(payload.get("sleep_answer", "")).lower()
    food_answer = str(payload.get("food_answer", "")).lower()
    medication_answer = str(payload.get("medication_answer", "")).lower()
    mood_answer = str(payload.get("mood_answer", "")).lower()

    category = "normal"
    risk_level = "low"
    needs_family_notification = False
    reason = "No immediate risk detected."
    suggested_action = "none"

    if "forgot" in medication_answer or "missed" in medication_answer or medication_answer == "no":
        category = "medication_issue"
        risk_level = "medium"
        needs_family_notification = True
        reason = "The user may have missed medication."
        suggested_action = "notify_family"

    elif "did not eat" in food_answer or "no" in food_answer or "not eat" in food_answer:
        category = "missed_meal"
        risk_level = "medium"
        needs_family_notification = True
        reason = "The user may have skipped meals."
        suggested_action = "notify_family"

    elif "bad" in sleep_answer or "poor" in sleep_answer:
        category = "poor_sleep"
        risk_level = "low"
        reason = "The user reports poor sleep."
        suggested_action = "follow_up_question"

    elif "sad" in mood_answer or "lonely" in mood_answer or "worried" in mood_answer:
        category = "emotional_support"
        risk_level = "low"
        reason = "The user may need emotional support."
        suggested_action = "follow_up_question"

    return {
        "category": category,
        "risk_level": risk_level,
        "needs_family_notification": needs_family_notification,
        "reason": reason,
        "suggested_action": suggested_action,
    }


@router.delete("/{risk_analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_risk_analysis(
    risk_analysis_id: int,
    db: Session = Depends(get_db),
) -> None:
    analysis = db.query(RiskAnalysis).filter(RiskAnalysis.id == risk_analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Risk analysis not found")

    db.delete(analysis)
    db.commit()