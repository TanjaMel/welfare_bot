"""
app/api/v1/endpoints/ml_insights.py

ML insights endpoints — predictions, quality scores, accuracy metrics.

Mount in api.py:
    from app.api.v1.endpoints.ml_insights import router as ml_router
    api_router.include_router(ml_router, prefix="/admin", tags=["ML Insights"])
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


class PredictionRow(BaseModel):
    user_id: int
    name: str
    predicted_score: Optional[float]
    current_score: Optional[float]
    trend_direction: str
    confidence: str
    days_of_data: int
    alert: bool
    message: str


class PopulationPredictions(BaseModel):
    generated_at: str
    total_users: int
    declining_count: int
    stable_count: int
    improving_count: int
    predictions: list[PredictionRow]


@router.get(
    "/predictions",
    response_model=PopulationPredictions,
    summary="Wellbeing predictions for tomorrow based on linear regression",
)
def get_population_predictions(db: Session = Depends(get_db)):
    from datetime import datetime
    from app.db.models.user import User
    from app.services.wellbeing_predictor import predict_tomorrow

    users = db.query(User).filter(
        User.is_active == True,
        User.role != "admin",
    ).all()

    predictions = []
    for user in users:
        pred = predict_tomorrow(user_id=user.id, db=db)
        name = f"{user.first_name} {user.last_name}".strip() or f"User {user.id}"
        predictions.append(PredictionRow(
            user_id=user.id,
            name=name,
            predicted_score=pred.predicted_score,
            current_score=pred.current_score,
            trend_direction=pred.trend_direction,
            confidence=pred.confidence,
            days_of_data=pred.days_of_data,
            alert=pred.alert,
            message=pred.message,
        ))

    # Sort: alerts first, then declining
    trend_order = {"declining": 0, "stable": 1, "improving": 2, "no_data": 3}
    predictions.sort(key=lambda p: (0 if p.alert else 1, trend_order.get(p.trend_direction, 3)))

    return PopulationPredictions(
        generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        total_users=len(predictions),
        declining_count=sum(1 for p in predictions if p.trend_direction == "declining"),
        stable_count=sum(1 for p in predictions if p.trend_direction == "stable"),
        improving_count=sum(1 for p in predictions if p.trend_direction == "improving"),
        predictions=predictions,
    )