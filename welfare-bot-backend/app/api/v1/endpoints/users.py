from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models.user import User
from app.schemas.user import UserCreate, UserRead

# NO prefix here — prefix="/users" is already set in api.py
router = APIRouter()


@router.get("/", response_model=list[UserRead], summary="List Users Endpoint")
def list_users_endpoint(db: Session = Depends(get_db)) -> list[UserRead]:
    return db.query(User).order_by(User.id.asc()).all()


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED, summary="Create User Endpoint")
def create_user_endpoint(payload: UserCreate, db: Session = Depends(get_db)) -> UserRead:
    existing = db.query(User).filter(User.phone_number == payload.phone_number).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="User with this phone number already exists",
        )
    user = User(
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone_number=payload.phone_number,
        language=payload.language,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserRead, summary="Get User")
def get_user(user_id: int, db: Session = Depends(get_db)) -> UserRead:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user