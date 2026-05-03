"""
app/services/notification_service.py

Sends email notifications via SendGrid for HIGH and CRITICAL risk alerts.
Also handles password reset emails.

Environment variables required:
    SENDGRID_API_KEY     — SendGrid API key (starts with SG.)
    SENDGRID_FROM_EMAIL  — Verified sender email address
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "noreply@welfarebot.com")


def _get_client():
    """Return SendGrid client or None if not configured."""
    if not SENDGRID_API_KEY:
        logger.warning("SENDGRID_API_KEY not set — email notifications disabled")
        return None
    try:
        from sendgrid import SendGridAPIClient
        return SendGridAPIClient(SENDGRID_API_KEY)
    except ImportError:
        logger.error("sendgrid package not installed")
        return None


def send_risk_alert_email(
    to_email: str,
    user_name: str,
    risk_level: str,
    suggested_action: str,
    reason: Optional[str] = None,
) -> bool:
    """
    Send a risk alert email to a care contact or admin.
    Called when risk level is HIGH or CRITICAL.
    Returns True if sent successfully, False otherwise.
    """
    client = _get_client()
    if not client:
        return False

    subject_map = {
        "critical": f"URGENT: {user_name} needs immediate attention",
        "high": f"Alert: {user_name} may need support today",
        "medium": f"Notice: {user_name} — follow-up recommended",
    }

    subject = subject_map.get(risk_level.lower(), f"Welfare Bot alert for {user_name}")

    reason_block = f"<p><strong>Details:</strong> {reason}</p>" if reason else ""

    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px;">
        <div style="background: #f8fafc; border-radius: 12px; padding: 24px; border: 1px solid #e2e8f0;">
            <h2 style="color: #1e293b; margin: 0 0 16px;">Welfare Bot Alert</h2>

            <div style="background: {'#fef2f2' if risk_level == 'critical' else '#fff7ed'};
                        border-left: 4px solid {'#dc2626' if risk_level == 'critical' else '#ea580c'};
                        padding: 16px; border-radius: 6px; margin-bottom: 20px;">
                <p style="margin: 0; font-weight: 600; color: {'#991b1b' if risk_level == 'critical' else '#9a3412'};">
                    Risk level: {risk_level.upper()}
                </p>
            </div>

            <p><strong>User:</strong> {user_name}</p>
            {reason_block}
            <p><strong>Recommended action:</strong> {suggested_action}</p>

            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">

            <p style="font-size: 13px; color: #64748b;">
                This is an automated alert from Welfare Bot. Please do not reply to this email.
                Contact the user directly or through your care system.
            </p>
            <p style="font-size: 12px; color: #94a3b8;">
                Welfare Bot — Care. Support. Well-being.
            </p>
        </div>
    </div>
    """

    text_content = (
        f"Welfare Bot Alert\n\n"
        f"User: {user_name}\n"
        f"Risk level: {risk_level.upper()}\n"
        f"Reason: {reason or 'See system for details'}\n"
        f"Recommended action: {suggested_action}\n\n"
        f"This is an automated alert from Welfare Bot."
    )

    try:
        from sendgrid.helpers.mail import Mail
        message = Mail(
            from_email=SENDGRID_FROM_EMAIL,
            to_emails=to_email,
            subject=subject,
            html_content=html_content,
            plain_text_content=text_content,
        )
        response = client.send(message)
        if response.status_code in (200, 202):
            logger.info(
                "Risk alert email sent to %s for user %s (risk: %s)",
                to_email, user_name, risk_level,
            )
            return True
        else:
            logger.warning(
                "SendGrid returned status %d for alert to %s",
                response.status_code, to_email,
            )
            return False
    except Exception as e:
        logger.error("Failed to send risk alert email: %s", e)
        return False


