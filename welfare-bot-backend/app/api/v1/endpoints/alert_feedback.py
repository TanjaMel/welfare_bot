"""
app/api/v1/endpoints/alert_feedback.py

Care worker feedback on risk alerts — was this alert helpful?
This creates labeled data for ML accuracy tracking.

Endpoints:
    POST /admin/feedback          — submit feedback on a risk analysis
    GET  /admin/feedback/accuracy — get precision/recall/F1 summary
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.risk_analysis import RiskAnalysis

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# In-DB feedback storage using existing risk_analysis table
# We add feedback via a simple endpoint that updates a JSON field
# ---------------------------------------------------------------------------

class FeedbackRequest(BaseModel):
    risk_analysis_id: int
    was_helpful: bool          # True = alert was correct, False = false alarm
    notes: Optional[str] = None  # Optional care worker note


class FeedbackResponse(BaseModel):
    risk_analysis_id: int
    was_helpful: bool
    message: str


class AccuracyMetrics(BaseModel):
    total_alerts: int
    feedback_received: int
    feedback_coverage_pct: float
    true_positives: int        # Helpful alerts
    false_positives: int       # False alarms
    precision: Optional[float] # TP / (TP + FP)
    interpretation: str
    recommendation: str


# ---------------------------------------------------------------------------
# We store feedback in risk_analysis.signals_json as a feedback key
# This avoids a new migration while still persisting the data
# ---------------------------------------------------------------------------

@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    summary="Submit care worker feedback on a risk alert",
)
def submit_feedback(
    payload: FeedbackRequest,
    db: Session = Depends(get_db),
):
    risk = db.query(RiskAnalysis).filter(
        RiskAnalysis.id == payload.risk_analysis_id
    ).first()

    if not risk:
        raise HTTPException(status_code=404, detail="Risk analysis not found")

    # Store feedback in signals_json
    signals = risk.signals_json or {}
    if isinstance(signals, list):
        signals = {}

    signals["feedback"] = {
        "was_helpful": payload.was_helpful,
        "notes": payload.notes,
        "submitted_at": datetime.utcnow().isoformat(),
    }

    risk.signals_json = signals
    db.commit()

    return FeedbackResponse(
        risk_analysis_id=payload.risk_analysis_id,
        was_helpful=payload.was_helpful,
        message="Thank you for your feedback. This helps improve alert accuracy.",
    )


@router.get(
    "/feedback/accuracy",
    response_model=AccuracyMetrics,
    summary="Get ML alert accuracy metrics based on care worker feedback",
)
def get_accuracy_metrics(db: Session = Depends(get_db)):
    """
    Calculate precision based on care worker feedback.
    Precision = true positives / (true positives + false positives)
    """
    # Get all risk analyses that have feedback
    all_risks = (
        db.query(RiskAnalysis)
        .filter(RiskAnalysis.risk_level.in_(["high", "critical"]))
        .all()
    )

    total_alerts = len(all_risks)
    true_positives = 0
    false_positives = 0

    for risk in all_risks:
        signals = risk.signals_json or {}
        if isinstance(signals, dict) and "feedback" in signals:
            feedback = signals["feedback"]
            if feedback.get("was_helpful"):
                true_positives += 1
            else:
                false_positives += 1

    feedback_received = true_positives + false_positives
    coverage = round(feedback_received / total_alerts * 100, 1) if total_alerts > 0 else 0.0

    precision = None
    interpretation = "No feedback data yet — ask care workers to rate alerts."
    recommendation = "Start collecting feedback by using the thumbs up/down buttons on alerts."

    if feedback_received >= 5:
        precision = round(true_positives / feedback_received * 100, 1) if feedback_received > 0 else 0.0

        if precision >= 80:
            interpretation = f"Excellent — {precision}% of alerts were genuinely helpful."
            recommendation = "Model is performing well. Keep current contamination threshold."
        elif precision >= 60:
            interpretation = f"Acceptable — {precision}% of alerts were helpful."
            recommendation = "Consider raising contamination threshold to reduce false alarms."
        else:
            interpretation = f"Too many false alarms — only {precision}% of alerts were helpful."
            recommendation = "Raise contamination threshold from 0.05 to 0.08 or 0.10."

    return AccuracyMetrics(
        total_alerts=total_alerts,
        feedback_received=feedback_received,
        feedback_coverage_pct=coverage,
        true_positives=true_positives,
        false_positives=false_positives,
        precision=precision,
        interpretation=interpretation,
        recommendation=recommendation,
    )