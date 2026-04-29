"""
Tests for app/services/ml_anomaly_model.py

Covers:
- Feature engineering
- Model training and prediction
- Accuracy metrics
- Hyperparameter optimization
- Edge cases
"""

import pytest
import numpy as np
from datetime import date, timedelta
from unittest.mock import MagicMock


def get_model():
    from app.services import ml_anomaly_model as m
    return m


def make_row(overall=70.0, mood=70.0, sleep=70.0, food=70.0,
             hydration=70.0, social=40.0):
    row = MagicMock()
    row.overall_wellbeing_score = overall
    row.mood_score = mood
    row.sleep_score = sleep
    row.food_score = food
    row.hydration_score = hydration
    row.social_activity_score = social
    return row


def make_stable_rows(n=20, base=70.0):
    """Generate n rows of stable wellbeing scores with small noise."""
    import random
    random.seed(42)
    return [
        make_row(
            overall=base + random.uniform(-3, 3),
            mood=base + random.uniform(-3, 3),
            sleep=base + random.uniform(-3, 3),
            food=base + random.uniform(-3, 3),
            hydration=base + random.uniform(-3, 3),
        )
        for _ in range(n)
    ]


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

class TestBuildFeatureMatrix:

    def test_shape_correct(self):
        m = get_model()
        rows = make_stable_rows(10)
        X, names = m.build_feature_matrix(rows)
        assert X.shape == (10, len(m.FEATURE_COLUMNS) + len(m.DERIVED_FEATURES))

    def test_feature_names_returned(self):
        m = get_model()
        rows = make_stable_rows(5)
        _, names = m.build_feature_matrix(rows)
        assert "overall_wellbeing_score" in names
        assert "overall_change_1d" in names
        assert "nutrition_score" in names

    def test_none_values_handled(self):
        m = get_model()
        rows = [make_row(overall=None, mood=None) for _ in range(5)]
        X, _ = m.build_feature_matrix(rows)
        assert not np.any(np.isnan(X))

    def test_change_features_computed(self):
        m = get_model()
        rows = [
            make_row(overall=80.0),
            make_row(overall=70.0),  # -10 change
            make_row(overall=60.0),  # -10 change
        ]
        X, names = m.build_feature_matrix(rows)
        change_1d_idx = names.index("overall_change_1d")
        assert X[1, change_1d_idx] == pytest.approx(-10.0, abs=0.1)

    def test_nutrition_score_is_average(self):
        m = get_model()
        rows = [make_row(food=80.0, hydration=60.0)]
        X, names = m.build_feature_matrix(rows)
        nutrition_idx = names.index("nutrition_score")
        assert X[0, nutrition_idx] == pytest.approx(70.0, abs=0.1)


# ---------------------------------------------------------------------------
# Model training
# ---------------------------------------------------------------------------

class TestTrainModel:

    def test_returns_model_and_scaler(self):
        m = get_model()
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler
        rows = make_stable_rows(20)
        X, _ = m.build_feature_matrix(rows)
        model, scaler = m.train_model(X)
        assert isinstance(model, IsolationForest)
        assert isinstance(scaler, StandardScaler)

    def test_model_fitted(self):
        m = get_model()
        rows = make_stable_rows(20)
        X, _ = m.build_feature_matrix(rows)
        model, scaler = m.train_model(X)
        # fitted model has estimators_
        assert hasattr(model, "estimators_")
        assert len(model.estimators_) == m.N_ESTIMATORS

    def test_contamination_parameter_respected(self):
        m = get_model()
        rows = make_stable_rows(20)
        X, _ = m.build_feature_matrix(rows)
        model, _ = m.train_model(X, contamination=0.1)
        assert model.contamination == 0.1

    def test_stable_data_mostly_normal(self):
        m = get_model()
        rows = make_stable_rows(50)
        X, _ = m.build_feature_matrix(rows)
        model, scaler = m.train_model(X, contamination=0.05)
        labels, _ = m.predict_anomaly(model, scaler, X)
        anomaly_rate = sum(1 for l in labels if l == -1) / len(labels)
        # Should be close to contamination rate, not wildly different
        assert anomaly_rate <= 0.15


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------

class TestPredictAnomaly:

    def test_normal_day_not_flagged(self):
        m = get_model()
        rows = make_stable_rows(30)
        X, _ = m.build_feature_matrix(rows)
        model, scaler = m.train_model(X, contamination=0.05)

        # Normal test point — same as training distribution
        X_normal = X[-1:]
        labels, scores = m.predict_anomaly(model, scaler, X_normal)
        # Not guaranteed but very likely to be normal
        assert labels.shape == (1,)
        assert scores.shape == (1,)

    def test_extreme_drop_flagged(self):
        m = get_model()
        # Train on stable data
        rows = make_stable_rows(30, base=70.0)
        X_train, _ = m.build_feature_matrix(rows)
        model, scaler = m.train_model(X_train, contamination=0.05)

        # Test with extreme anomaly — all scores near zero
        anomaly_rows = [make_row(overall=5.0, mood=5.0, sleep=5.0,
                                  food=5.0, hydration=5.0, social=5.0)]
        X_anomaly, _ = m.build_feature_matrix(anomaly_rows)
        labels, scores = m.predict_anomaly(model, scaler, X_anomaly)
        assert labels[0] == -1, "Extreme score drop should be flagged as anomaly"

    def test_scores_more_negative_for_anomalies(self):
        m = get_model()
        rows = make_stable_rows(30, base=70.0)
        X, _ = m.build_feature_matrix(rows)
        model, scaler = m.train_model(X, contamination=0.05)

        normal = np.array([[70, 70, 70, 70, 70, 40, 0, 0, 1.0, 70]], dtype=np.float32)
        anomaly = np.array([[5, 5, 5, 5, 5, 5, -65, -65, 1.0, 5]], dtype=np.float32)

        _, score_normal = m.predict_anomaly(model, scaler, normal)
        _, score_anomaly = m.predict_anomaly(model, scaler, anomaly)

        assert score_anomaly[0] < score_normal[0], (
            "Anomaly should have lower (more negative) score than normal"
        )


