from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.db.models.daily_checkin import DailyCheckIn
from app.db.models.risk_analysis import RiskAnalysis
from app.db.models.notification import Notification
from app.schemas.checkin import DailyCheckInCreate, DailyCheckInRead, DailyCheckInUpdate
from app.schemas.checkin_response import CheckinAnalysisResponse
from app.schemas.risk_analysis import RiskAnalysisResponse
from app.schemas.notification import NotificationRead

from app.services import risk_service as risk_service  # no change needed if file exists

router = APIRouter()


@router.get("/", response_model=List[DailyCheckInRead], summary="List Checkins")
def list_checkins(db: Session = Depends(get_db)):
    return db.query(DailyCheckIn).all()


@router.post("/", response_model=CheckinAnalysisResponse, status_code=201, summary="Create Checkin")
def create_checkin(payload: DailyCheckInCreate, db: Session = Depends(get_db)):
    # 1. Save check-in
    checkin = DailyCheckIn(
        user_id=payload.user_id,
        checkin_date=payload.checkin_date,
        sleep_quality=payload.sleep_quality,
        food_intake=payload.food_intake,
        hydration=payload.hydration,
        mood=payload.mood,
        notes=payload.notes,
    )
    db.add(checkin)
    db.commit()
    db.refresh(checkin)

    # 2. Build text for risk analysis from checkin fields
    checkin_text_parts = []
    if payload.sleep_quality:
        checkin_text_parts.append(payload.sleep_quality)
    if payload.food_intake:
        checkin_text_parts.append(payload.food_intake)
    if payload.hydration:
        checkin_text_parts.append(payload.hydration)
    if payload.mood:
        checkin_text_parts.append(payload.mood)
    if payload.notes:
        checkin_text_parts.append(payload.notes)
    checkin_text = ". ".join(checkin_text_parts)

    # 3. Run risk assessment using the real risk_service
    result = risk_service.assess(
        current_message=checkin_text,
        preferred_language=None,
        elderly=True,
    )

    # 4. Save RiskAnalysis — using the actual ORM column names
    risk = RiskAnalysis(
        user_id=payload.user_id,
        daily_checkin_id=checkin.id,
        conversation_message_id=None,
        category=result["category"],
        risk_level=result["risk_level"],
        risk_score=result["score"],
        reason="; ".join(result["reasons"]) if result["reasons"] else None,
        suggested_action=result["suggested_action"],
        follow_up_question=result["follow_up_question"],
        signals_json=result["signals"],
        reasons_json=result["reasons"],
        should_alert_family=result["should_alert_family"],
        model_version="rule_engine_v1",
    )
    db.add(risk)
    db.commit()
    db.refresh(risk)

    # 5. Create notification if needed — using actual ORM column names
    notifications: list[NotificationRead] = []
    if result["should_alert_family"]:
        notif = Notification(
            user_id=payload.user_id,
            risk_analysis_id=risk.id,
            channel="sms",
            message=(
                f"Risk level '{result['risk_level']}' detected in check-in. "
                f"{result['suggested_action']}"
            ),
            status="pending",
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)
        notifications.append(NotificationRead.model_validate(notif))

    return CheckinAnalysisResponse(
        checkin=DailyCheckInRead.model_validate(checkin),
        risk_analysis=RiskAnalysisResponse.model_validate(risk),
        notifications=notifications,
    )


@router.get("/user/{user_id}", response_model=List[DailyCheckInRead], summary="List User Checkins")
def list_user_checkins(user_id: int, db: Session = Depends(get_db)):
    return (
        db.query(DailyCheckIn)
        .filter(DailyCheckIn.user_id == user_id)
        .order_by(DailyCheckIn.created_at.desc())
        .all()
    )


@router.get("/{checkin_id}", response_model=DailyCheckInRead, summary="Get Checkin")
def get_checkin(checkin_id: int, db: Session = Depends(get_db)):
    obj = db.query(DailyCheckIn).filter(DailyCheckIn.id == checkin_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Checkin not found")
    return obj


@router.put("/{checkin_id}", response_model=DailyCheckInRead, summary="Update Checkin")
def update_checkin(
    checkin_id: int, payload: DailyCheckInUpdate, db: Session = Depends(get_db)
):
    obj = db.query(DailyCheckIn).filter(DailyCheckIn.id == checkin_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Checkin not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{checkin_id}", status_code=204, summary="Delete Checkin")
def delete_checkin(checkin_id: int, db: Session = Depends(get_db)):
    obj = db.query(DailyCheckIn).filter(DailyCheckIn.id == checkin_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Checkin not found")
    db.delete(obj)
    db.commit()