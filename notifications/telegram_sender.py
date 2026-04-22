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


def format_watchlist_block(watchlist: list[dict]) -> str:
    """Format watchlist items for Telegram."""
    if not watchlist:
        return "No immediate watchlist setups. No valid entry conditions identified."
    lines = ["<b>Watchlist (near-entry setups):</b>"]
    for w in watchlist[:5]:
        ticker = w.get("ticker", "?")
        setup = w.get("setup", "")[:80]
        trigger = w.get("trigger", "")[:80]
        lines.append(f"• <b>{ticker}</b> — {setup}")
        if trigger:
            lines.append(f"  Trigger: {trigger}")
    return "\n".join(lines)


def format_decision_telegram(today_iso: str, action: str, orders: list[dict], nav: float, watchlist: list[dict] | None = None) -> str:
    lines = [f"<b>AI Portfolio — {today_iso}</b>", f"Action: <b>{action}</b>", f"NAV: ${nav:,.2f}"]
    if orders:
        lines.append("\n<b>Positions Entered:</b>")
        for o in orders:
            lines.append(
                f"• {o.get('action')} {o.get('shares', 0):.4f} {o.get('ticker')} "
                f"@ ${o.get('price', 0):.2f}"
            )
    if watchlist is None:
        watchlist = []
    lines.append(f"\n{format_watchlist_block(watchlist)}")
    return "\n".join(lines)
