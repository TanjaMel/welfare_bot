from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.db.models.care_contact import CareContact
from app.schemas.care_contact import CareContactCreate, CareContactRead, CareContactUpdate

router = APIRouter()

@router.get("/", response_model=List[CareContactRead], summary="List Care Contacts")
def list_care_contacts(db: Session = Depends(get_db)):
    return db.query(CareContact).all()

@router.post("/", response_model=CareContactRead, status_code=201, summary="Create Care Contact")
def create_care_contact(payload: CareContactCreate, db: Session = Depends(get_db)):
    obj = CareContact(**payload.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@router.get("/user/{user_id}", response_model=List[CareContactRead], summary="List User Care Contacts")
def list_user_care_contacts(user_id: int, db: Session = Depends(get_db)):
    return db.query(CareContact).filter(CareContact.user_id == user_id).all()

@router.get("/{care_contact_id}", response_model=CareContactRead, summary="Get Care Contact")
def get_care_contact(care_contact_id: int, db: Session = Depends(get_db)):
    obj = db.query(CareContact).filter(CareContact.id == care_contact_id).first()
    if not obj: raise HTTPException(status_code=404, detail="Not found")
    return obj

@router.put("/{care_contact_id}", response_model=CareContactRead, summary="Update Care Contact")
def update_care_contact(care_contact_id: int, payload: CareContactUpdate, db: Session = Depends(get_db)):
    obj = db.query(CareContact).filter(CareContact.id == care_contact_id).first()
    if not obj: raise HTTPException(status_code=404, detail="Not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return obj

@router.delete("/{care_contact_id}", status_code=204, summary="Delete Care Contact")
def delete_care_contact(care_contact_id: int, db: Session = Depends(get_db)):
    obj = db.query(CareContact).filter(CareContact.id == care_contact_id).first()
    if not obj: raise HTTPException(status_code=404, detail="Not found")
    db.delete(obj); db.commit()