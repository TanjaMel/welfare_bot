from sqlalchemy.orm import Session

from app.db.models.user import User
from app.schemas.user import UserCreate


def list_users(db: Session) -> list[User]:
    return db.query(User).order_by(User.id.desc()).all()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_phone_number(db: Session, phone_number: str) -> User | None:
    return db.query(User).filter(User.phone_number == phone_number).first()


def create_user(db: Session, payload: UserCreate) -> User:
    try:
        user = User(**payload.model_dump())
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except Exception:
        db.rollback()
        raise