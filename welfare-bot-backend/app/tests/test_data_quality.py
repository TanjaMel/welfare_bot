"""
Tests for app/services/data_quality.py

Covers:
- Missing value detection
- Outlier detection
- Gap detection
- Quality scoring
- Repair utilities
- Population report

Each test class focuses on one function from data_quality.py.
Tests use mock objects instead of a real database so they run
fast and without any database connection.
"""

import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock


def get_dq():
    """Helper to import the data_quality module in each test."""
    from app.services import data_quality as dq
    return dq


def make_row(
    user_id=1,
    row_date=None,
    overall=70.0,
    mood=70.0,
    sleep=70.0,
    food=70.0,
    hydration=70.0,
    medication=None,    # None by default — medication is often legitimately absent
    social=40.0,
    risk=2.0,
):
    """
    Creates a mock WellbeingDailyMetrics row with default healthy values.
    Override any field to test specific scenarios.
    """
    row = MagicMock()
    row.user_id = user_id
    row.date = row_date or date.today()
    row.overall_wellbeing_score = overall
    row.mood_score = mood
    row.sleep_score = sleep
    row.food_score = food
    row.hydration_score = hydration
    row.medication_score = medication
    row.social_activity_score = social
    row.risk_score = risk
    return row


def make_rows_for_dates(start_date, n_days, **kwargs):
    """Creates n_days consecutive rows starting from start_date."""
    return [
        make_row(row_date=start_date + timedelta(days=i), **kwargs)
        for i in range(n_days)
    ]


# ---------------------------------------------------------------------------
# Metric quality checks — tests for _check_metric_quality()
# ---------------------------------------------------------------------------

class TestCheckMetricQuality:

    def test_perfect_data_high_score(self):
        """All 10 rows have valid values — quality score should be 90+."""
        dq = get_dq()
        rows = [make_row(overall=70.0) for _ in range(10)]
        result = dq._check_metric_quality(rows, "overall_wellbeing_score")
        assert result.missing_count == 0
        assert result.missing_rate == 0.0
        assert result.outlier_count == 0
        assert result.quality_score >= 90.0

    def test_all_missing_zero_score(self):
        """All values are None — quality should be near 0."""
        dq = get_dq()
        rows = [make_row(overall=None) for _ in range(10)]
        result = dq._check_metric_quality(rows, "overall_wellbeing_score")
        assert result.missing_count == 10
        assert result.missing_rate == 1.0
        assert result.quality_score < 10.0

    def test_outlier_detected(self):
        """One value is 150 — above the 100 maximum — should be flagged."""
        dq = get_dq()
        rows = [make_row(overall=70.0)] * 9 + [make_row(overall=150.0)]
        result = dq._check_metric_quality(rows, "overall_wellbeing_score")
        assert result.outlier_count == 1
        assert result.max_value == 150.0

    def test_negative_value_is_outlier(self):
        """Negative values are below the 0 minimum — should be flagged as outlier."""
        dq = get_dq()
        rows = [make_row(overall=-5.0)]
        result = dq._check_metric_quality(rows, "overall_wellbeing_score")
        assert result.outlier_count == 1

    def test_empty_rows_returns_zero_quality(self):
        """No rows at all — should return quality score of 0."""
        dq = get_dq()
        result = dq._check_metric_quality([], "overall_wellbeing_score")
        assert result.total_rows == 0
        assert result.quality_score == 0.0

    def test_partial_missing(self):
        """7 rows have values, 3 are None — missing rate should be 0.3."""
        dq = get_dq()
        rows = [make_row(overall=70.0)] * 7 + [make_row(overall=None)] * 3
        result = dq._check_metric_quality(rows, "overall_wellbeing_score")
        assert result.missing_count == 3
        assert abs(result.missing_rate - 0.3) < 0.01

    def test_mean_computed_correctly(self):
        """Two values: 60 and 80 — mean should be 70."""
        dq = get_dq()
        rows = [make_row(overall=60.0), make_row(overall=80.0)]
        result = dq._check_metric_quality(rows, "overall_wellbeing_score")
        assert result.mean_value == pytest.approx(70.0, abs=0.1)


# ---------------------------------------------------------------------------
# Gap detection — tests for _detect_gaps()
# ---------------------------------------------------------------------------

