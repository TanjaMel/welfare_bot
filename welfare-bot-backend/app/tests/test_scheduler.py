"""
Matches the actual implementation:
- AggregationPipeline(db) — db passed to constructor
- pipeline.run(target_date=target_date) — keyword arg, no db in run()
- backfill_missing_metrics() returns None (fire-and-forget)
- scheduler uses "daily_wellbeing_aggregation" job id
- start_scheduler() returns the scheduler instance
"""

import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch


def get_scheduler_module():
    from app.services import scheduler as sched_module
    return sched_module


class TestSchedulerLifecycle:

    def setup_method(self):
        mod = get_scheduler_module()
        mod.shutdown_scheduler()

    def teardown_method(self):
        mod = get_scheduler_module()
        mod.shutdown_scheduler()

    def test_start_scheduler_creates_daily_job(self):
        mod = get_scheduler_module()
        sched = mod.start_scheduler()
        assert sched is not None
        assert sched.running
        job = sched.get_job("daily_wellbeing_aggregation")
        assert job is not None

    def test_start_scheduler_idempotent(self):
        mod = get_scheduler_module()
        s1 = mod.start_scheduler()
        s2 = mod.start_scheduler()
        assert s1 is s2
        jobs = [j for j in s1.get_jobs() if j.id == "daily_wellbeing_aggregation"]
        assert len(jobs) == 1

    def test_shutdown_scheduler(self):
        mod = get_scheduler_module()
        mod.start_scheduler()
        mod.shutdown_scheduler()
        assert mod.scheduler is None

    def test_job_cron_fires_at_00_05(self):
        from apscheduler.triggers.cron import CronTrigger
        mod = get_scheduler_module()
        sched = mod.start_scheduler()
        job = sched.get_job("daily_wellbeing_aggregation")
        assert isinstance(job.trigger, CronTrigger)
        fields = {f.name: str(f) for f in job.trigger.fields}
        assert fields.get("hour") == "0"
        assert fields.get("minute") == "5"


class TestRunDailyAggregation:

    def test_run_daily_aggregation_calls_yesterday(self):
        mod = get_scheduler_module()
        yesterday = date.today() - timedelta(days=1)
        with patch.object(mod, "run_aggregation_for_date") as mock_run:
            mod.run_daily_aggregation()
        mock_run.assert_called_once_with(yesterday)

    def test_run_daily_aggregation_is_callable(self):
        mod = get_scheduler_module()
        assert callable(mod.run_daily_aggregation)


class TestRunAggregationForDate:

    def test_run_for_specific_date(self):
        mod = get_scheduler_module()
        target = date(2025, 3, 15)
        with patch("app.services.scheduler.SessionLocal") as mock_session_cls, \
             patch("app.services.scheduler.AggregationPipeline") as mock_pipeline_cls:
            mock_db = MagicMock()
            mock_session_cls.return_value = mock_db
            mock_pipeline = MagicMock()
            mock_pipeline_cls.return_value = mock_pipeline
            mod.run_aggregation_for_date(target)
        mock_pipeline_cls.assert_called_once_with(mock_db)
        mock_pipeline.run.assert_called_once_with(target_date=target)

    def test_commits_on_success(self):
        mod = get_scheduler_module()
        with patch("app.services.scheduler.SessionLocal") as mock_session_cls, \
             patch("app.services.scheduler.AggregationPipeline"):
            mock_db = MagicMock()
            mock_session_cls.return_value = mock_db
            mod.run_aggregation_for_date(date.today())
        mock_db.commit.assert_called_once()
        mock_db.rollback.assert_not_called()
        mock_db.close.assert_called_once()

    def test_rollbacks_on_error(self):
        mod = get_scheduler_module()
        with patch("app.services.scheduler.SessionLocal") as mock_session_cls, \
             patch("app.services.scheduler.AggregationPipeline") as mock_pipeline_cls:
            mock_db = MagicMock()
            mock_session_cls.return_value = mock_db
            mock_pipeline_cls.return_value.run.side_effect = RuntimeError("DB failure")
            with pytest.raises(RuntimeError):
                mod.run_aggregation_for_date(date.today())
        mock_db.rollback.assert_called_once()
        mock_db.commit.assert_not_called()
        mock_db.close.assert_called_once()

    def test_always_closes_session(self):
        mod = get_scheduler_module()
        with patch("app.services.scheduler.SessionLocal") as mock_session_cls, \
             patch("app.services.scheduler.AggregationPipeline") as mock_pipeline_cls:
            mock_db = MagicMock()
            mock_session_cls.return_value = mock_db
            mock_pipeline_cls.return_value.run.side_effect = ValueError("oops")
            with pytest.raises(ValueError):
                mod.run_aggregation_for_date(date.today())
        mock_db.close.assert_called_once()


class TestBackfill:

    def test_backfill_calls_run_for_each_day(self):
        mod = get_scheduler_module()
        with patch.object(mod, "run_aggregation_for_date") as mock_run:
            mod.backfill_missing_metrics(days=5)
        assert mock_run.call_count == 5

    def test_backfill_calls_correct_dates(self):
        mod = get_scheduler_module()
        today = date.today()
        expected = [today - timedelta(days=i) for i in range(1, 4)]
        with patch.object(mod, "run_aggregation_for_date") as mock_run:
            mod.backfill_missing_metrics(days=3)
        called = [c.args[0] for c in mock_run.call_args_list]
        assert called == expected

    def test_backfill_continues_on_single_day_error(self):
        mod = get_scheduler_module()
        call_count = 0
        def flaky(target_date):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("Day 2 failed")
        with patch.object(mod, "run_aggregation_for_date", side_effect=flaky):
            mod.backfill_missing_metrics(days=4)
        assert call_count == 4

    def test_backfill_returns_none(self):
        mod = get_scheduler_module()
        with patch.object(mod, "run_aggregation_for_date"):
            result = mod.backfill_missing_metrics(days=3)
        assert result is None