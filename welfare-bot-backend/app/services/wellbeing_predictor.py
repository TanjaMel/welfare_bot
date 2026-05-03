"""
app/services/wellbeing_predictor.py

Predicts tomorrow's wellbeing score using linear regression on recent history.
Proactive rather than reactive — flags users whose score is predicted to decline
before it actually drops.

Uses scikit-learn LinearRegression — no new dependencies needed.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class WellbeingPrediction:
    def __init__(
        self,
        user_id: int,
        predicted_score: Optional[float],
        current_score: Optional[float],
        trend_direction: str,      # "declining" | "stable" | "improving"
        confidence: str,           # "high" | "medium" | "low"
        days_of_data: int,
        alert: bool,
        message: str,
    ):
        self.user_id = user_id
        self.predicted_score = predicted_score
        self.current_score = current_score
        self.trend_direction = trend_direction
        self.confidence = confidence
        self.days_of_data = days_of_data
        self.alert = alert
        self.message = message


def predict_tomorrow(
    user_id: int,
    db,
    assessment_date: Optional[date] = None,
) -> WellbeingPrediction:
    """
    Predict tomorrow's wellbeing score using linear regression
    on the last 14 days of wellbeing metrics.
    """
    try:
        import numpy as np
        from sklearn.linear_model import LinearRegression
        from app.db.models.wellbeing_daily_metrics import WellbeingDailyMetrics

        ref_date = assessment_date or date.today()
        window_start = ref_date - timedelta(days=14)

        rows = (
            db.query(WellbeingDailyMetrics)
            .filter(
                WellbeingDailyMetrics.user_id == user_id,
                WellbeingDailyMetrics.date >= window_start,
                WellbeingDailyMetrics.date <= ref_date,
            )
            .order_by(WellbeingDailyMetrics.date)
            .all()
        )

        if len(rows) < 3:
            return WellbeingPrediction(
                user_id=user_id,
                predicted_score=None,
                current_score=None,
                trend_direction="no_data",
                confidence="low",
                days_of_data=len(rows),
                alert=False,
                message="Not enough data for prediction yet.",
            )

        # Prepare features: day index (0, 1, 2...) and score
        X = np.array([[i] for i in range(len(rows))])
        y = np.array([r.overall_wellbeing_score or 50.0 for r in rows])

        model = LinearRegression()
        model.fit(X, y)

        # Predict next day
        next_day_idx = np.array([[len(rows)]])
        predicted = float(model.predict(next_day_idx)[0])
        predicted = max(0.0, min(100.0, predicted))  # clamp to 0-100

        current_score = float(rows[-1].overall_wellbeing_score or 50.0)
        slope = float(model.coef_[0])

        # Determine trend
        if slope < -1.5:
            trend = "declining"
        elif slope > 1.5:
            trend = "improving"
        else:
            trend = "stable"

        # Confidence based on data quantity
        if len(rows) >= 10:
            confidence = "high"
        elif len(rows) >= 5:
            confidence = "medium"
        else:
            confidence = "low"

        # Alert if predicted score is declining significantly
        score_drop = current_score - predicted
        alert = trend == "declining" and score_drop > 5 and confidence in ("high", "medium")

        if alert:
            message = (
                f"Predicted score tomorrow: {round(predicted, 1)}% "
                f"(down {round(score_drop, 1)}% from today). "
                f"Proactive check-in recommended."
            )
        elif trend == "improving":
            message = f"Wellbeing improving. Predicted tomorrow: {round(predicted, 1)}%."
        else:
            message = f"Wellbeing stable. Predicted tomorrow: {round(predicted, 1)}%."

        return WellbeingPrediction(
            user_id=user_id,
            predicted_score=round(predicted, 1),
            current_score=round(current_score, 1),
            trend_direction=trend,
            confidence=confidence,
            days_of_data=len(rows),
            alert=alert,
            message=message,
        )

    except Exception as e:
        logger.error("Prediction failed for user %d: %s", user_id, e)
        return WellbeingPrediction(
            user_id=user_id,
            predicted_score=None,
            current_score=None,
            trend_direction="no_data",
            confidence="low",
            days_of_data=0,
            alert=False,
            message="Prediction unavailable.",
        )


def run_population_predictions(db) -> list[WellbeingPrediction]:
    """
    Run predictions for all active non-admin users.
    Called by scheduler — results used to pre-flag declining users.
    """
    from app.db.models.user import User

    users = db.query(User).filter(
        User.is_active == True,
        User.role != "admin",
    ).all()

    results = []
    for user in users:
        prediction = predict_tomorrow(user_id=user.id, db=db)
        results.append(prediction)

    declining = [r for r in results if r.alert]
    logger.info(
        "Population predictions: %d users, %d predicted to decline",
        len(results), len(declining),
    )
    return results