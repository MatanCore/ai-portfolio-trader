"""Daily job orchestrator — 16 steps, runs at 4:30 PM ET on trading days."""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas_market_calendars as mcal
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from ai.claude_client import get_decision
from ai.prompt_builder import build_system_prompt, build_user_prompt
from config.settings import settings
from data.coingecko import fetch_crypto_prices
from data.fear_greed import fetch_fear_greed
from data.market_data import (
    batch_fetch_prices,
    compute_spy_n_day_return,
    fetch_spy_history,
    fetch_vix,
    three_red_days,
)
from data.s5fi import compute_s5fi
from data.universe import CRYPTO_SYMBOL_MAP, all_crypto_ids, all_stock_tickers, crypto_symbol
from db.database import SessionLocal
from db.models import DailyDecision, MarketContextLog
from notifications.email_sender import format_decision_email, send_email
from notifications.telegram_sender import format_decision_telegram, send_telegram
from portfolio.simulator import OrderInput, apply_orders, write_snapshot
from portfolio.state import load_portfolio_state, update_position_prices
from portfolio.stops import check_and_apply_stops
from signals.detector import evaluate_signals

logger = logging.getLogger(__name__)

LOCK_FILE = Path("data_cache/.daily_job.lock")
ET = pytz.timezone("US/Eastern")
NYSE = mcal.get_calendar("NYSE")


def _acquire_lock() -> bool:
    Path("data_cache").mkdir(exist_ok=True)
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
            try:
                os.kill(pid, 0)
                return False
            except OSError:
                LOCK_FILE.unlink(missing_ok=True)
        except Exception:
            LOCK_FILE.unlink(missing_ok=True)
    LOCK_FILE.write_text(str(os.getpid()))
    return True


def _release_lock() -> None:
    LOCK_FILE.unlink(missing_ok=True)


def _is_trading_day(d: date) -> bool:
    sched = NYSE.schedule(start_date=d, end_date=d)
    return not sched.empty


def _today_et() -> date:
    return datetime.now(ET).date()


