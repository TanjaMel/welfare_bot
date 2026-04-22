from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.db.models.risk_analysis import RiskAnalysis
from app.schemas.risk_analysis import RiskAnalysisCreate, RiskAnalysisRead, RiskAnalysisUpdate
from app.services import risk_service  # import module, not a missing function

router = APIRouter()


@router.get("/", response_model=List[RiskAnalysisRead], summary="List Risk Analyses")
def list_risk_analyses(db: Session = Depends(get_db)):
    return db.query(RiskAnalysis).all()


@router.get("/user/{user_id}", response_model=List[RiskAnalysisRead], summary="List User Risk Analyses")
def list_user_risk_analyses(user_id: int, db: Session = Depends(get_db)):
    return (
        db.query(RiskAnalysis)
        .filter(RiskAnalysis.user_id == user_id)
        .order_by(RiskAnalysis.created_at.desc())
        .all()
    )


@router.get("/{risk_analysis_id}", response_model=RiskAnalysisRead, summary="Get Risk Analysis")
def get_risk_analysis(risk_analysis_id: int, db: Session = Depends(get_db)):
    obj = db.query(RiskAnalysis).filter(RiskAnalysis.id == risk_analysis_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    return obj


@router.put("/{risk_analysis_id}", response_model=RiskAnalysisRead, summary="Update Risk Analysis")
def update_risk_analysis(
    risk_analysis_id: int, payload: RiskAnalysisUpdate, db: Session = Depends(get_db)
):
    obj = db.query(RiskAnalysis).filter(RiskAnalysis.id == risk_analysis_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{risk_analysis_id}", status_code=204, summary="Delete Risk Analysis")
def delete_risk_analysis(risk_analysis_id: int, db: Session = Depends(get_db)):
    obj = db.query(RiskAnalysis).filter(RiskAnalysis.id == risk_analysis_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(obj)
    db.commit()


@router.post("/", response_model=RiskAnalysisRead, status_code=201, summary="Create Risk Analysis")
def create_risk_analysis(payload: RiskAnalysisCreate, db: Session = Depends(get_db)):
    obj = RiskAnalysis(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.post("/analyze-message", summary="Analyze Message")
def analyze_message(text: str, language: str = "fi"):
    # Uses the real risk_service.assess() signature
    result = risk_service.assess(
        current_message=text,
        preferred_language=language,
        elderly=True,
    )
    return result


@router.post("/analyze-checkin", summary="Analyze Checkin")
def analyze_checkin_endpoint(payload: dict):
    # Build a single text from checkin fields and run through assess()
    parts = [
        payload.get("sleep_quality", ""),
        payload.get("food_intake", ""),
        payload.get("hydration", ""),
        payload.get("mood", ""),
        payload.get("notes", ""),
    ]
    text = ". ".join(p for p in parts if p)
    language = payload.get("language", "fi")
    result = risk_service.assess(
        current_message=text,
        preferred_language=language,
        elderly=True,
    )
    return result