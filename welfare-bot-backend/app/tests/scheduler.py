"""
Midnight aggregation scheduler using APScheduler (in-process).
Runs the wellbeing metrics pipeline every day at 00:05 server time
so all of yesterday's data is fully written before the job fires.

Setup
-----
Call `start_scheduler()` once from app/main.py lifespan:

    from app.services.scheduler import start_scheduler, shutdown_scheduler
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        start_scheduler()
        yield
        shutdown_scheduler()

    app = FastAPI(lifespan=lifespan)
"""

import logging
from datetime import date, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

logger = logging.getLogger(__name__)

# Module-level singleton — only one scheduler per process
_scheduler: BackgroundScheduler | None = None

# Job function

def run_daily_aggregation() -> None:
    """
    Compute and upsert wellbeing_daily_metrics for yesterday.

    Called automatically by APScheduler at 00:05 every day.
    Can also be called manually for backfill (see `run_aggregation_for_date`).
    """
    from app.db.session import SessionLocal          # adjust to your session factory
    from app.services.aggregation_pipeline import AggregationPipeline

    yesterday = date.today() - timedelta(days=1)
    logger.info("Aggregation pipeline starting for %s", yesterday)

    db = SessionLocal()
    try:
        pipeline = AggregationPipeline()
        stats = pipeline.run(db, yesterday)
        db.commit()
        logger.info(
            "Aggregation pipeline completed for %s — %d users processed",
            yesterday,
            stats.get("users_processed", 0),
        )
    except Exception as exc:
        db.rollback()
        logger.exception("Aggregation pipeline FAILED for %s: %s", yesterday, exc)
        raise
    finally:
        db.close()


def run_aggregation_for_date(target_date: date) -> dict:
    """
    Manually trigger the aggregation pipeline for a specific date.
    Useful for backfilling missing rows.

    Usage:
        from app.services.scheduler import run_aggregation_for_date
        run_aggregation_for_date(date(2025, 6, 1))
    """
    from app.db.session import SessionLocal
    from app.services.aggregation_pipeline import AggregationPipeline

    logger.info("Manual aggregation triggered for %s", target_date)

    db = SessionLocal()
    try:
        pipeline = AggregationPipeline()
        stats = pipeline.run(db, target_date)
        db.commit()
        logger.info("Manual aggregation completed for %s: %s", target_date, stats)
        return stats
    except Exception as exc:
        db.rollback()
        logger.exception("Manual aggregation FAILED for %s: %s", target_date, exc)
        raise
    finally:
        db.close()

# Backfill utility

def backfill_missing_metrics(days: int = 30) -> dict:
    """
    Re-run the aggregation pipeline for the last N days.
    Safe to run multiple times — the pipeline uses upsert semantics.

    Returns a summary dict: {date_str: users_processed}.
    """
    from app.db.session import SessionLocal
    from app.services.aggregation_pipeline import AggregationPipeline

    results = {}
    db = SessionLocal()
    try:
        pipeline = AggregationPipeline()
        for offset in range(1, days + 1):
            target = date.today() - timedelta(days=offset)
            try:
                stats = pipeline.run(db, target)
                db.commit()
                results[str(target)] = stats.get("users_processed", 0)
                logger.info("Backfill OK for %s", target)
            except Exception as exc:
                db.rollback()
                logger.error("Backfill FAILED for %s: %s", target, exc)
                results[str(target)] = "ERROR"
    finally:
        db.close()

    logger.info("Backfill complete: %s", results)
    return results


# Scheduler lifecycle

def _on_job_executed(event) -> None:
    if event.exception:
        logger.error("Scheduled job '%s' raised an exception", event.job_id)
    else:
        logger.info("Scheduled job '%s' completed successfully", event.job_id)


def start_scheduler() -> None:
    """
    Start the background scheduler with the daily aggregation job.
    Safe to call multiple times — will not create duplicate schedulers.
    """
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        logger.warning("Scheduler is already running — skipping start_scheduler()")
        return

    _scheduler = BackgroundScheduler(
        job_defaults={
            "coalesce": True,        # If multiple misfires queue up, run once
            "max_instances": 1,      # Never run the same job concurrently
            "misfire_grace_time": 3600,  # Run up to 1h late if the server was down
        }
    )

    # Register event listeners
    _scheduler.add_listener(_on_job_executed, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    # Daily aggregation — fires at 00:05 every day (server local time)
    _scheduler.add_job(
        run_daily_aggregation,
        trigger=CronTrigger(hour=0, minute=5),
        id="daily_aggregation",
        name="Wellbeing daily metrics aggregation",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(
        "Scheduler started. Next run: %s",
        _scheduler.get_job("daily_aggregation").next_run_time,
    )


def shutdown_scheduler() -> None:
    """Gracefully shut down the scheduler on app teardown."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down.")
    _scheduler = None


def get_scheduler() -> BackgroundScheduler | None:
    """Return the active scheduler instance (for inspection / testing)."""
    return _scheduler