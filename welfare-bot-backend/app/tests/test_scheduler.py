"""
Covers:
- Scheduler starts and registers the daily job
- Job fires the aggregation pipeline with yesterday's date
- Scheduler is idempotent (double start doesn't duplicate jobs)
- Backfill utility calls the pipeline for each requested day
- Graceful shutdown
"""

import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch, call


def get_scheduler_module():
    from app.services import scheduler as sched_module
    return sched_module

# Scheduler lifecycle

class TestSchedulerLifecycle:

    def setup_method(self):
        """Ensure scheduler is stopped before each test."""
        mod = get_scheduler_module()
        mod.shutdown_scheduler()

    def teardown_method(self):
        """Clean up after each test."""
        mod = get_scheduler_module()
        mod.shutdown_scheduler()

    def test_start_scheduler_creates_daily_job(self):
        mod = get_scheduler_module()
        mod.start_scheduler()
        scheduler = mod.get_scheduler()

        assert scheduler is not None
        assert scheduler.running
        job = scheduler.get_job("daily_aggregation")
        assert job is not None, "daily_aggregation job must be registered"

    def test_start_scheduler_idempotent(self):
        """Calling start_scheduler twice must not duplicate the job."""
        mod = get_scheduler_module()
        mod.start_scheduler()
        mod.start_scheduler()  # second call — should be a no-op

        scheduler = mod.get_scheduler()
        jobs = [j for j in scheduler.get_jobs() if j.id == "daily_aggregation"]
        assert len(jobs) == 1, f"Expected 1 job, found {len(jobs)}"

    def test_shutdown_scheduler(self):
        mod = get_scheduler_module()
        mod.start_scheduler()
        mod.shutdown_scheduler()

        scheduler = mod.get_scheduler()
        assert scheduler is None or not scheduler.running

    def test_job_cron_fires_at_00_05(self):
        """Verify the trigger is set to 00:05."""
        from apscheduler.triggers.cron import CronTrigger
        mod = get_scheduler_module()
        mod.start_scheduler()
        scheduler = mod.get_scheduler()
        job = scheduler.get_job("daily_aggregation")

        trigger = job.trigger
        assert isinstance(trigger, CronTrigger)
        # CronTrigger fields are stored as field objects; check their expressions
        fields = {f.name: str(f) for f in trigger.fields}
        assert fields.get("hour") == "0", f"Expected hour=0, got {fields.get('hour')}"
        assert fields.get("minute") == "5", f"Expected minute=5, got {fields.get('minute')}"


# Job function

class TestRunDailyAggregation:

    def test_run_daily_aggregation_uses_yesterday(self):
        """The job should always pass yesterday's date to the pipeline."""
        mod = get_scheduler_module()
        yesterday = date.today() - timedelta(days=1)

        with patch("app.services.scheduler.SessionLocal") as mock_session_cls, \
             patch("app.services.scheduler.AggregationPipeline") as mock_pipeline_cls:

            mock_db = MagicMock()
            mock_session_cls.return_value = mock_db
            mock_pipeline = MagicMock()
            mock_pipeline.run.return_value = {"users_processed": 3}
            mock_pipeline_cls.return_value = mock_pipeline

            mod.run_daily_aggregation()

        mock_pipeline.run.assert_called_once_with(mock_db, yesterday)

    def test_run_daily_aggregation_commits_on_success(self):
        mod = get_scheduler_module()

        with patch("app.services.scheduler.SessionLocal") as mock_session_cls, \
             patch("app.services.scheduler.AggregationPipeline") as mock_pipeline_cls:

            mock_db = MagicMock()
            mock_session_cls.return_value = mock_db
            mock_pipeline_cls.return_value.run.return_value = {"users_processed": 1}

            mod.run_daily_aggregation()

        mock_db.commit.assert_called_once()
        mock_db.rollback.assert_not_called()

    def test_run_daily_aggregation_rollbacks_on_error(self):
        mod = get_scheduler_module()

        with patch("app.services.scheduler.SessionLocal") as mock_session_cls, \
             patch("app.services.scheduler.AggregationPipeline") as mock_pipeline_cls:

            mock_db = MagicMock()
            mock_session_cls.return_value = mock_db
            mock_pipeline_cls.return_value.run.side_effect = RuntimeError("DB failure")

            with pytest.raises(RuntimeError):
                mod.run_daily_aggregation()

        mock_db.rollback.assert_called_once()
        mock_db.commit.assert_not_called()

    def test_run_daily_aggregation_always_closes_session(self):
        """DB session must be closed even when an exception occurs."""
        mod = get_scheduler_module()

        with patch("app.services.scheduler.SessionLocal") as mock_session_cls, \
             patch("app.services.scheduler.AggregationPipeline") as mock_pipeline_cls:

            mock_db = MagicMock()
            mock_session_cls.return_value = mock_db
            mock_pipeline_cls.return_value.run.side_effect = ValueError("oops")

            with pytest.raises(ValueError):
                mod.run_daily_aggregation()

        mock_db.close.assert_called_once()


# Manual trigger

class TestRunAggregationForDate:

    def test_run_for_specific_date(self):
        mod = get_scheduler_module()
        target = date(2025, 3, 15)

        with patch("app.services.scheduler.SessionLocal") as mock_session_cls, \
             patch("app.services.scheduler.AggregationPipeline") as mock_pipeline_cls:

            mock_db = MagicMock()
            mock_session_cls.return_value = mock_db
            mock_pipeline = MagicMock()
            mock_pipeline.run.return_value = {"users_processed": 5}
            mock_pipeline_cls.return_value = mock_pipeline

            result = mod.run_aggregation_for_date(target)

        mock_pipeline.run.assert_called_once_with(mock_db, target)
        assert result["users_processed"] == 5

# Backfill utility


class TestBackfill:

    def test_backfill_calls_pipeline_for_each_day(self):
        mod = get_scheduler_module()

        with patch("app.services.scheduler.SessionLocal") as mock_session_cls, \
             patch("app.services.scheduler.AggregationPipeline") as mock_pipeline_cls:

            mock_db = MagicMock()
            mock_session_cls.return_value = mock_db
            mock_pipeline = MagicMock()
            mock_pipeline.run.return_value = {"users_processed": 2}
            mock_pipeline_cls.return_value = mock_pipeline

            results = mod.backfill_missing_metrics(days=7)

        assert mock_pipeline.run.call_count == 7
        assert len(results) == 7

    def test_backfill_continues_on_single_day_error(self):
        """One failing day must not abort the whole backfill."""
        mod = get_scheduler_module()

        call_count = 0

        def flaky_run(db, target_date):
            nonlocal call_count
            call_count += 1
            if call_count == 3:
                raise RuntimeError("Simulated failure on day 3")
            return {"users_processed": 1}

        with patch("app.services.scheduler.SessionLocal") as mock_session_cls, \
             patch("app.services.scheduler.AggregationPipeline") as mock_pipeline_cls:

            mock_db = MagicMock()
            mock_session_cls.return_value = mock_db
            mock_pipeline = MagicMock()
            mock_pipeline.run.side_effect = flaky_run
            mock_pipeline_cls.return_value = mock_pipeline

            results = mod.backfill_missing_metrics(days=5)

        # All 5 days should have a result (some may be "ERROR")
        assert len(results) == 5
        error_days = [k for k, v in results.items() if v == "ERROR"]
        assert len(error_days) == 1, f"Expected 1 error day, got {error_days}"