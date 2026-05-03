"""
Weekly trend report — sent every Monday morning via SendGrid.
Add to scheduler.py:
    from app.services.weekly_report import send_weekly_report
    scheduler.add_job(send_weekly_report, trigger="cron", day_of_week="mon", hour=8, minute=0)
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)


def send_weekly_report() -> None:
    """
    Send weekly population summary to admin email every Monday at 8:00 UTC.
    """
    try:
        from app.db.session import SessionLocal
        from app.db.models.user import User
        from app.db.models.conversation_message import ConversationMessage
        from app.db.models.risk_analysis import RiskAnalysis
        from app.db.models.wellbeing_daily_metrics import WellbeingDailyMetrics
        from sqlalchemy import func

        db = SessionLocal()
        try:
            today = date.today()
            week_start = today - timedelta(days=7)
            week_start_dt = datetime.combine(week_start, datetime.min.time())

            # Population
            users = db.query(User).filter(
                User.is_active == True,
                User.role != "admin"
            ).all()
            total_users = len(users)
            user_ids = [u.id for u in users]

            if not user_ids:
                return

            # Active users this week
            active_ids = set(
                row[0] for row in
                db.query(ConversationMessage.user_id)
                .filter(
                    ConversationMessage.user_id.in_(user_ids),
                    ConversationMessage.created_at >= week_start_dt,
                )
                .distinct()
                .all()
            )

            # Risk counts this week
            risk_rows = (
                db.query(RiskAnalysis.risk_level, func.count(RiskAnalysis.id))
                .filter(
                    RiskAnalysis.user_id.in_(user_ids),
                    RiskAnalysis.created_at >= week_start_dt,
                )
                .group_by(RiskAnalysis.risk_level)
                .all()
            )
            risk_counts = {level: count for level, count in risk_rows}

            # Avg wellbeing this week vs previous week
            avg_this_week = (
                db.query(func.avg(WellbeingDailyMetrics.overall_wellbeing_score))
                .filter(
                    WellbeingDailyMetrics.user_id.in_(user_ids),
                    WellbeingDailyMetrics.date >= week_start,
                )
                .scalar()
            )
            avg_prev_week = (
                db.query(func.avg(WellbeingDailyMetrics.overall_wellbeing_score))
                .filter(
                    WellbeingDailyMetrics.user_id.in_(user_ids),
                    WellbeingDailyMetrics.date >= week_start - timedelta(days=7),
                    WellbeingDailyMetrics.date < week_start,
                )
                .scalar()
            )

            # Build report
            avg_str = f"{round(float(avg_this_week), 1)}%" if avg_this_week else "No data"
            trend_str = ""
            if avg_this_week and avg_prev_week:
                diff = float(avg_this_week) - float(avg_prev_week)
                if diff > 2:
                    trend_str = f" (↑ up {round(diff, 1)}% from last week)"
                elif diff < -2:
                    trend_str = f" (↓ down {round(abs(diff), 1)}% from last week)"
                else:
                    trend_str = " (→ stable vs last week)"

            critical = risk_counts.get("critical", 0)
            high = risk_counts.get("high", 0)

            subject = f"Welfare Bot — Weekly Report {today.strftime('%d %b %Y')}"

            html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px;">
                <div style="background: #f8fafc; border-radius: 12px; padding: 24px; border: 1px solid #e2e8f0;">
                    <h2 style="color: #1e293b; margin: 0 0 4px;">Weekly Population Report</h2>
                    <p style="color: #64748b; margin: 0 0 20px;">Week of {week_start.strftime('%d %b')} — {today.strftime('%d %b %Y')}</p>

                    <div style="display: grid; gap: 12px; margin-bottom: 20px;">
                        <div style="background: #fff; padding: 16px; border-radius: 8px; border: 1px solid #e2e8f0;">
                            <div style="font-size: 13px; color: #64748b;">Total users</div>
                            <div style="font-size: 24px; font-weight: 700; color: #1e293b;">{total_users}</div>
                            <div style="font-size: 12px; color: #94a3b8;">{len(active_ids)} active this week</div>
                        </div>
                        <div style="background: #fff; padding: 16px; border-radius: 8px; border: 1px solid #e2e8f0;">
                            <div style="font-size: 13px; color: #64748b;">Average wellbeing score</div>
                            <div style="font-size: 24px; font-weight: 700; color: #16a34a;">{avg_str}{trend_str}</div>
                        </div>
                        <div style="background: {'#fef2f2' if critical > 0 else '#fff'}; padding: 16px; border-radius: 8px; border: 1px solid {'#fca5a5' if critical > 0 else '#e2e8f0'};">
                            <div style="font-size: 13px; color: #64748b;">High/Critical alerts this week</div>
                            <div style="font-size: 24px; font-weight: 700; color: {'#dc2626' if (critical + high) > 0 else '#16a34a'};">
                                {critical + high}
                            </div>
                            <div style="font-size: 12px; color: #94a3b8;">{critical} critical, {high} high</div>
                        </div>
                    </div>

                    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
                    <p style="font-size: 13px; color: #64748b;">
                        View full details at your admin dashboard.
                    </p>
                    <p style="font-size: 12px; color: #94a3b8;">Welfare Bot — Care. Support. Well-being.</p>
                </div>
            </div>
            """

            text = (
                f"Welfare Bot Weekly Report — {today.strftime('%d %b %Y')}\n\n"
                f"Total users: {total_users} ({len(active_ids)} active this week)\n"
                f"Average wellbeing: {avg_str}{trend_str}\n"
                f"High/Critical alerts: {critical + high} ({critical} critical, {high} high)\n"
            )

            # Send via SendGrid
            from app.services.notification_service import _get_client, SENDGRID_FROM_EMAIL
            from sendgrid.helpers.mail import Mail

            admin_email = os.getenv("ADMIN_EMAIL")
            if not admin_email:
                logger.warning("ADMIN_EMAIL not set — weekly report not sent")
                return

            client = _get_client()
            if not client:
                return

            message = Mail(
                from_email=SENDGRID_FROM_EMAIL,
                to_emails=admin_email,
                subject=subject,
                html_content=html,
                plain_text_content=text,
            )
            response = client.send(message)
            if response.status_code in (200, 202):
                logger.info("Weekly report sent to %s", admin_email)
            else:
                logger.warning("Weekly report SendGrid status: %d", response.status_code)

        finally:
            db.close()

    except Exception as e:
        logger.error("Weekly report failed: %s", e)