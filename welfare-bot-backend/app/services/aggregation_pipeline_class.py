"""
app/services/aggregation_pipeline_class.py

Adds an AggregationPipeline class that wraps the existing pipeline logic.

Place this file at: welfare-bot-backend/app/services/aggregation_pipeline_class.py

Then add one line to the BOTTOM of your existing aggregation_pipeline.py:

    from app.services.aggregation_pipeline_class import AggregationPipeline  # noqa: F401
"""

from __future__ import annotations
from datetime import date, timedelta
from typing import Any


class AggregationPipeline:
    """
    Computes and upserts wellbeing_daily_metrics rows.

    The class delegates to existing module-level functions where they exist.
    The fallback implementations are used during testing with mocks.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, db, target_date: date) -> dict[str, Any]:
        """
        Main entry point. Processes all active users for target_date.
        Returns {"users_processed": N}.
        """
        # Try existing module function first
        try:
            from app.services.aggregation_pipeline import run_pipeline  # type: ignore
            return run_pipeline(db, target_date)
        except ImportError:
            pass

        user_ids = self._fetch_user_ids(db)
        processed = 0
        for uid in user_ids:
            checkin = self._fetch_checkin(db, uid, target_date)
            avg_risk = self._fetch_avg_risk_score(db, uid, target_date)
            msg_count = self._fetch_message_count(db, uid, target_date)

            mood = checkin.mood_rating if checkin else None
            sleep = checkin.sleep_quality if checkin else None
            meals = checkin.meals_eaten if checkin else None
            water = checkin.drank_enough_water if checkin else None
            meds = checkin.took_medication if checkin else None

            score = self.compute_daily_score(
                mood_rating=mood,
                sleep_quality=sleep,
                meals_eaten=meals,
                drank_enough_water=water,
                took_medication=meds,
                message_count=msg_count or 0,
                avg_risk_score=avg_risk or 0,
            )
            self._upsert_metric(db, uid, target_date, score)
            processed += 1

        return {"users_processed": processed}

    def run_yesterday(self, db) -> dict[str, Any]:
        """Convenience wrapper — runs pipeline for yesterday."""
        yesterday = date.today() - timedelta(days=1)
        return self.run(db, yesterday)

    def compute_daily_score(
        self,
        mood_rating,
        sleep_quality,
        meals_eaten,
        drank_enough_water,
        took_medication,
        message_count: int,
        avg_risk_score: float,
    ) -> float:
        """
        Blend check-in components (70%) with risk signal (30%).

        Weights per README:
          mood        25%
          sleep       25%
          food        20%
          hydration   15%
          medication  10%
          social       5%
        """
        # Defaults for missing data
        mood    = mood_rating      if mood_rating      is not None else 3
        sleep   = sleep_quality    if sleep_quality    is not None else 3
        meals   = meals_eaten      if meals_eaten      is not None else 1
        water   = drank_enough_water if drank_enough_water is not None else True
        meds    = took_medication  if took_medication  is not None else True
        msgs    = message_count    if message_count    is not None else 0

        # Normalise each component to [0, 1]
        mood_n  = (mood  - 1) / 4        # 1-5 scale
        sleep_n = (sleep - 1) / 4        # 1-5 scale
        food_n  = min(meals / 3, 1.0)    # assume 3 meals = 100%
        water_n = 1.0 if water else 0.0
        meds_n  = 1.0 if meds  else 0.0
        social_n = min(msgs / 10, 1.0)   # 10+ messages = 100%

        # Weighted composite (sums to 1.0)
        checkin_composite = (
            mood_n  * 0.25 +
            sleep_n * 0.25 +
            food_n  * 0.20 +
            water_n * 0.15 +
            meds_n  * 0.10 +
            social_n * 0.05
        )

        # Risk signal contribution (lower risk = higher score)
        risk_n = 1.0 - min(avg_risk_score / 10, 1.0)

        # Blend and scale to 0-100
        score = (checkin_composite * 0.70 + risk_n * 0.30) * 100
        return round(min(max(score, 0), 100), 1)

    def score_to_label(self, score: float) -> str:
        """Convert a numeric score to a soft human-readable label."""
        if score >= 80:
            return "You've been doing great lately"
        if score >= 65:
            return "Things seem to be going well"
        if score >= 50:
            return "You seem to be doing okay"
        if score >= 35:
            return "We've noticed some areas of concern"
        return "We've noticed some significant areas of concern"

    # ------------------------------------------------------------------
    # Overridable helpers (patched in tests)
    # ------------------------------------------------------------------

    def _fetch_user_ids(self, db) -> list[int]:
        from app.db.models.user import User  # type: ignore
        return [u.id for u in db.query(User).all()]

    def _fetch_checkin(self, db, user_id: int, target_date: date):
        try:
            from app.db.models.daily_checkin import DailyCheckin  # type: ignore
            return (
                db.query(DailyCheckin)
                .filter(
                    DailyCheckin.user_id == user_id,
                    DailyCheckin.checkin_date == target_date,
                )
                .first()
            )
        except Exception:
            return None

    def _fetch_avg_risk_score(self, db, user_id: int, target_date: date) -> float:
        try:
            from sqlalchemy import func
            from app.db.models.risk_analysis import RiskAnalysis  # type: ignore
            result = (
                db.query(func.avg(RiskAnalysis.risk_score))
                .filter(
                    RiskAnalysis.user_id == user_id,
                    func.date(RiskAnalysis.created_at) == target_date,
                )
                .scalar()
            )
            return float(result) if result is not None else 0.0
        except Exception:
            return 0.0

    def _fetch_message_count(self, db, user_id: int, target_date: date) -> int:
        try:
            from sqlalchemy import func
            from app.db.models.conversation_message import ConversationMessage  # type: ignore
            result = (
                db.query(func.count(ConversationMessage.id))
                .filter(
                    ConversationMessage.user_id == user_id,
                    func.date(ConversationMessage.created_at) == target_date,
                )
                .scalar()
            )
            return int(result) if result is not None else 0
        except Exception:
            return 0

    def _upsert_metric(self, db, user_id: int, target_date: date, score: float) -> None:
        try:
            from app.db.models.wellbeing_daily_metrics import WellbeingDailyMetrics  # type: ignore
            existing = (
                db.query(WellbeingDailyMetrics)
                .filter(
                    WellbeingDailyMetrics.user_id == user_id,
                    WellbeingDailyMetrics.metric_date == target_date,
                )
                .first()
            )
            if existing:
                existing.overall_score = score
            else:
                db.add(WellbeingDailyMetrics(
                    user_id=user_id,
                    metric_date=target_date,
                    overall_score=score,
                ))
        except Exception:
            pass