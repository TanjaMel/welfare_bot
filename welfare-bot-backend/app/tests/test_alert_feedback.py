"""
Tests for alert_feedback.py
- submit feedback on risk analyses
- accuracy metrics calculation
- precision/recall interpretation
"""
import pytest
from unittest.mock import MagicMock, patch


def make_risk_analysis(risk_level: str = "high", signals: dict = None) -> MagicMock:
    ra = MagicMock()
    ra.id = 1
    ra.risk_level = risk_level
    ra.signals_json = signals or {}
    return ra


class TestSubmitFeedback:

    def test_helpful_feedback_stored(self):
        from app.api.v1.endpoints.alert_feedback import submit_feedback, FeedbackRequest
        db = MagicMock()
        risk = make_risk_analysis()
        db.query.return_value.filter.return_value.first.return_value = risk

        payload = FeedbackRequest(risk_analysis_id=1, was_helpful=True)
        result = submit_feedback(payload, db)

        assert result.was_helpful is True
        assert result.risk_analysis_id == 1
        db.commit.assert_called_once()

    def test_false_alarm_feedback_stored(self):
        from app.api.v1.endpoints.alert_feedback import submit_feedback, FeedbackRequest
        db = MagicMock()
        risk = make_risk_analysis()
        db.query.return_value.filter.return_value.first.return_value = risk

        payload = FeedbackRequest(risk_analysis_id=1, was_helpful=False, notes="Not relevant")
        result = submit_feedback(payload, db)

        assert result.was_helpful is False
        db.commit.assert_called_once()

    def test_nonexistent_risk_raises_404(self):
        from fastapi import HTTPException
        from app.api.v1.endpoints.alert_feedback import submit_feedback, FeedbackRequest
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        payload = FeedbackRequest(risk_analysis_id=999, was_helpful=True)
        with pytest.raises(HTTPException) as exc_info:
            submit_feedback(payload, db)
        assert exc_info.value.status_code == 404

    def test_feedback_stored_in_signals_json(self):
        from app.api.v1.endpoints.alert_feedback import submit_feedback, FeedbackRequest
        db = MagicMock()
        risk = make_risk_analysis(signals={})
        db.query.return_value.filter.return_value.first.return_value = risk

        payload = FeedbackRequest(risk_analysis_id=1, was_helpful=True, notes="Good catch")
        submit_feedback(payload, db)

        assert "feedback" in risk.signals_json
        assert risk.signals_json["feedback"]["was_helpful"] is True
        assert risk.signals_json["feedback"]["notes"] == "Good catch"

    def test_feedback_overwrites_previous(self):
        from app.api.v1.endpoints.alert_feedback import submit_feedback, FeedbackRequest
        db = MagicMock()
        risk = make_risk_analysis(signals={"feedback": {"was_helpful": False}})
        db.query.return_value.filter.return_value.first.return_value = risk

        payload = FeedbackRequest(risk_analysis_id=1, was_helpful=True)
        submit_feedback(payload, db)

        assert risk.signals_json["feedback"]["was_helpful"] is True

    def test_response_has_thank_you_message(self):
        from app.api.v1.endpoints.alert_feedback import submit_feedback, FeedbackRequest
        db = MagicMock()
        risk = make_risk_analysis()
        db.query.return_value.filter.return_value.first.return_value = risk

        payload = FeedbackRequest(risk_analysis_id=1, was_helpful=True)
        result = submit_feedback(payload, db)

        assert len(result.message) > 0


class TestAccuracyMetrics:

    def _make_risks_with_feedback(self, feedbacks: list[bool]) -> list:
        risks = []
        for i, helpful in enumerate(feedbacks):
            r = MagicMock()
            r.id = i
            r.risk_level = "high"
            r.signals_json = {"feedback": {"was_helpful": helpful}}
            risks.append(r)
        return risks

    def test_no_feedback_returns_interpretation(self):
        from app.api.v1.endpoints.alert_feedback import get_accuracy_metrics
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []

        result = get_accuracy_metrics(db)
        assert result.total_alerts == 0
        assert result.feedback_received == 0
        assert result.precision is None
        assert len(result.interpretation) > 0

    def test_all_helpful_gives_100_precision(self):
        from app.api.v1.endpoints.alert_feedback import get_accuracy_metrics
        db = MagicMock()
        risks = self._make_risks_with_feedback([True, True, True, True, True])
        db.query.return_value.filter.return_value.all.return_value = risks

        result = get_accuracy_metrics(db)
        assert result.true_positives == 5
        assert result.false_positives == 0
        assert result.precision == 100.0

    def test_all_false_alarms_gives_0_precision(self):
        from app.api.v1.endpoints.alert_feedback import get_accuracy_metrics
        db = MagicMock()
        risks = self._make_risks_with_feedback([False, False, False, False, False])
        db.query.return_value.filter.return_value.all.return_value = risks

        result = get_accuracy_metrics(db)
        assert result.true_positives == 0
        assert result.false_positives == 5
        assert result.precision == 0.0

    def test_mixed_feedback_calculates_correctly(self):
        from app.api.v1.endpoints.alert_feedback import get_accuracy_metrics
        db = MagicMock()
        # 3 helpful, 2 false alarms = 60% precision
        risks = self._make_risks_with_feedback([True, True, True, False, False])
        db.query.return_value.filter.return_value.all.return_value = risks

        result = get_accuracy_metrics(db)
        assert result.true_positives == 3
        assert result.false_positives == 2
        assert result.precision == 60.0

    def test_needs_5_feedback_for_precision(self):
        from app.api.v1.endpoints.alert_feedback import get_accuracy_metrics
        db = MagicMock()
        # Only 4 feedback items — not enough
        risks = self._make_risks_with_feedback([True, True, True, True])
        db.query.return_value.filter.return_value.all.return_value = risks

        result = get_accuracy_metrics(db)
        assert result.precision is None

    def test_coverage_percentage_correct(self):
        from app.api.v1.endpoints.alert_feedback import get_accuracy_metrics
        db = MagicMock()
        # 10 total alerts, 5 with feedback = 50% coverage
        all_risks = []
        for i in range(10):
            r = MagicMock()
            r.risk_level = "high"
            if i < 5:
                r.signals_json = {"feedback": {"was_helpful": True}}
            else:
                r.signals_json = {}
            all_risks.append(r)
        db.query.return_value.filter.return_value.all.return_value = all_risks

        result = get_accuracy_metrics(db)
        assert result.total_alerts == 10
        assert result.feedback_received == 5
        assert result.feedback_coverage_pct == 50.0

    def test_excellent_precision_gives_positive_recommendation(self):
        from app.api.v1.endpoints.alert_feedback import get_accuracy_metrics
        db = MagicMock()
        risks = self._make_risks_with_feedback([True] * 10)
        db.query.return_value.filter.return_value.all.return_value = risks

        result = get_accuracy_metrics(db)
        assert "well" in result.interpretation.lower() or "excellent" in result.interpretation.lower()

    def test_poor_precision_gives_adjustment_recommendation(self):
        from app.api.v1.endpoints.alert_feedback import get_accuracy_metrics
        db = MagicMock()
        risks = self._make_risks_with_feedback([False] * 10)
        db.query.return_value.filter.return_value.all.return_value = risks

        result = get_accuracy_metrics(db)
        assert "false alarm" in result.interpretation.lower() or "alarm" in result.interpretation.lower()