from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.call_session import CallSessionCreate, CallSessionRead
from app.services.call_service import create_call, list_calls

router = APIRouter(prefix="/calls", tags=["calls"])


@router.get("/", response_model=list[CallSessionRead])
def list_calls_endpoint(db: Session = Depends(get_db)) -> list[CallSessionRead]:
    return list_calls(db)


@router.post("/", response_model=CallSessionRead, status_code=status.HTTP_201_CREATED)
def create_call_endpoint(
    payload: CallSessionCreate,
    db: Session = Depends(get_db),
) -> CallSessionRead:
    try:
        return create_call(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc