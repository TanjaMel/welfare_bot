from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler

from app.db.session import SessionLocal
from app.services.aggregation_pipeline import AggregationPipeline

logger = logging.getLogger(__name__)

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

    scheduler.add_job(
        send_pending_notifications,
        trigger="interval",
        minutes=5,
        id="send_pending_notifications",
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


def send_pending_notifications() -> None:
    """
    Process all pending notifications in the queue.
    Runs every 5 minutes — sends email alerts for HIGH/CRITICAL risk.
    """
    try:
        from app.db.models.notification import Notification
        from app.services.notification_service import send_notification_from_queue

        db = SessionLocal()
        try:
            pending = (
                db.query(Notification)
                .filter(Notification.status == "pending")
                .limit(20)
                .all()
            )

            if not pending:
                return

            logger.info("Processing %d pending notifications", len(pending))

            for notif in pending:
                try:
                    send_notification_from_queue(notif.id, db)
                except Exception as e:
                    logger.error(
                        "Failed to send notification %d: %s", notif.id, e
                    )
        finally:
            db.close()

    except Exception as e:
        logger.error("Notification job failed: %s", e)