from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models.care_contact import CareContact
from app.db.models.user import User
from app.schemas.care_contact import CareContactCreate, CareContactRead, CareContactUpdate

router = APIRouter(prefix="/care-contacts", tags=["care-contacts"])


@router.get("", response_model=list[CareContactRead])
def list_care_contacts(db: Session = Depends(get_db)) -> list[CareContactRead]:
    return db.query(CareContact).order_by(CareContact.id.desc()).all()


@router.get("/user/{user_id}", response_model=list[CareContactRead])
def list_user_care_contacts(
    user_id: int,
    db: Session = Depends(get_db),
) -> list[CareContactRead]:
    return (
        db.query(CareContact)
        .filter(CareContact.user_id == user_id)
        .order_by(CareContact.id.desc())
        .all()
    )


@router.get("/{care_contact_id}", response_model=CareContactRead)
def get_care_contact(
    care_contact_id: int,
    db: Session = Depends(get_db),
) -> CareContactRead:
    contact = db.query(CareContact).filter(CareContact.id == care_contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Care contact not found")
    return contact


@router.post("", response_model=CareContactRead, status_code=status.HTTP_201_CREATED)
def create_care_contact(
    payload: CareContactCreate,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
) -> CareContactRead:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    contact = CareContact(user_id=user_id, **payload.model_dump())
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


@router.put("/{care_contact_id}", response_model=CareContactRead)
def update_care_contact(
    care_contact_id: int,
    payload: CareContactUpdate,
    db: Session = Depends(get_db),
) -> CareContactRead:
    contact = db.query(CareContact).filter(CareContact.id == care_contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Care contact not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(contact, key, value)

    db.commit()
    db.refresh(contact)
    return contact


@router.delete("/{care_contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_care_contact(
    care_contact_id: int,
    db: Session = Depends(get_db),
) -> None:
    contact = db.query(CareContact).filter(CareContact.id == care_contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Care contact not found")

    db.delete(contact)
    db.commit()