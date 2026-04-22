from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.db.models.notification import Notification
from app.schemas.notification import NotificationCreate, NotificationRead, NotificationUpdate

router = APIRouter()

@router.get("/", response_model=List[NotificationRead], summary="List Notifications")
def list_notifications(db: Session = Depends(get_db)):
    return db.query(Notification).all()

@router.get("/{notification_id}", response_model=NotificationRead, summary="Get Notification")
def get_notification(notification_id: int, db: Session = Depends(get_db)):
    obj = db.query(Notification).filter(Notification.id == notification_id).first()
    if not obj: raise HTTPException(status_code=404, detail="Not found")
    return obj

@router.put("/{notification_id}", response_model=NotificationRead, summary="Update Notification")
def update_notification(notification_id: int, payload: NotificationUpdate, db: Session = Depends(get_db)):
    obj = db.query(Notification).filter(Notification.id == notification_id).first()
    if not obj: raise HTTPException(status_code=404, detail="Not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return obj

@router.delete("/{notification_id}", status_code=204, summary="Delete Notification")
def delete_notification(notification_id: int, db: Session = Depends(get_db)):
    obj = db.query(Notification).filter(Notification.id == notification_id).first()
    if not obj: raise HTTPException(status_code=404, detail="Not found")
    db.delete(obj); db.commit()

@router.get("/user/{user_id}", response_model=List[NotificationRead], summary="List User Notifications")
def list_user_notifications(user_id: int, db: Session = Depends(get_db)):
    return db.query(Notification).filter(Notification.user_id == user_id).order_by(Notification.created_at.desc()).all()

@router.post("/", response_model=NotificationRead, status_code=201, summary="Create Notification")
def create_notification(payload: NotificationCreate, db: Session = Depends(get_db)):
    obj = Notification(**payload.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@router.post("/{notification_id}/mark-sent", response_model=NotificationRead, summary="Mark Notification Sent")
def mark_sent(notification_id: int, db: Session = Depends(get_db)):
    from datetime import datetime, timezone
    obj = db.query(Notification).filter(Notification.id == notification_id).first()
    if not obj: raise HTTPException(status_code=404, detail="Not found")
    obj.is_sent = True
    obj.sent_at = datetime.now(timezone.utc)
    db.commit(); db.refresh(obj)
    return obj