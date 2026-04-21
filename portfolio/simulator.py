"""Apply Claude's orders to the portfolio and persist to DB."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Iterable

from sqlalchemy.orm import Session

from db.models import Order, Position, PortfolioSnapshot
from portfolio.state import load_portfolio_state, STARTING_CAPITAL

logger = logging.getLogger(__name__)

MAX_SINGLE_POSITION_PCT = 25.0
MIN_CASH_RESERVE_PCT = 20.0


@dataclass
class OrderInput:
    ticker: str
    action: str          # BUY | SELL
    asset_type: str      # stock | crypto
    price: float
    shares: float | None = None
    allocation_pct: float | None = None
    thesis: str = ""
    risk_note: str = ""
    trailing_stop_override_pct: float | None = None
    trailing_stop_justification: str | None = None


@dataclass
class AppliedOrder:
    ticker: str
    action: str
    shares: float
    price: float
    total_value: float
    allocation_pct: float
    rejected: bool = False
    reject_reason: str | None = None


def apply_orders(
    db: Session,
    orders: Iterable[OrderInput],
    today: date,
) -> list[AppliedOrder]:
    """Apply orders sequentially. Returns AppliedOrder list (successful + rejected)."""
    state = load_portfolio_state(db)
    cash = state.cash
    total_nav = state.total_nav
    applied: list[AppliedOrder] = []

    for o in orders:
        if o.action == "BUY":
            shares, value, reject = _size_buy(o, cash, total_nav)
            if reject:
                applied.append(AppliedOrder(o.ticker, o.action, 0, o.price, 0, 0, rejected=True, reject_reason=reject))
                continue

            pos = Position(
                ticker=o.ticker,
                asset_type=o.asset_type,
                shares=shares,
                entry_price=o.price,
                entry_date=today,
                current_price=o.price,
                cost_basis=value,
                highest_price=o.price,
                trailing_stop_pct=o.trailing_stop_override_pct or 12.0,
                trailing_stop_active=False,
                is_open=True,
                thesis=o.thesis,
            )
            db.add(pos)
            db.add(Order(
                decision_date=today,
                ticker=o.ticker,
                action="BUY",
                shares=shares,
                price=o.price,
                total_value=value,
                allocation_pct=(value / total_nav * 100.0) if total_nav else 0,
                thesis=o.thesis,
                risk_note=o.risk_note,
                trailing_stop_override_pct=o.trailing_stop_override_pct,
                trailing_stop_justification=o.trailing_stop_justification,
            ))
            cash -= value
            total_nav = cash + _invested_value(db)
            applied.append(AppliedOrder(o.ticker, "BUY", shares, o.price, value, value / total_nav * 100.0 if total_nav else 0))

        elif o.action == "SELL":
            pos = db.query(Position).filter(Position.ticker == o.ticker, Position.is_open.is_(True)).first()
            if pos is None:
                applied.append(AppliedOrder(o.ticker, "SELL", 0, o.price, 0, 0, rejected=True, reject_reason="no open position"))
                continue
            if o.shares is not None and o.shares <= 0:
                applied.append(AppliedOrder(o.ticker, "SELL", 0, o.price, 0, 0, rejected=True, reject_reason="invalid shares <= 0"))
                continue
            sell_shares = o.shares if o.shares and o.shares < pos.shares else pos.shares
            proceeds = sell_shares * o.price
            realized = (o.price - pos.entry_price) * sell_shares

            if sell_shares >= pos.shares:
                pos.is_open = False
                pos.exit_price = o.price
                pos.exit_date = today
                pos.realized_pnl = realized
                pos.exit_reason = "ai_sell"
            else:
                pos.shares -= sell_shares
                pos.cost_basis = pos.shares * pos.entry_price

            db.add(Order(
                decision_date=today,
                ticker=o.ticker,
                action="SELL",
                shares=sell_shares,
                price=o.price,
                total_value=proceeds,
                allocation_pct=0,
                thesis=o.thesis,
                risk_note=o.risk_note,
            ))
            cash += proceeds
            total_nav = cash + _invested_value(db)
            applied.append(AppliedOrder(o.ticker, "SELL", sell_shares, o.price, proceeds, 0))
        else:
            applied.append(AppliedOrder(o.ticker, o.action, 0, 0, 0, 0, rejected=True, reject_reason="unknown action"))

    db.commit()
    return applied


def _invested_value(db: Session) -> float:
    total = 0.0
    for p in db.query(Position).filter(Position.is_open.is_(True)).all():
        total += p.shares * p.current_price
    return total


def _size_buy(o: OrderInput, cash: float, total_nav: float) -> tuple[float, float, str | None]:
    if total_nav <= 0:
        return 0, 0, "zero NAV"
    if o.price <= 0:
        return 0, 0, "invalid price"

    if o.shares and o.shares > 0:
        value = o.shares * o.price
        shares = o.shares
    elif o.allocation_pct and o.allocation_pct > 0:
        alloc = min(o.allocation_pct, MAX_SINGLE_POSITION_PCT)
        value = total_nav * (alloc / 100.0)
        shares = value / o.price
    else:
        return 0, 0, "missing shares and allocation_pct"

    if value > total_nav * (MAX_SINGLE_POSITION_PCT / 100.0):
        value = total_nav * (MAX_SINGLE_POSITION_PCT / 100.0)
        shares = value / o.price

    min_cash_after = total_nav * (MIN_CASH_RESERVE_PCT / 100.0)
    if cash - value < min_cash_after:
        value = max(0.0, cash - min_cash_after)
        if value <= 0:
            return 0, 0, f"would breach {MIN_CASH_RESERVE_PCT}% min cash reserve"
        shares = value / o.price

    if shares <= 0:
        return 0, 0, "sized to zero shares"

    return shares, value, None


def write_snapshot(db: Session, today: date) -> PortfolioSnapshot:
    state = load_portfolio_state(db)
    total_return = (state.total_nav / STARTING_CAPITAL - 1) * 100.0

    prev = (
        db.query(PortfolioSnapshot)
        .filter(PortfolioSnapshot.snapshot_date < today)
        .order_by(PortfolioSnapshot.snapshot_date.desc())
        .first()
    )
    daily_return = 0.0
    if prev and prev.total_nav > 0:
        daily_return = (state.total_nav / prev.total_nav - 1) * 100.0

    existing = db.query(PortfolioSnapshot).filter(PortfolioSnapshot.snapshot_date == today).first()
    if existing:
        existing.total_nav = state.total_nav
        existing.cash = state.cash
        existing.invested_value = state.invested_value
        existing.unrealized_pnl = state.unrealized_pnl
        existing.daily_return_pct = daily_return
        existing.total_return_pct = total_return
        snap = existing
    else:
        snap = PortfolioSnapshot(
            snapshot_date=today,
            total_nav=state.total_nav,
            cash=state.cash,
            invested_value=state.invested_value,
            unrealized_pnl=state.unrealized_pnl,
            daily_return_pct=daily_return,
            total_return_pct=total_return,
        )
        db.add(snap)
    db.commit()
    return snap