def send_password_reset_email(
    to_email: str,
    reset_token: str,
    user_name: str = "",
) -> bool:
    """
    Send a password reset email with a reset link.
    Returns True if sent successfully, False otherwise.
    """
    client = _get_client()
    if not client:
        return False

    # Build reset URL — uses Railway live URL or localhost for dev
    base_url = os.getenv("APP_URL", "https://welfarebot-production.up.railway.app")
    reset_url = f"{base_url}/reset-password?token={reset_token}"

    greeting = f"Hello {user_name}," if user_name else "Hello,"

    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px;">
        <div style="background: #f8fafc; border-radius: 12px; padding: 24px; border: 1px solid #e2e8f0;">
            <h2 style="color: #1e293b; margin: 0 0 16px;">Password Reset</h2>
            <p>{greeting}</p>
            <p>You requested a password reset for your Welfare Bot account.</p>
            <p>Click the button below to set a new password. This link expires in 1 hour.</p>

            <div style="text-align: center; margin: 28px 0;">
                <a href="{reset_url}"
                   style="background: #4F7DF3; color: white; padding: 12px 28px;
                          border-radius: 8px; text-decoration: none; font-weight: 600;
                          display: inline-block;">
                    Reset Password
                </a>
            </div>

            <p style="font-size: 13px; color: #64748b;">
                If you did not request this, you can safely ignore this email.
                Your password will not change.
            </p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
            <p style="font-size: 12px; color: #94a3b8;">
                Welfare Bot — Care. Support. Well-being.
            </p>
        </div>
    </div>
    """

    text_content = (
        f"{greeting}\n\n"
        f"You requested a password reset for your Welfare Bot account.\n\n"
        f"Reset link (expires in 1 hour):\n{reset_url}\n\n"
        f"If you did not request this, ignore this email."
    )

    try:
        from sendgrid.helpers.mail import Mail
        message = Mail(
            from_email=SENDGRID_FROM_EMAIL,
            to_emails=to_email,
            subject="Reset your Welfare Bot password",
            html_content=html_content,
            plain_text_content=text_content,
        )
        response = client.send(message)
        if response.status_code in (200, 202):
            logger.info("Password reset email sent to %s", to_email)
            return True
        else:
            logger.warning(
                "SendGrid returned status %d for password reset to %s",
                response.status_code, to_email,
            )
            return False
    except Exception as e:
        logger.error("Failed to send password reset email: %s", e)
        return False


def send_notification_from_queue(
    notification_id: int,
    db,
) -> bool:
    """
    Process a single pending notification from the queue.
    Updates notification status in DB after sending.
    """
    try:
        from app.db.models.notification import Notification
        from app.db.models.user import User
        from app.db.models.care_contact import CareContact

        notif = db.query(Notification).filter(Notification.id == notification_id).first()
        if not notif:
            logger.warning("Notification %d not found", notification_id)
            return False

        if notif.status != "pending":
            return False

        user = db.query(User).filter(User.id == notif.user_id).first()
        if not user:
            logger.warning("User %d not found for notification %d", notif.user_id, notification_id)
            return False

        user_name = f"{user.first_name} {user.last_name}".strip() or f"User {user.id}"

        # Find care contact email
        care_contact = (
            db.query(CareContact)
            .filter(CareContact.user_id == notif.user_id)
            .first()
        )

        # Determine recipient — care contact first, then admin email
        admin_email = os.getenv("ADMIN_EMAIL")
        to_email = None

        if care_contact and care_contact.email:
            to_email = care_contact.email
        elif admin_email:
            to_email = admin_email

        if not to_email:
            logger.warning(
                "No recipient email for notification %d — no care contact or admin email",
                notification_id,
            )
            notif.status = "failed"
            db.commit()
            return False

        # Parse risk level from message
        risk_level = "high"
        if "critical" in notif.message.lower():
            risk_level = "critical"

        success = send_risk_alert_email(
            to_email=to_email,
            user_name=user_name,
            risk_level=risk_level,
            suggested_action=notif.message,
        )

        notif.status = "sent" if success else "failed"
        db.commit()
        return success

    except Exception as e:
        logger.error("Error processing notification %d: %s", notification_id, e)
        return False