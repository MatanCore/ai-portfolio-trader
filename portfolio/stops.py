"""Trailing stop logic — runs BEFORE Claude each day.

Rules:
- Activate trailing stop once a position reaches +20% unrealized profit.
- Default trail: 12% from highest_price (Claude can override at entry).
- If current_price <= highest_price * (1 - stop_pct/100), close position.
"""
from __future__ import annotations

import logging
from datetime import date

from sqlalchemy.orm import Session

from db.models import Order, Position

logger = logging.getLogger(__name__)

PROFIT_ACTIVATION_PCT = 20.0


def check_and_apply_stops(db: Session, today: date) -> list[dict]:
    """Check all open positions for trailing stop triggers. Close triggered ones.

    Returns a list of {ticker, exit_price, realized_pnl, reason} for stopped positions.
    """
    closed_events: list[dict] = []
    open_positions = db.query(Position).filter(Position.is_open.is_(True)).all()

    for p in open_positions:
        profit_pct = ((p.current_price / p.entry_price) - 1.0) * 100.0 if p.entry_price else 0.0

        if not p.trailing_stop_active and profit_pct >= PROFIT_ACTIVATION_PCT:
            p.trailing_stop_active = True

        if p.trailing_stop_active:
            stop_price = p.highest_price * (1.0 - p.trailing_stop_pct / 100.0)
            p.trailing_stop_price = stop_price

            if p.current_price <= stop_price:
                realized = (p.current_price - p.entry_price) * p.shares
                proceeds = p.shares * p.current_price
                p.is_open = False
                p.exit_price = p.current_price
                p.exit_date = today
                p.realized_pnl = realized
                p.exit_reason = f"trailing_stop_{p.trailing_stop_pct:.1f}pct"
                db.add(Order(
                    decision_date=today,
                    ticker=p.ticker,
                    action="SELL",
                    shares=p.shares,
                    price=p.current_price,
                    total_value=proceeds,
                    allocation_pct=0,
                    thesis="trailing stop triggered",
                    risk_note=f"auto-close at {p.trailing_stop_pct:.1f}% trail from highest ${p.highest_price:.2f}",
                ))
                closed_events.append({
                    "ticker": p.ticker,
                    "exit_price": p.current_price,
                    "realized_pnl": realized,
                    "reason": p.exit_reason,
                    "shares": p.shares,
                    "proceeds": p.shares * p.current_price,
                })
                logger.info(f"[STOP] {p.ticker} closed at ${p.current_price:.2f} (PnL=${realized:.2f})")

    db.commit()
    return closed_events
