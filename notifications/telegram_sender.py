"""Telegram bot notification (optional)."""
from __future__ import annotations

import logging

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)


def send_telegram(text: str) -> bool:
    if not settings.telegram_enabled:
        return False
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("Telegram credentials missing")
        return False

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    try:
        r = httpx.post(
            url,
            data={
                "chat_id": settings.telegram_chat_id,
                "text": text[:4000],
                "parse_mode": "HTML",
                "disable_web_page_preview": "true",
            },
            timeout=15.0,
        )
        r.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        return False


def format_candidates_block(candidates: list[dict]) -> str:
    """Format buy candidates for display in notifications."""
    if not candidates:
        return "No immediate buy candidates. Market conditions do not justify entry yet."
    lines = ["<b>Buy Candidates (monitor for entry):</b>"]
    for c in candidates[:5]:  # Limit to top 5
        ticker = c.get("ticker", "?")
        thesis = c.get("thesis", "")[:100]  # Truncate thesis to 100 chars
        trigger = c.get("trigger", "")[:100]
        risk = c.get("risk_level", "?")
        conf = int(c.get("confidence", 0) * 100)
        lines.append(f"• <b>{ticker}</b> — {thesis} (risk: {risk.upper()}, {conf}% confidence)")
        if trigger:
            lines.append(f"  Entry: {trigger}")
    return "\n".join(lines)


def format_decision_telegram(today_iso: str, action: str, orders: list[dict], nav: float, candidates: list[dict] | None = None) -> str:
    lines = [f"<b>AI Portfolio — {today_iso}</b>", f"Action: <b>{action}</b>", f"NAV: ${nav:,.2f}"]
    if orders:
        lines.append("\n<b>Orders:</b>")
        for o in orders:
            lines.append(
                f"• {o.get('action')} {o.get('shares', 0):.4f} {o.get('ticker')} "
                f"@ ${o.get('price', 0):.2f}"
            )
    if candidates is None:
        candidates = []
    lines.append(f"\n{format_candidates_block(candidates)}")
    return "\n".join(lines)