class TestDetectGaps:

    def test_no_gaps_when_all_days_present(self):
        """7 consecutive days of data — no concerning gaps expected."""
        dq = get_dq()
        today = date.today()
        start = today - timedelta(days=6)
        rows = make_rows_for_dates(start, 7)
        gaps = dq._detect_gaps(rows, start, today)
        concerning = [g for g in gaps if g.is_concerning]
        assert len(concerning) == 0

    def test_single_day_gap_not_concerning(self):
        """One day missing — gap of 1 day is below GAP_THRESHOLD_DAYS=2, not concerning."""
        dq = get_dq()
        today = date.today()
        start = today - timedelta(days=6)
        # Skip day 3 by creating rows for days 0-2 and 4-6
        rows = make_rows_for_dates(start, 3) + make_rows_for_dates(start + timedelta(days=4), 3)
        gaps = dq._detect_gaps(rows, start, today)
        one_day_gaps = [g for g in gaps if g.gap_days == 1]
        assert len(one_day_gaps) > 0
        assert not one_day_gaps[0].is_concerning

    def test_long_gap_is_concerning(self):
        """Only first 3 and last 3 days have data — 8 day gap in the middle is concerning."""
        dq = get_dq()
        today = date.today()
        start = today - timedelta(days=13)
        rows = (
            make_rows_for_dates(start, 3)
            + make_rows_for_dates(today - timedelta(days=2), 3)
        )
        gaps = dq._detect_gaps(rows, start, today)
        concerning = [g for g in gaps if g.is_concerning]
        assert len(concerning) > 0
        assert max(g.gap_days for g in concerning) >= dq.GAP_THRESHOLD_DAYS

    def test_no_rows_returns_single_full_gap(self):
        """No data at all — the entire 7-day period should be one large gap."""
        dq = get_dq()
        today = date.today()
        start = today - timedelta(days=6)
        gaps = dq._detect_gaps([], start, today)
        assert len(gaps) == 1
        assert gaps[0].gap_days == 7
        assert gaps[0].is_concerning is True


# ---------------------------------------------------------------------------
# User data quality report — tests for check_user_data_quality()
# ---------------------------------------------------------------------------

