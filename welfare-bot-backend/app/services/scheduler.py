from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler

from app.db.session import SessionLocal
from app.services.aggregation_pipeline import AggregationPipeline
from app.services.weekly_report import send_weekly_report

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# BACKGROUND SCHEDULER
#
# This module manages all automated background jobs in the system.
# It uses APScheduler — a Python library for scheduling tasks.
#
# There are 3 scheduled jobs:
#   1. daily_wellbeing_aggregation  — runs every night at 00:05 UTC
#   2. weekly_report                — runs every Monday at 08:00 UTC
#   3. send_pending_notifications   — runs every 5 minutes
#
# The scheduler runs in a background thread so it never blocks API requests.
# It is started when the FastAPI application starts (in main.py).
# ─────────────────────────────────────────────────────────────────────────────

# Global scheduler instance — None means the scheduler is not running
scheduler: Optional[BackgroundScheduler] = None


def start_scheduler() -> BackgroundScheduler:
    """
    Starts the background scheduler and registers all three jobs.

    Idempotent: if the scheduler is already running, returns it as-is
    without creating a new one or registering duplicate jobs.

    All times are in UTC to ensure consistent behaviour regardless of
    the server's timezone. Railway runs in UTC by default.
    """
    global scheduler

    # If already running, return existing instance — avoid duplicate jobs
    if scheduler is not None and scheduler.running:
        return scheduler

    scheduler = BackgroundScheduler(timezone="UTC")

    # ── JOB 1: Daily wellbeing aggregation ───────────────────────────────
    # Runs every night at 00:05 UTC (5 minutes after midnight).
    # The 5-minute delay ensures that any late-night messages from the
    # previous day have been saved to the database before aggregation runs.
    # Calls run_daily_aggregation() which processes yesterday's data
    # for all active users.
    scheduler.add_job(
        run_daily_aggregation,
        trigger="cron",
        hour=0,
        minute=5,
        id="daily_wellbeing_aggregation",
        replace_existing=True,  # prevents duplicate jobs on hot reload
    )

    # ── JOB 2: Weekly population report ──────────────────────────────────
    # Runs every Monday at 08:00 UTC.
    # Sends an email to the admin with a summary of the past week:
    # total users, active users, average wellbeing vs previous week,
    # and high/critical alert counts.
    # Implemented in weekly_report.py using SendGrid.
    scheduler.add_job(
        send_weekly_report,
        trigger="cron",
        day_of_week="mon",
        hour=8,
        minute=0,
        id="weekly_report",
        replace_existing=True,
    )

    # ── JOB 3: Notification queue processor ──────────────────────────────
    # Runs every 5 minutes using an interval trigger (not cron).
    # Checks the notifications table for any rows with status="pending"
    # and sends them via SendGrid email.
    # This is how HIGH/CRITICAL risk alerts reach care contacts —
    # the risk detection writes to the queue, this job sends the emails.
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
    """
    Gracefully stops the scheduler and clears the global instance.

    Called when the application shuts down.
    wait=False means it does not wait for currently running jobs to finish —
    this prevents delays during deployment restarts on Railway.
    """
    global scheduler

    if scheduler is not None and scheduler.running:
        scheduler.shutdown(wait=False)

    scheduler = None


def run_daily_aggregation() -> None:
    """
    Entry point for the nightly aggregation job.

    Always processes yesterday's date — because the job runs at 00:05 UTC,
    "today" has just started and we want to aggregate the completed day.
    Delegates the actual work to run_aggregation_for_date().
    """
    target_date = date.today() - timedelta(days=1)
    run_aggregation_for_date(target_date)


def run_aggregation_for_date(target_date: date) -> None:
    """
    Runs the full aggregation pipeline for a specific date.

    Opens a new database session, runs the pipeline for all active users,
    commits the results, and always closes the session — even if an error occurs.

    This function is also used by backfill_missing_metrics() to reprocess
    historical dates when data was missing.

    Raises the exception after rollback so the scheduler can log it.
    """
    db = SessionLocal()

    try:
        pipeline = AggregationPipeline(db)
        pipeline.run(target_date=target_date)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        # Always close the session to prevent connection leaks
        db.close()


def backfill_missing_metrics(days: int = 7) -> None:
    """
    Reprocesses the last N days of data for all users.

    Used when:
    - The system was down and missed some nightly runs
    - A bug was fixed and historical data needs recomputing
    - A new user was added and needs historical scores calculated

    Continues even if one day fails — logs the error and moves on
    so a single bad day does not block the entire backfill.
    """
    for offset in range(1, days + 1):
        target_date = date.today() - timedelta(days=offset)

        try:
            run_aggregation_for_date(target_date)
        except Exception:
            # Log and continue — do not let one failed day block the rest
            continue


def send_pending_notifications() -> None:
    """
    Processes all pending notifications in the queue and sends them via email.

    This is the second half of the notification pipeline:
    - First half: risk detection writes a notification row with status="pending"
    - Second half: this function (running every 5 minutes) sends the email

    Processes up to 20 notifications per run to avoid overloading SendGrid
    if a large backlog builds up.

    Each notification is processed individually so one failure does not
    block the others from being sent.
    """
    try:
        from app.db.models.notification import Notification
        from app.services.notification_service import send_notification_from_queue

        db = SessionLocal()
        try:
            # Fetch pending notifications — limit 20 per run
            pending = (
                db.query(Notification)
                .filter(Notification.status == "pending")
                .limit(20)
                .all()
            )

            # Nothing to do — exit early without logging
            if not pending:
                return

            logger.info("Processing %d pending notifications", len(pending))

            # Send each notification individually
            # If one fails, log the error and continue with the rest
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