def daily_job() -> dict:
    """Full 16-step orchestrator. Returns a summary dict."""
    if not _acquire_lock():
        logger.warning("Daily job already running elsewhere; aborting")
        return {"skipped": True, "reason": "lock held"}

    try:
        today = _today_et()

        if not _is_trading_day(today):
            logger.info(f"{today} is not a trading day; skipping")
            return {"skipped": True, "reason": "non-trading day", "date": today.isoformat()}

        db = SessionLocal()
        try:
            existing = db.query(DailyDecision).filter(DailyDecision.decision_date == today).first()
            if existing:
                logger.info(f"Decision for {today} already exists; skipping")
                return {"skipped": True, "reason": "already ran today", "date": today.isoformat()}

            logger.info(f"[1/16] Starting daily job for {today}")

            logger.info("[4/16] Fetching market data (Fear/Greed, VIX, SPY, cryptos, stocks)")
            fear_greed = fetch_fear_greed() or {}
            vix = fetch_vix()
            spy_hist = fetch_spy_history(days=10)
            spy_close = float(spy_hist["Close"].iloc[-1]) if not spy_hist.empty else None
            spy_1d = compute_spy_n_day_return(spy_hist, 1)
            spy_5d = compute_spy_n_day_return(spy_hist, 5)
            spy_red3 = three_red_days(spy_hist)

            crypto_prices_by_id = fetch_crypto_prices(all_crypto_ids())
            crypto_prices = {crypto_symbol(cid): p for cid, p in crypto_prices_by_id.items()}

            logger.info("[5/16] Batch-fetching stock prices")
            stock_prices = batch_fetch_prices(all_stock_tickers())
            universe_prices = {**stock_prices, **crypto_prices}

            logger.info("[6/16] Computing S5FI (slow)")
            s5fi = compute_s5fi()

            logger.info("[7/16] Evaluating signals")
            signal_result = evaluate_signals(
                fear_greed_value=fear_greed.get("value"),
                vix_value=vix,
                s5fi_value=s5fi,
                spy_three_red=spy_red3,
            )

            logger.info("[8/16] Logging MarketContextLog")
            mcl_existing = db.query(MarketContextLog).filter(MarketContextLog.log_date == today).first()
            if mcl_existing:
                mcl = mcl_existing
            else:
                mcl = MarketContextLog(log_date=today)
                db.add(mcl)
            mcl.fear_greed_value = fear_greed.get("value")
            mcl.fear_greed_label = fear_greed.get("label")
            mcl.vix = vix
            mcl.spy_close = spy_close
            mcl.spy_1d_return = spy_1d
            mcl.spy_5d_return = spy_5d
            mcl.s5fi = s5fi
            mcl.signal_extreme_fear = signal_result.extreme_fear
            mcl.signal_vix_spike = signal_result.vix_spike
            mcl.signal_s5fi_breadth = signal_result.s5fi_breadth
            mcl.signal_three_red_days = signal_result.three_red_days
            mcl.signals_active_count = signal_result.active_count
            db.commit()

            logger.info("[9/16] Loading portfolio state")

            logger.info("[10/16] Updating position prices")
            update_position_prices(db, universe_prices)

            logger.info("[11/16] Checking trailing stops")
            stop_events = check_and_apply_stops(db, today)
            if stop_events:
                logger.info(f"  {len(stop_events)} positions stopped out")

            state = load_portfolio_state(db)

            logger.info("[12/16] Building prompts")
            recent = (
                db.query(DailyDecision)
                .filter(DailyDecision.decision_date < today)
                .order_by(DailyDecision.decision_date.desc())
                .limit(5)
                .all()
            )
            recent_list = [
                {
                    "date": d.decision_date.isoformat(),
                    "action": d.action,
                    "confidence": d.confidence,
                    "notes": (d.notes or "")[:300],
                    "signals_active": d.signals_active,
                }
                for d in recent
            ]
            market_context = {
                "vix": vix,
                "fear_greed": fear_greed,
                "spy_close": spy_close,
                "spy_1d_return_pct": spy_1d,
                "spy_5d_return_pct": spy_5d,
                "s5fi": s5fi,
            }
            system_prompt = build_system_prompt()
            user_prompt = build_user_prompt(
                today=today,
                portfolio_state=state.to_dict(),
                signal_result=signal_result.to_dict(),
                market_context=market_context,
                asset_universe=universe_prices,
                recent_decisions=recent_list,
                stop_events_today=stop_events,
            )

            logger.info("[13/16] Calling Claude")
            result = get_decision(system_prompt, user_prompt)
            decision = result.decision
            logger.info(f"  Decision: {decision.action} (conf={decision.confidence:.2f}, positions={len(decision.positions)})")

            logger.info("[14/16] Applying orders")
            order_inputs = []
            crypto_symbols = set(CRYPTO_SYMBOL_MAP.values())
            for p in decision.positions:
                risk_per_share = p.entry_price - p.stop_loss
                if risk_per_share <= 0:
                    logger.warning(f"  Skipping {p.ticker}: invalid stop loss ({p.stop_loss} >= {p.entry_price})")
                    continue
                risk_amount = state.total_nav * (p.risk_pct / 100.0)
                shares = risk_amount / risk_per_share
                asset_type = "crypto" if p.ticker.upper() in crypto_symbols else "stock"
                order_inputs.append(OrderInput(
                    ticker=p.ticker,
                    action="BUY",
                    asset_type=asset_type,
                    price=p.entry_price,
                    shares=shares,
                    thesis=p.entry_reason,
                    risk_note=f"Stop: ${p.stop_loss} | Target: ${p.take_profit} | RR: {p.risk_reward} | Strategy: {p.strategy}",
                ))
            applied = apply_orders(db, order_inputs, today)

            logger.info("[15/16] Saving DailyDecision + PortfolioSnapshot")
            daily = DailyDecision(
                decision_date=today,
                action=decision.action,
                confidence=decision.confidence,
                market_assessment="",
                notes=decision.reasoning,
                raw_json=json.dumps(decision.model_dump(), default=str),
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cache_read_tokens=result.cache_read_tokens,
                duration_seconds=result.duration_seconds,
                signals_active=signal_result.active_count,
                fear_greed_value=fear_greed.get("value"),
                vix_value=vix,
                s5fi_value=s5fi,
            )
            db.add(daily)
            db.commit()
            snap = write_snapshot(db, today)

            logger.info("[16/16] Sending notifications")
            order_dicts = [
                {
                    "ticker": a.ticker,
                    "action": a.action,
                    "shares": a.shares,
                    "price": a.price,
                    "total_value": a.total_value,
                }
                for a in applied if not a.rejected
            ]
            watchlist_dicts = [w.model_dump() for w in decision.watchlist] if decision.watchlist else []
            should_notify = order_dicts or decision.action != "HOLD" or len(watchlist_dicts) > 0
            if should_notify:
                subj, body = format_decision_email(
                    today.isoformat(), decision.action, order_dicts, snap.total_nav, snap.cash, watchlist_dicts
                )
                send_email(subj, body)
                send_telegram(format_decision_telegram(
                    today.isoformat(), decision.action, order_dicts, snap.total_nav, watchlist_dicts
                ))

            return {
                "date": today.isoformat(),
                "action": decision.action,
                "orders_applied": len([a for a in applied if not a.rejected]),
                "orders_rejected": len([a for a in applied if a.rejected]),
                "stops_triggered": len(stop_events),
                "nav": snap.total_nav,
                "cash": snap.cash,
            }
        finally:
            db.close()
    except Exception as e:
        logger.exception(f"Daily job failed: {e}")
        return {"error": str(e)}
    finally:
        _release_lock()


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=ET)
    scheduler.add_job(
        daily_job,
        CronTrigger(
            day_of_week="mon-fri",
            hour=settings.daily_run_hour,
            minute=settings.daily_run_minute,
            timezone=ET,
        ),
        id="daily_portfolio_job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=600,  # Allow up to 10 minutes late before skipping
    )
    scheduler.start()
    logger.info(
        f"Scheduler started — daily at {settings.daily_run_hour:02d}:{settings.daily_run_minute:02d} ET"
    )
    return scheduler
