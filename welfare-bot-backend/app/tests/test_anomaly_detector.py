"""
Tests for app/services/anomaly_detector.py

Covers:
- Z-score computation
- Trend slope calculation
- Per-user anomaly detection
- Edge cases (no data, insufficient data, all None values)
"""

import pytest
import math
from datetime import date, timedelta
from unittest.mock import MagicMock


def get_ad():
    from app.services import anomaly_detector as ad
    return ad


def make_row(
    user_id=1,
    row_date=None,
    overall=70.0,
    mood=70.0,
    sleep=70.0,
    food=70.0,
    hydration=70.0,
    social=40.0,
):
    """Creates a mock WellbeingDailyMetrics row."""
    row = MagicMock()
    row.user_id = user_id
    row.date = row_date or date.today()
    row.overall_wellbeing_score = overall
    row.mood_score = mood
    row.sleep_score = sleep
    row.food_score = food
    row.hydration_score = hydration
    row.social_activity_score = social
    return row


def make_rows(n: int, overall=70.0, **kwargs) -> list:
    """Creates n rows with the given values, on consecutive dates."""
    today = date.today()
    return [
        make_row(
            row_date=today - timedelta(days=n - 1 - i),
            overall=overall,
            **kwargs,
        )
        for i in range(n)
    ]


def make_db(rows: list) -> MagicMock:
    """Creates a mock DB that returns the given rows."""
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = rows
    return db


# ─────────────────────────────────────────────────────────────────────────────
# Z-score helpers
# ─────────────────────────────────────────────────────────────────────────────

class TestComputeMeanStd:

    def test_basic_mean(self):
        """Mean of [60, 70, 80] should be 70."""
        ad = get_ad()
        mean, std = ad._compute_mean_std([60.0, 70.0, 80.0])
        assert mean == pytest.approx(70.0, abs=0.1)

    def test_basic_std(self):
        """Std of [70, 70, 70] should be near 0 (returns epsilon)."""
        ad = get_ad()
        mean, std = ad._compute_mean_std([70.0, 70.0, 70.0])
        assert std > 0  # should never return exactly 0

    def test_empty_list(self):
        """Empty list should return safe defaults (0.0, 1.0)."""
        ad = get_ad()
        mean, std = ad._compute_mean_std([])
        assert mean == 0.0
        assert std == 1.0


class TestComputeZScore:

    def test_value_at_mean_is_zero(self):
        """A value exactly at the mean should have Z-score of 0."""
        ad = get_ad()
        assert ad._compute_z_score(70.0, 70.0, 10.0) == pytest.approx(0.0)

    def test_one_std_above(self):
        """A value one std above the mean should have Z-score of 1.0."""
        ad = get_ad()
        assert ad._compute_z_score(80.0, 70.0, 10.0) == pytest.approx(1.0)

    def test_two_std_below(self):
        """A value two stds below the mean should have Z-score of -2.0."""
        ad = get_ad()
        assert ad._compute_z_score(50.0, 70.0, 10.0) == pytest.approx(-2.0)


class TestComputeTrendSlope:

    def test_flat_trend_is_zero(self):
        """All equal values should give a slope of 0."""
        ad = get_ad()
        slope = ad._compute_trend_slope([70.0] * 10)
        assert slope == pytest.approx(0.0, abs=0.1)

    def test_declining_trend_is_negative(self):
        """Values decreasing by 2 per day should give slope of -2."""
        ad = get_ad()
        values = [80.0, 78.0, 76.0, 74.0, 72.0]
        slope = ad._compute_trend_slope(values)
        assert slope == pytest.approx(-2.0, abs=0.1)

    def test_improving_trend_is_positive(self):
        """Values increasing by 2 per day should give slope of +2."""
        ad = get_ad()
        values = [60.0, 62.0, 64.0, 66.0, 68.0]
        slope = ad._compute_trend_slope(values)
        assert slope == pytest.approx(2.0, abs=0.1)

    def test_single_value_returns_zero(self):
        """Cannot compute slope from a single value."""
        ad = get_ad()
        slope = ad._compute_trend_slope([70.0])
        assert slope == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Per-user anomaly detection
# ─────────────────────────────────────────────────────────────────────────────

