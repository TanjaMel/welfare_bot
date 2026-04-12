from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models.care_contact import CareContact
from app.db.models.daily_checkin import DailyCheckIn
from app.db.models.notification import Notification
from app.db.models.risk_analysis import RiskAnalysis
from app.db.models.user import User
from app.schemas.checkin import DailyCheckInCreate, DailyCheckInRead, DailyCheckInUpdate
from app.schemas.notification import NotificationRead
from app.schemas.risk_analysis import RiskAnalysisRead
from app.services.risk_analysis_service import (
    analyze_checkin_answers,
    build_notification_message,
)

router = APIRouter(prefix="/checkins", tags=["checkins"])


class DailyCheckInPipelineResponse(BaseModel):
    checkin: DailyCheckInRead
    risk_analysis: RiskAnalysisRead
    notifications: list[NotificationRead]


@router.get("", response_model=list[DailyCheckInRead])
def list_checkins(db: Session = Depends(get_db)) -> list[DailyCheckInRead]:
    return db.query(DailyCheckIn).order_by(DailyCheckIn.id.desc()).all()


@router.get("/user/{user_id}", response_model=list[DailyCheckInRead])
def list_user_checkins(
    user_id: int,
    db: Session = Depends(get_db),
) -> list[DailyCheckInRead]:
    return (
        db.query(DailyCheckIn)
        .filter(DailyCheckIn.user_id == user_id)
        .order_by(DailyCheckIn.checkin_date.desc(), DailyCheckIn.id.desc())
        .all()
    )


@router.get("/{checkin_id}", response_model=DailyCheckInRead)
def get_checkin(
    checkin_id: int,
    db: Session = Depends(get_db),
) -> DailyCheckInRead:
    checkin = db.query(DailyCheckIn).filter(DailyCheckIn.id == checkin_id).first()
    if not checkin:
        raise HTTPException(status_code=404, detail="Check-in not found")
    return checkin


@router.post("", response_model=DailyCheckInPipelineResponse, status_code=status.HTTP_201_CREATED)
def create_checkin(
    payload: DailyCheckInCreate,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
) -> DailyCheckInPipelineResponse:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    checkin = DailyCheckIn(
        user_id=user_id,
        **payload.model_dump(),
        completed_at=datetime.utcnow(),
    )
    db.add(checkin)
    db.commit()
    db.refresh(checkin)

    analysis_data = analyze_checkin_answers(payload)

    analysis = RiskAnalysis(
        user_id=user_id,
        daily_checkin_id=checkin.id,
        category=analysis_data["category"],
        risk_level=analysis_data["risk_level"],
        needs_family_notification=analysis_data["needs_family_notification"],
        reason=analysis_data["reason"],
        suggested_action=analysis_data["suggested_action"],
        model_version=analysis_data["model_version"],
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    created_notifications: list[Notification] = []

    if analysis.needs_family_notification:
        contacts = (
            db.query(CareContact)
            .filter(CareContact.user_id == user_id, CareContact.is_primary.is_(True))
            .all()
        )

        if not contacts:
            contacts = db.query(CareContact).filter(CareContact.user_id == user_id).all()

        for contact in contacts:
            notification = Notification(
                user_id=user_id,
                care_contact_id=contact.id,
                risk_analysis_id=analysis.id,
                channel=contact.preferred_notification_method,
                message=build_notification_message(
                    first_name=user.first_name,
                    last_name=user.last_name,
                    category=analysis.category,
                    risk_level=analysis.risk_level,
                    reason=analysis.reason,
                ),
                status="pending",
            )
            db.add(notification)
            created_notifications.append(notification)

        db.commit()

        for notification in created_notifications:
            db.refresh(notification)

    return DailyCheckInPipelineResponse(
        checkin=DailyCheckInRead.model_validate(checkin),
        risk_analysis=RiskAnalysisRead.model_validate(analysis),
        notifications=[NotificationRead.model_validate(n) for n in created_notifications],
    )


@router.put("/{checkin_id}", response_model=DailyCheckInRead)
def update_checkin(
    checkin_id: int,
    payload: DailyCheckInUpdate,
    db: Session = Depends(get_db),
) -> DailyCheckInRead:
    checkin = db.query(DailyCheckIn).filter(DailyCheckIn.id == checkin_id).first()
    if not checkin:
        raise HTTPException(status_code=404, detail="Check-in not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(checkin, key, value)

    db.commit()
    db.refresh(checkin)
    return checkin


@router.post("/{checkin_id}/complete", response_model=DailyCheckInRead)
def complete_checkin(
    checkin_id: int,
    db: Session = Depends(get_db),
) -> DailyCheckInRead:
    checkin = db.query(DailyCheckIn).filter(DailyCheckIn.id == checkin_id).first()
    if not checkin:
        raise HTTPException(status_code=404, detail="Check-in not found")

    checkin.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(checkin)
    return checkin


@router.delete("/{checkin_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_checkin(
    checkin_id: int,
    db: Session = Depends(get_db),
) -> None:
    checkin = db.query(DailyCheckIn).filter(DailyCheckIn.id == checkin_id).first()
    if not checkin:
        raise HTTPException(status_code=404, detail="Check-in not found")

    db.delete(checkin)
    db.commit()