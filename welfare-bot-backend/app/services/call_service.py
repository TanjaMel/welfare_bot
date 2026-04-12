from sqlalchemy.orm import Session

from app.db.models.call_session import CallSession
from app.db.models.user import User
from app.schemas.call_session import CallSessionCreate


def list_calls(db: Session) -> list[CallSession]:
    return db.query(CallSession).order_by(CallSession.id.desc()).all()


def create_call(db: Session, payload: CallSessionCreate) -> CallSession:
    user = db.query(User).filter(User.id == payload.user_id).first()
    if user is None:
        raise ValueError("User not found")

    call = CallSession(user_id=payload.user_id)
    db.add(call)
    db.commit()
    db.refresh(call)
    return call