class TestDetectAnomaliesForUser:

    def test_insufficient_data_returns_safe_defaults(self):
        """
        With only 5 rows (below MIN_HISTORY_DAYS=7),
        the function should return is_flagged=False.
        """
        ad = get_ad()
        rows = make_rows(5)
        db = make_db(rows)
        result = ad.detect_anomalies_for_user(user_id=1, db=db)
        assert result.is_flagged is False
        assert result.trend_direction == "no_data"

    def test_stable_user_not_flagged(self):
        """
        A user with 30 days of stable scores around 70
        should not be flagged as anomalous.
        """
        ad = get_ad()
        rows = make_rows(30, overall=70.0, sleep=70.0, mood=70.0,
                         food=70.0, hydration=70.0, social=40.0)
        db = make_db(rows)
        result = ad.detect_anomalies_for_user(user_id=1, db=db)
        assert result.is_flagged is False

    def test_extreme_low_value_flagged(self):
        """
        A user whose last day has a score of 5 (far below their normal 70)
        should be flagged as anomalous.
        """
        ad = get_ad()
        today = date.today()
        # 29 days of normal scores
        rows = make_rows(29, overall=70.0, sleep=70.0)
        # Today: extreme drop to 5
        rows.append(make_row(
            row_date=today,
            overall=5.0,
            sleep=5.0,
            mood=5.0,
            food=5.0,
            hydration=5.0,
            social=5.0,
        ))
        db = make_db(rows)
        result = ad.detect_anomalies_for_user(user_id=1, db=db)
        assert result.is_flagged is True
        assert len(result.anomalous_metrics) > 0

    def test_result_has_required_fields(self):
        """Result should always have all required fields."""
        ad = get_ad()
        rows = make_rows(15)
        db = make_db(rows)
        result = ad.detect_anomalies_for_user(user_id=1, db=db)
        assert hasattr(result, "user_id")
        assert hasattr(result, "is_flagged")
        assert hasattr(result, "flag_reason")
        assert hasattr(result, "anomalous_metrics")
        assert hasattr(result, "trend_direction")
        assert hasattr(result, "trend_slope")

    def test_declining_trend_detected(self):
        """
        A user whose scores decline by 3 points per day over 20 days
        should have trend_direction='declining'.
        """
        ad = get_ad()
        today = date.today()
        rows = [
            make_row(
                row_date=today - timedelta(days=19 - i),
                overall=80.0 - (i * 3),  # 80, 77, 74, ... declining
            )
            for i in range(20)
        ]
        db = make_db(rows)
        result = ad.detect_anomalies_for_user(user_id=1, db=db)
        assert result.trend_direction == "declining"
        assert result.trend_slope < 0

    def test_improving_trend_detected(self):
        """
        A user whose scores increase by 2 points per day
        should have trend_direction='improving'.
        """
        ad = get_ad()
        today = date.today()
        rows = [
            make_row(
                row_date=today - timedelta(days=19 - i),
                overall=40.0 + (i * 2),  # 40, 42, 44, ... improving
            )
            for i in range(20)
        ]
        db = make_db(rows)
        result = ad.detect_anomalies_for_user(user_id=1, db=db)
        assert result.trend_direction == "improving"
        assert result.trend_slope > 0

    def test_anomaly_direction_is_low(self):
        """
        When today's value is far below normal,
        the anomaly direction should be 'low'.
        """
        ad = get_ad()
        today = date.today()
        rows = make_rows(29, overall=70.0, sleep=70.0)
        rows.append(make_row(row_date=today, overall=10.0, sleep=10.0))
        db = make_db(rows)
        result = ad.detect_anomalies_for_user(user_id=1, db=db)
        if result.metric_anomalies:
            directions = [a.direction for a in result.metric_anomalies]
            assert "low" in directions

    def test_flag_reason_is_string(self):
        """flag_reason should always be a non-empty string."""
        ad = get_ad()
        rows = make_rows(20)
        db = make_db(rows)
        result = ad.detect_anomalies_for_user(user_id=1, db=db)
        assert isinstance(result.flag_reason, str)
        assert len(result.flag_reason) > 0

    def test_days_of_history_correct(self):
        """days_of_history should match the number of rows returned."""
        ad = get_ad()
        rows = make_rows(20)
        db = make_db(rows)
        result = ad.detect_anomalies_for_user(user_id=1, db=db)
        assert result.days_of_history == 20

    def test_z_threshold_used_in_result(self):
        """The z_threshold_used field should match what was passed in."""
        ad = get_ad()
        rows = make_rows(15)
        db = make_db(rows)
        result = ad.detect_anomalies_for_user(user_id=1, db=db, z_threshold=3.0)
        assert result.z_threshold_used == 3.0