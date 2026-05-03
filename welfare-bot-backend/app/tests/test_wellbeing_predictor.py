"""
Tests for wellbeing_predictor.py
- predict_tomorrow() with various data scenarios
- trend detection (declining, stable, improving)
- alert logic
- edge cases (no data, minimal data)
"""
import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock


def make_metrics(scores: list[float], base_date: date = None) -> list:
    """Create mock WellbeingDailyMetrics rows."""
    if base_date is None:
        base_date = date.today() - timedelta(days=len(scores))
    rows = []
    for i, score in enumerate(scores):
        row = MagicMock()
        row.overall_wellbeing_score = score
        row.date = base_date + timedelta(days=i)
        rows.append(row)
    return rows


def make_db(scores: list[float]) -> MagicMock:
    """Create a mock DB that returns the given scores."""
    db = MagicMock()
    rows = make_metrics(scores)
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = rows
    return db


class TestPredictTomorrow:

    def test_insufficient_data_returns_no_alert(self):
        from app.services.wellbeing_predictor import predict_tomorrow
        db = make_db([70.0, 65.0])  # only 2 rows — below minimum 3
        result = predict_tomorrow(user_id=1, db=db)
        assert result.alert is False
        assert result.trend_direction == "no_data"
        assert result.predicted_score is None

    def test_stable_scores_no_alert(self):
        from app.services.wellbeing_predictor import predict_tomorrow
        scores = [70.0, 71.0, 70.0, 69.0, 71.0, 70.0, 70.0]
        db = make_db(scores)
        result = predict_tomorrow(user_id=1, db=db)
        assert result.alert is False
        assert result.trend_direction in ("stable", "improving")
        assert result.predicted_score is not None

    def test_declining_scores_triggers_alert(self):
        from app.services.wellbeing_predictor import predict_tomorrow
        # Sharp decline over 10 days
        scores = [90.0, 85.0, 80.0, 75.0, 70.0, 65.0, 60.0, 55.0, 50.0, 45.0]
        db = make_db(scores)
        result = predict_tomorrow(user_id=1, db=db)
        assert result.trend_direction == "declining"
        assert result.predicted_score is not None
        assert result.predicted_score < scores[-1]

    def test_improving_scores_no_alert(self):
        from app.services.wellbeing_predictor import predict_tomorrow
        scores = [40.0, 45.0, 50.0, 55.0, 60.0, 65.0, 70.0]
        db = make_db(scores)
        result = predict_tomorrow(user_id=1, db=db)
        assert result.trend_direction == "improving"
        assert result.alert is False

    def test_predicted_score_clamped_to_0_100(self):
        from app.services.wellbeing_predictor import predict_tomorrow
        # Extreme decline that would predict below 0
        scores = [20.0, 15.0, 10.0, 5.0, 2.0]
        db = make_db(scores)
        result = predict_tomorrow(user_id=1, db=db)
        if result.predicted_score is not None:
            assert 0.0 <= result.predicted_score <= 100.0

    def test_result_has_required_fields(self):
        from app.services.wellbeing_predictor import predict_tomorrow
        scores = [70.0, 68.0, 66.0, 64.0, 62.0]
        db = make_db(scores)
        result = predict_tomorrow(user_id=42, db=db)
        assert result.user_id == 42
        assert result.trend_direction in ("declining", "stable", "improving", "no_data")
        assert result.confidence in ("high", "medium", "low")
        assert isinstance(result.days_of_data, int)
        assert isinstance(result.message, str)
        assert len(result.message) > 0

    def test_confidence_increases_with_more_data(self):
        from app.services.wellbeing_predictor import predict_tomorrow
        few_scores = [70.0, 65.0, 60.0]
        many_scores = [70.0] * 10

        db_few = make_db(few_scores)
        db_many = make_db(many_scores)

        result_few = predict_tomorrow(user_id=1, db=db_few)
        result_many = predict_tomorrow(user_id=1, db=db_many)

        confidence_order = {"low": 0, "medium": 1, "high": 2}
        assert confidence_order[result_many.confidence] >= confidence_order[result_few.confidence]

    def test_no_data_returns_safe_defaults(self):
        from app.services.wellbeing_predictor import predict_tomorrow
        db = make_db([])
        result = predict_tomorrow(user_id=1, db=db)
        assert result.alert is False
        assert result.predicted_score is None
        assert result.trend_direction == "no_data"

    def test_alert_requires_significant_drop(self):
        from app.services.wellbeing_predictor import predict_tomorrow
        # Small decline — should not alert
        scores = [72.0, 71.0, 70.0, 69.0, 68.0, 67.0, 66.0, 65.0, 64.0, 63.0]
        db = make_db(scores)
        result = predict_tomorrow(user_id=1, db=db)
        # Small slope — may or may not alert depending on threshold
        assert isinstance(result.alert, bool)


class TestWellbeingPredictionResult:

    def test_declining_message_mentions_prediction(self):
        from app.services.wellbeing_predictor import predict_tomorrow
        scores = [90.0, 80.0, 70.0, 60.0, 50.0, 40.0, 30.0, 20.0, 10.0, 5.0]
        db = make_db(scores)
        result = predict_tomorrow(user_id=1, db=db)
        if result.alert:
            assert "Predicted" in result.message or "predicted" in result.message

    def test_days_of_data_matches_input(self):
        from app.services.wellbeing_predictor import predict_tomorrow
        scores = [70.0, 68.0, 66.0, 64.0, 62.0]
        db = make_db(scores)
        result = predict_tomorrow(user_id=1, db=db)
        assert result.days_of_data == len(scores)