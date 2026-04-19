"""Two-way Telegram bot for remote portfolio control.

Uses Application.context.bot_data and asyncio within the app's event loop.
Only responds to messages from the configured TELEGRAM_CHAT_ID.

Commands:
  /help       — list commands
  /status     — NAV, cash, return %, open positions count
  /positions  — each open position with unrealized P&L
  /decision   — last Claude decision with reasoning
  /run        — trigger today's job (trading-day gated)
"""
from __future__ import annotations

import asyncio
import logging
import threading

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, ExtBot

from db.database import SessionLocal
from db.models import DailyDecision, Position
from portfolio.state import STARTING_CAPITAL, load_portfolio_state
from scheduler.jobs import daily_job, _is_trading_day, _today_et

logger = logging.getLogger(__name__)

_app_task: threading.Thread | None = None


def _authorized(update: Update, chat_id: str) -> bool:
    """Only respond to the configured chat."""
    return str(update.effective_chat.id) == str(chat_id)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update, context.bot_data["chat_id"]):
        return
    text = (
        "<b>AI Portfolio Bot</b>\n\n"
        "/status — NAV, cash, return\n"
        "/positions — open positions + P&amp;L\n"
        "/decision — last Claude decision\n"
        "/run — trigger today's job (trading days only)\n"
        "/help — this message"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update, context.bot_data["chat_id"]):
        return
    db = SessionLocal()
    try:
        state = load_portfolio_state(db)
        total_return = (state.total_nav / STARTING_CAPITAL - 1) * 100.0
        text = (
            f"<b>Portfolio Status</b>\n\n"
            f"NAV: <b>${state.total_nav:,.2f}</b>\n"
            f"Cash: ${state.cash:,.2f} ({state.cash_pct:.1f}%)\n"
            f"Invested: ${state.invested_value:,.2f} ({state.invested_pct:.1f}%)\n"
            f"Total return: <b>{total_return:+.2f}%</b>\n"
            f"Open positions: {len(state.positions)}"
        )
    finally:
        db.close()
    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_positions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update, context.bot_data["chat_id"]):
        return
    db = SessionLocal()
    try:
        positions = db.query(Position).filter(Position.is_open.is_(True)).all()
        if not positions:
            await update.message.reply_text("No open positions.")
            return
        lines = ["<b>Open Positions</b>\n"]
        for p in positions:
            pnl_sign = "+" if p.unrealized_pnl >= 0 else ""
            stop_info = f"  🔴 Stop active @ {p.trailing_stop_pct:.0f}%" if p.trailing_stop_active else ""
            lines.append(
                f"<b>{p.ticker}</b> ({p.asset_type})\n"
                f"  {p.shares:.4f} sh · entry ${p.entry_price:.2f} · now ${p.current_price:.2f}\n"
                f"  P&amp;L: {pnl_sign}${p.unrealized_pnl:.2f} ({pnl_sign}{p.unrealized_pnl_pct:.1f}%)"
                f"{stop_info}"
            )
        await update.message.reply_text("\n\n".join(lines), parse_mode="HTML")
    finally:
        db.close()


async def cmd_decision(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update, context.bot_data["chat_id"]):
        return
    db = SessionLocal()
    try:
        d = db.query(DailyDecision).order_by(DailyDecision.decision_date.desc()).first()
        if not d:
            await update.message.reply_text("No decisions recorded yet.")
            return
        action_emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}.get(d.action, "")
        text = (
            f"<b>Last Decision — {d.decision_date}</b>\n\n"
            f"{action_emoji} <b>{d.action}</b>  conf {d.confidence:.2f}  signals {d.signals_active}/4\n\n"
            f"<b>Assessment:</b>\n{d.market_assessment}\n\n"
            f"<b>Notes:</b>\n{(d.notes or '')[:600]}"
        )
    finally:
        db.close()
    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update, context.bot_data["chat_id"]):
        return

    today = _today_et()
    if not _is_trading_day(today):
        await update.message.reply_text(
            f"⛔ Not a trading day ({today}). The job only runs on NYSE market days."
        )
        return

    await update.message.reply_text(
        "⏳ Starting daily job… This takes 3–5 minutes. I'll message you when it's done."
    )

    async def _run_and_notify() -> None:
        try:
            result = await asyncio.to_thread(daily_job)
            if result.get("skipped"):
                msg = f"⚠️ Job skipped: {result.get('reason')}"
            elif result.get("error"):
                msg = f"❌ Job failed: {result['error']}"
            else:
                msg = (
                    f"✅ <b>Done — {result['date']}</b>\n"
                    f"Action: <b>{result['action']}</b>\n"
                    f"Orders applied: {result['orders_applied']}\n"
                    f"NAV: ${result['nav']:,.2f}  Cash: ${result['cash']:,.2f}"
                )
            await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode="HTML")
        except Exception as e:
            logger.exception(f"Bot /run job failed: {e}")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ Error: {e}")

    asyncio.create_task(_run_and_notify())


def start_bot(token: str, chat_id: str) -> None:
    """Build and start the bot in its own thread with its own event loop."""
    global _app_task

    def _run_bot_loop() -> None:
        app = Application.builder().token(token).build()
        app.bot_data["chat_id"] = chat_id

        app.add_handler(CommandHandler("start", cmd_help))
        app.add_handler(CommandHandler("help", cmd_help))
        app.add_handler(CommandHandler("status", cmd_status))
        app.add_handler(CommandHandler("positions", cmd_positions))
        app.add_handler(CommandHandler("decision", cmd_decision))
        app.add_handler(CommandHandler("run", cmd_run))

        try:
            logger.info("Telegram bot started — polling for commands")
            asyncio.run(app.run_polling(drop_pending_updates=True))
        except Exception as e:
            logger.error(f"Bot polling failed: {e}")

    _app_task = threading.Thread(target=_run_bot_loop, name="telegram-bot", daemon=True)
    _app_task.start()


def stop_bot() -> None:
    """Stop the bot (cleanup on shutdown)."""
    pass  # Thread will be daemon, so it exits when main exits