class TestCheckUserDataQuality:

    def _make_db_mock(self, rows):
        """Creates a mock database that returns the given rows."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = rows
        return mock_db

    def test_perfect_data_high_quality_score(self):
        """30 days of complete data — quality score should be above 50."""
        dq = get_dq()
        today = date.today()
        start = today - timedelta(days=29)
        rows = make_rows_for_dates(start, 30)
        db = self._make_db_mock(rows)
        result = dq.check_user_data_quality(user_id=1, db=db)
        assert result.overall_quality_score > 50.0
        assert result.coverage_rate == pytest.approx(1.0, abs=0.01)

    def test_no_data_low_quality_score(self):
        """No rows at all — coverage should be 0 and quality should be very low."""
        dq = get_dq()
        db = self._make_db_mock([])
        result = dq.check_user_data_quality(user_id=1, db=db)
        assert result.total_days_present == 0
        assert result.coverage_rate == 0.0
        assert result.overall_quality_score < 10.0

    def test_result_has_required_fields(self):
        """Result should always have all required fields regardless of data."""
        dq = get_dq()
        db = self._make_db_mock([make_row()])
        result = dq.check_user_data_quality(user_id=1, db=db)
        assert hasattr(result, "user_id")
        assert hasattr(result, "overall_quality_score")
        assert hasattr(result, "metric_quality")
        assert hasattr(result, "gaps")
        assert hasattr(result, "issues")
        assert hasattr(result, "suggestions")

    def test_outlier_triggers_issue(self):
        """A value of 150 is an outlier — should appear in issues list."""
        dq = get_dq()
        rows = [make_row(overall=150.0)]
        db = self._make_db_mock(rows)
        result = dq.check_user_data_quality(user_id=1, db=db)
        assert len(result.issues) > 0
        assert any("outlier" in issue.lower() for issue in result.issues)

    def test_large_gap_triggers_issue(self):
        """Only last 3 days have data — 27-day gap should appear in issues list."""
        dq = get_dq()
        today = date.today()
        rows = make_rows_for_dates(today - timedelta(days=2), 3)
        db = self._make_db_mock(rows)
        result = dq.check_user_data_quality(user_id=1, db=db)
        assert any("gap" in issue.lower() for issue in result.issues)

    def test_needs_attention_set_for_bad_data(self):
        """No data at all should trigger needs_attention=True."""
        dq = get_dq()
        db = self._make_db_mock([])
        result = dq.check_user_data_quality(user_id=1, db=db)
        assert result.needs_attention is True

    def test_metric_quality_list_populated(self):
        """Result should have one MetricQuality entry per metric column."""
        dq = get_dq()
        rows = [make_row()]
        db = self._make_db_mock(rows)
        result = dq.check_user_data_quality(user_id=1, db=db)
        assert len(result.metric_quality) == len(dq.METRIC_COLUMNS)

    def test_coverage_rate_correct(self):
        """15 out of 30 days have data — coverage rate should be ~0.5."""
        dq = get_dq()
        today = date.today()
        start = today - timedelta(days=29)
        rows = make_rows_for_dates(start, 15)
        db = self._make_db_mock(rows)
        result = dq.check_user_data_quality(user_id=1, db=db, lookback_days=30)
        assert result.coverage_rate == pytest.approx(0.5, abs=0.05)


# ---------------------------------------------------------------------------
# Repair utilities — tests for repair_outliers()
# ---------------------------------------------------------------------------

class TestRepairOutliers:

    def test_dry_run_does_not_modify(self):
        """
        In dry_run mode, the function should report the outlier
        but NOT change the value or commit to the database.
        """
        dq = get_dq()
        rows = [make_row(overall=150.0)]
        mock_db = MagicMock()
        result = dq.repair_outliers(rows, mock_db, dry_run=True)
        assert result["mode"] == "dry_run"
        assert result["rows_affected"] == 1
        mock_db.commit.assert_not_called()  # database must NOT be touched
        assert rows[0].overall_wellbeing_score == 150.0  # value must NOT change

    def test_repair_mode_clamps_outliers(self):
        """
        In repair mode (dry_run=False), the function should
        fix the value and commit to the database.
        """
        dq = get_dq()
        row = make_row(overall=150.0)
        mock_db = MagicMock()
        result = dq.repair_outliers([row], mock_db, dry_run=False)
        assert result["mode"] == "repaired"
        mock_db.commit.assert_called_once()  # database MUST be committed

    def test_no_outliers_no_repairs(self):
        """All values within 0–100 — nothing to repair."""
        dq = get_dq()
        rows = [make_row(overall=70.0) for _ in range(5)]
        mock_db = MagicMock()
        result = dq.repair_outliers(rows, mock_db, dry_run=True)
        assert result["rows_affected"] == 0
        assert result["total_values_fixed"] == 0

    def test_negative_outlier_clamped_to_zero(self):
        """A value of -10 should be clamped to 0.0 (the minimum)."""
        dq = get_dq()
        row = make_row(overall=-10.0)
        mock_db = MagicMock()
        result = dq.repair_outliers([row], mock_db, dry_run=True)
        assert result["details"][0]["repairs"][0]["repaired"] == 0.0

    def test_high_outlier_clamped_to_100(self):
        """A value of 200 should be clamped to 100.0 (the maximum)."""
        dq = get_dq()
        row = make_row(overall=200.0)
        mock_db = MagicMock()
        result = dq.repair_outliers([row], mock_db, dry_run=True)
        assert result["details"][0]["repairs"][0]["repaired"] == 100.0


# ---------------------------------------------------------------------------
# Population quality report — tests for run_population_quality_check()
# ---------------------------------------------------------------------------

class TestRunPopulationQualityCheck:

    def test_returns_population_quality(self):
        """Should return a PopulationDataQuality object with required fields."""
        dq = get_dq()
        mock_db = MagicMock()
        mock_user = MagicMock(id=1, first_name="Test", last_name="User", is_active=True)
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_user]
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        result = dq.run_population_quality_check(mock_db)
        assert hasattr(result, "total_users")
        assert hasattr(result, "avg_quality_score")
        assert hasattr(result, "user_reports")

    def test_empty_users_returns_zero_scores(self):
        """No active users — all counts and scores should be zero."""
        dq = get_dq()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        result = dq.run_population_quality_check(mock_db)
        assert result.total_users == 0
        assert result.avg_quality_score == 0.0

    def test_user_reports_sorted_by_quality(self):
        """
        User reports should be sorted by quality score ascending
        so the worst-quality users appear first in the list.
        This makes it easier for care workers to see who needs attention.
        """
        dq = get_dq()
        mock_db = MagicMock()
        users = [
            MagicMock(id=i, first_name=f"User{i}", last_name="", is_active=True)
            for i in range(1, 4)
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = users
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        result = dq.run_population_quality_check(mock_db)
        scores = [r["quality_score"] for r in result.user_reports]
        assert scores == sorted(scores), "Reports should be sorted by quality score ascending"