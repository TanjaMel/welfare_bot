from fastapi import APIRouter, status

from app.schemas.user import UserCreate, UserRead

router = APIRouter(prefix="/users", tags=["users"])

_fake_users: list[UserRead] = []
_next_id = 1


@router.get("/", response_model=list[UserRead])
def list_users_endpoint() -> list[UserRead]:
    return _fake_users


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user_endpoint(payload: UserCreate) -> UserRead:
    global _next_id

    user = UserRead(
        id=_next_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        language=payload.language,
        phone_number=payload.phone_number,
    )
    _fake_users.append(user)
    _next_id += 1
    return user