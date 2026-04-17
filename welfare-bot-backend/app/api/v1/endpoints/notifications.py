from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.db.models.care_contact import CareContact
from app.db.models.notification import Notification
from app.db.models.risk_analysis import RiskAnalysis
from app.db.models.user import User
from app.schemas.notification import NotificationCreate, NotificationRead, NotificationUpdate

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/", response_model=list[NotificationRead])
def list_notifications(db: Session = Depends(get_db)) -> list[NotificationRead]:
    return db.query(Notification).order_by(Notification.id.desc()).all()


@router.get("/{notification_id}", response_model=NotificationRead)
def get_notification(
    notification_id: int,
    db: Session = Depends(get_db),
) -> NotificationRead:
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification


@router.get("/user/{user_id}", response_model=list[NotificationRead])
def list_user_notifications(
    user_id: int,
    db: Session = Depends(get_db),
) -> list[NotificationRead]:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.id.desc())
        .all()
    )


@router.post("", response_model=NotificationRead, status_code=status.HTTP_201_CREATED)
def create_notification(
    payload: NotificationCreate,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
) -> NotificationRead:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    care_contact = db.query(CareContact).filter(CareContact.id == payload.care_contact_id).first()
    if not care_contact:
        raise HTTPException(status_code=404, detail="Care contact not found")

    risk_analysis = db.query(RiskAnalysis).filter(RiskAnalysis.id == payload.risk_analysis_id).first()
    if not risk_analysis:
        raise HTTPException(status_code=404, detail="Risk analysis not found")

    notification = Notification(
        user_id=user_id,
        **payload.model_dump(),
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


@router.put("/{notification_id}", response_model=NotificationRead)
def update_notification(
    notification_id: int,
    payload: NotificationUpdate,
    db: Session = Depends(get_db),
) -> NotificationRead:
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(notification, key, value)

    db.commit()
    db.refresh(notification)
    return notification


@router.post("/{notification_id}/mark-sent", response_model=NotificationRead)
def mark_notification_sent(
    notification_id: int,
    db: Session = Depends(get_db),
) -> NotificationRead:
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.status = "sent"
    notification.sent_at = datetime.utcnow()

    db.commit()
    db.refresh(notification)
    return notification


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(
    notification_id: int,
    db: Session = Depends(get_db),
) -> None:
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    db.delete(notification)
    db.commit()