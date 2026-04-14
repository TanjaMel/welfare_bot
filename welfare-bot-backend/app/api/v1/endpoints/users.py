from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models.user import User
from app.schemas.user import UserCreate, UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[UserRead])
def list_users_endpoint(db: Session = Depends(get_db)) -> list[UserRead]:
    users = db.query(User).order_by(User.id.asc()).all()
    return users


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user_endpoint(payload: UserCreate, db: Session = Depends(get_db)) -> UserRead:
    user = User(
        first_name=payload.first_name,
        last_name=payload.last_name,
        language=payload.language,
        phone_number=payload.phone_number,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user