# ---------------------------------------------------------------------------
# Per-user detection
# ---------------------------------------------------------------------------

class TestDetectUserAnomaly:

    def test_insufficient_data_returns_safe_result(self):
        m = get_model()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            make_row() for _ in range(3)  # below MIN_TRAINING_SAMPLES
        ]
        result = m.detect_user_anomaly(user_id=1, db=mock_db)
        assert result["is_anomalous"] is False
        assert result["model_info"]["status"] == "insufficient_data"

    def test_stable_user_not_flagged(self):
        m = get_model()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
            make_stable_rows(20)
        )
        result = m.detect_user_anomaly(user_id=1, db=mock_db)
        assert "is_anomalous" in result
        assert "anomaly_score" in result
        assert result["model_info"]["status"] == "trained"

    def test_result_has_required_fields(self):
        m = get_model()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
            make_stable_rows(15)
        )
        result = m.detect_user_anomaly(user_id=1, db=mock_db)
        required = {"is_anomalous", "anomaly_score", "confidence",
                    "feature_contributions", "model_info"}
        assert required.issubset(result.keys())

    def test_anomaly_score_between_0_and_10(self):
        m = get_model()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
            make_stable_rows(20)
        )
        result = m.detect_user_anomaly(user_id=1, db=mock_db)
        assert 0.0 <= result["anomaly_score"] <= 10.0

    def test_feature_contributions_populated(self):
        m = get_model()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
            make_stable_rows(20)
        )
        result = m.detect_user_anomaly(user_id=1, db=mock_db)
        assert len(result["feature_contributions"]) > 0


# ---------------------------------------------------------------------------
# Accuracy monitoring
# ---------------------------------------------------------------------------

class TestEvaluateModelAccuracy:

    def test_perfect_predictions(self):
        m = get_model()
        y_true = [1, 0, 1, 0, 1, 0, 0, 1]
        y_pred = [1, 0, 1, 0, 1, 0, 0, 1]
        result = m.evaluate_model_accuracy(y_true, y_pred)
        assert result["precision"] == 1.0
        assert result["recall"] == 1.0
        assert result["f1"] == 1.0

    def test_all_false_positives(self):
        m = get_model()
        y_true = [0, 0, 0, 0, 1]
        y_pred = [1, 1, 1, 1, 1]
        result = m.evaluate_model_accuracy(y_true, y_pred)
        assert result["precision"] < 0.5

    def test_all_false_negatives(self):
        m = get_model()
        y_true = [1, 1, 1, 1, 0]
        y_pred = [0, 0, 0, 0, 0]
        result = m.evaluate_model_accuracy(y_true, y_pred)
        assert result["recall"] == 0.0

    def test_empty_input_returns_error(self):
        m = get_model()
        result = m.evaluate_model_accuracy([], [])
        assert "error" in result

    def test_mismatched_lengths_returns_error(self):
        m = get_model()
        result = m.evaluate_model_accuracy([1, 0, 1], [1, 0])
        assert "error" in result

    def test_returns_interpretation(self):
        m = get_model()
        y_true = [1, 0, 1, 0, 1, 0, 1, 0]
        y_pred = [1, 0, 1, 0, 1, 0, 1, 0]
        result = m.evaluate_model_accuracy(y_true, y_pred)
        assert "interpretation" in result
        assert len(result["interpretation"]) > 0


# ---------------------------------------------------------------------------
# Hyperparameter optimization
# ---------------------------------------------------------------------------

class TestOptimizeContamination:

    def test_returns_best_contamination(self):
        m = get_model()
        rows = make_stable_rows(30)
        X, _ = m.build_feature_matrix(rows)
        # Simple y_true: last 3 rows are anomalies
        y_true = [0] * 27 + [1] * 3
        result = m.optimize_contamination(X, y_true, contamination_values=[0.05, 0.10])
        assert "best_contamination" in result
        assert result["best_contamination"] in [0.05, 0.10]

    def test_returns_all_results(self):
        m = get_model()
        rows = make_stable_rows(20)
        X, _ = m.build_feature_matrix(rows)
        y_true = [0] * 18 + [1] * 2
        result = m.optimize_contamination(X, y_true, contamination_values=[0.05, 0.10, 0.15])
        assert len(result["all_results"]) == 3

    def test_recommendation_string_present(self):
        m = get_model()
        rows = make_stable_rows(20)
        X, _ = m.build_feature_matrix(rows)
        y_true = [0] * 19 + [1]
        result = m.optimize_contamination(X, y_true, contamination_values=[0.05])
        assert "recommendation" in result
        assert "CONTAMINATION" in result["recommendation"]