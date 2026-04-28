from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler

from app.db.session import SessionLocal
from app.services.aggregation_pipeline import AggregationPipeline

scheduler: Optional[BackgroundScheduler] = None


def start_scheduler() -> BackgroundScheduler:
    global scheduler

    if scheduler is not None and scheduler.running:
        return scheduler

    scheduler = BackgroundScheduler(timezone="UTC")

    scheduler.add_job(
        run_daily_aggregation,
        trigger="cron",
        hour=0,
        minute=5,
        id="daily_wellbeing_aggregation",
        replace_existing=True,
    )

    scheduler.start()
    return scheduler


def shutdown_scheduler() -> None:
    global scheduler

    if scheduler is not None and scheduler.running:
        scheduler.shutdown(wait=False)

    scheduler = None


def run_daily_aggregation() -> None:
    target_date = date.today() - timedelta(days=1)
    run_aggregation_for_date(target_date)


def run_aggregation_for_date(target_date: date) -> None:
    db = SessionLocal()

    try:
        pipeline = AggregationPipeline(db)
        pipeline.run(target_date=target_date)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def backfill_missing_metrics(days: int = 7) -> None:
    for offset in range(1, days + 1):
        target_date = date.today() - timedelta(days=offset)

        try:
            run_aggregation_for_date(target_date)
        except Exception:
            continue