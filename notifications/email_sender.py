"""SMTP email sender (Gmail App Password friendly)."""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from config.settings import settings

logger = logging.getLogger(__name__)


def send_email(subject: str, body: str) -> bool:
    if not settings.email_enabled:
        logger.info("Email disabled; skipping")
        return False
    if not settings.smtp_user or not settings.smtp_password or not settings.email_to:
        logger.warning("SMTP credentials or recipient missing")
        return False

    msg = EmailMessage()
    msg["From"] = settings.smtp_user
    msg["To"] = settings.email_to
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
        logger.info(f"Email sent: {subject}")
        return True
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False


def format_decision_email(today_iso: str, action: str, orders: list[dict], nav: float, cash: float) -> tuple[str, str]:
    subject = f"[AI Portfolio] {today_iso} — {action} ({len(orders)} orders) | NAV ${nav:,.2f}"
    lines = [
        f"Date: {today_iso}",
        f"Action: {action}",
        f"NAV: ${nav:,.2f}   Cash: ${cash:,.2f}",
        "",
        "Orders:",
    ]
    if not orders:
        lines.append("  (no orders)")
    for o in orders:
        lines.append(
            f"  - {o.get('action')} {o.get('shares', 0):.4f} {o.get('ticker')} @ ${o.get('price', 0):.2f}  "
            f"= ${o.get('total_value', 0):,.2f}"
        )
    return subject, "\n".join(lines)
