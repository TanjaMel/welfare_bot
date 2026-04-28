"""
Covers:
- Daily score computation from check-in data
- Weight blending (check-in 70% + risk signal 30%)
- Edge cases: missing check-in, all-zero data, partial data
- Pre-aggregation stores exactly one row per user per day
- Idempotency: running the pipeline twice doesn't duplicate rows
"""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch, call


def get_pipeline():
    from app.services.aggregation_pipeline import AggregationPipeline
    return AggregationPipeline()

# Score computation unit tests


class TestScoreComputation:
    """
    Tests against the weight table from the README:
      mood        25%
      sleep       25%
      food        20%
      hydration   15%
      medication  10%
      social       5%
    Overall = checkin_composite * 0.70 + risk_signal_score * 0.30
    """

    def test_perfect_checkin_gives_high_score(self):
        pipeline = get_pipeline()
        score = pipeline.compute_daily_score(
            mood_rating=5,
            sleep_quality=5,
            meals_eaten=3,
            drank_enough_water=True,
            took_medication=True,
            message_count=10,
            avg_risk_score=0,
        )
        assert score >= 85, f"Perfect data should yield >=85, got {score}"

    def test_zero_checkin_gives_low_score(self):
        pipeline = get_pipeline()
        score = pipeline.compute_daily_score(
            mood_rating=1,
            sleep_quality=1,
            meals_eaten=0,
            drank_enough_water=False,
            took_medication=False,
            message_count=0,
            avg_risk_score=8,
        )
        assert score <= 30, f"Worst-case data should yield <=30, got {score}"

    def test_score_always_between_0_and_100(self):
        pipeline = get_pipeline()
        for mood in range(1, 6):
            for sleep in range(1, 6):
                score = pipeline.compute_daily_score(
                    mood_rating=mood,
                    sleep_quality=sleep,
                    meals_eaten=2,
                    drank_enough_water=True,
                    took_medication=True,
                    message_count=5,
                    avg_risk_score=2,
                )
                assert 0 <= score <= 100, (
                    f"Score out of range for mood={mood}, sleep={sleep}: {score}"
                )

    def test_high_risk_score_lowers_overall(self):
        pipeline = get_pipeline()
        low_risk = pipeline.compute_daily_score(
            mood_rating=4, sleep_quality=4, meals_eaten=3,
            drank_enough_water=True, took_medication=True,
            message_count=5, avg_risk_score=1,
        )
        high_risk = pipeline.compute_daily_score(
            mood_rating=4, sleep_quality=4, meals_eaten=3,
            drank_enough_water=True, took_medication=True,
            message_count=5, avg_risk_score=9,
        )
        assert low_risk > high_risk, (
            "High risk score should lower the overall daily score"
        )

    def test_no_medication_lowers_score(self):
        pipeline = get_pipeline()
        with_meds = pipeline.compute_daily_score(
            mood_rating=4, sleep_quality=4, meals_eaten=2,
            drank_enough_water=True, took_medication=True,
            message_count=5, avg_risk_score=2,
        )
        without_meds = pipeline.compute_daily_score(
            mood_rating=4, sleep_quality=4, meals_eaten=2,
            drank_enough_water=True, took_medication=False,
            message_count=5, avg_risk_score=2,
        )
        assert with_meds > without_meds

    def test_social_weight_is_minor(self):
        """5% weight — going from 0 to 20 messages should shift score modestly."""
        pipeline = get_pipeline()
        no_social = pipeline.compute_daily_score(
            mood_rating=3, sleep_quality=3, meals_eaten=2,
            drank_enough_water=True, took_medication=True,
            message_count=0, avg_risk_score=3,
        )
        very_social = pipeline.compute_daily_score(
            mood_rating=3, sleep_quality=3, meals_eaten=2,
            drank_enough_water=True, took_medication=True,
            message_count=20, avg_risk_score=3,
        )
        diff = abs(very_social - no_social)
        assert diff <= 10, (
            f"Social factor (5% weight) shouldn't shift score by more than 10 pts, "
            f"got {diff}"
        )

# Missing / partial data handling
class TestMissingData:

    def test_no_checkin_for_day_uses_defaults(self):
        """If no check-in exists for a user-day, pipeline should not crash."""
        pipeline = get_pipeline()
        score = pipeline.compute_daily_score(
            mood_rating=None,
            sleep_quality=None,
            meals_eaten=None,
            drank_enough_water=None,
            took_medication=None,
            message_count=0,
            avg_risk_score=0,
        )
        assert isinstance(score, (int, float))
        assert 0 <= score <= 100

    def test_no_risk_analyses_for_day(self):
        """If there are no risk analyses, avg_risk_score defaults to 0."""
        pipeline = get_pipeline()
        score = pipeline.compute_daily_score(
            mood_rating=3,
            sleep_quality=3,
            meals_eaten=2,
            drank_enough_water=True,
            took_medication=True,
            message_count=3,
            avg_risk_score=0,   # no analyses → treated as 0
        )
        assert isinstance(score, (int, float))

# Database-level pipeline run tests 


class TestPipelineRun:

    def test_run_creates_one_row_per_user(self):
        """
        Pipeline.run(session, target_date) should upsert exactly one
        wellbeing_daily_metrics row per active user.
        """
        pipeline = get_pipeline()
        mock_session = MagicMock()

        user_ids = [1, 2, 3]
        target_date = date.today() - timedelta(days=1)

        # Mock the query for active users
        mock_session.query.return_value.all.return_value = [
            MagicMock(id=uid) for uid in user_ids
        ]

        with patch.object(pipeline, "_fetch_user_ids", return_value=user_ids), \
             patch.object(pipeline, "_fetch_checkin", return_value=None), \
             patch.object(pipeline, "_fetch_avg_risk_score", return_value=2.0), \
             patch.object(pipeline, "_fetch_message_count", return_value=5), \
             patch.object(pipeline, "_upsert_metric") as mock_upsert:

            pipeline.run(mock_session, target_date)

        assert mock_upsert.call_count == len(user_ids), (
            f"Expected {len(user_ids)} upserts, got {mock_upsert.call_count}"
        )

    def test_run_is_idempotent(self):
        """
        Running the pipeline twice for the same date must not create
        duplicate rows — upsert (insert-or-update) semantics required.
        """
        pipeline = get_pipeline()
        mock_session = MagicMock()
        target_date = date.today() - timedelta(days=1)

        with patch.object(pipeline, "_fetch_user_ids", return_value=[1]), \
             patch.object(pipeline, "_fetch_checkin", return_value=None), \
             patch.object(pipeline, "_fetch_avg_risk_score", return_value=2.0), \
             patch.object(pipeline, "_fetch_message_count", return_value=3), \
             patch.object(pipeline, "_upsert_metric") as mock_upsert:

            pipeline.run(mock_session, target_date)
            pipeline.run(mock_session, target_date)

        # Both runs should call upsert — but the DB layer must handle conflicts.
        # Here we just assert it's called; the upsert SQL is tested separately.
        assert mock_upsert.call_count == 2

    def test_run_uses_yesterday_by_default(self):
        """When no target_date is supplied, pipeline should default to yesterday."""
        from datetime import date, timedelta
        pipeline = get_pipeline()

        with patch.object(pipeline, "_fetch_user_ids", return_value=[]), \
             patch.object(pipeline, "run", wraps=pipeline.run) as mock_run:

            pipeline.run_yesterday(MagicMock())
            # Verify target_date was yesterday
            called_date = mock_run.call_args[0][1]
            assert called_date == date.today() - timedelta(days=1)

# Output label tests — scores must map to soft human-readable labels


class TestOutputLabels:

    @pytest.mark.parametrize("score,expected_label_fragment", [
        (90, "great"),
        (70, "well"),
        (50, "okay"),
        (30, "concern"),
        (10, "concern"),
    ])
    def test_score_to_label(self, score, expected_label_fragment):
        """Human-readable label must never expose raw numbers to the user."""
        pipeline = get_pipeline()
        label = pipeline.score_to_label(score)
        assert expected_label_fragment.lower() in label.lower(), (
            f"Score {score} should produce a label containing "
            f"'{expected_label_fragment}', got '{label}'"
        )

    def test_label_is_always_soft_language(self):
        """No label should contain clinical terms or raw numbers."""
        pipeline = get_pipeline()
        clinical_terms = ["score", "metric", "risk", "0", "1", "2", "3", "4",
                          "5", "6", "7", "8", "9"]
        for score in range(0, 101, 10):
            label = pipeline.score_to_label(score)
            for term in clinical_terms:
                assert term not in label.lower(), (
                    f"Label for score {score} contains forbidden term '{term}': '{label}'"
                )