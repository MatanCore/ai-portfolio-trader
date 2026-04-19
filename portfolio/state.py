"""Load and serialize current portfolio state for prompts and views."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from db.models import Order, Position, PortfolioSnapshot

STARTING_CAPITAL = 10_000.0


def compute_cash(db: Session) -> float:
    """Authoritative cash balance = starting capital +/- all order cashflows."""
    total = STARTING_CAPITAL
    for o in db.query(Order).all():
        if o.action == "BUY":
            total -= o.total_value
        elif o.action == "SELL":
            total += o.total_value
    return total


@dataclass
class PositionView:
    ticker: str
    asset_type: str
    shares: float
    entry_price: float
    current_price: float
    cost_basis: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    entry_date: date
    highest_price: float
    trailing_stop_active: bool
    trailing_stop_pct: float
    trailing_stop_price: float | None


@dataclass
class PortfolioState:
    cash: float
    total_nav: float
    invested_value: float
    unrealized_pnl: float
    positions: list[PositionView] = field(default_factory=list)

    @property
    def cash_pct(self) -> float:
        return (self.cash / self.total_nav * 100.0) if self.total_nav > 0 else 0.0

    @property
    def invested_pct(self) -> float:
        return (self.invested_value / self.total_nav * 100.0) if self.total_nav > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "cash": round(self.cash, 2),
            "cash_pct": round(self.cash_pct, 2),
            "invested_value": round(self.invested_value, 2),
            "invested_pct": round(self.invested_pct, 2),
            "total_nav": round(self.total_nav, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "total_return_pct": round((self.total_nav / STARTING_CAPITAL - 1) * 100, 2),
            "positions": [
                {
                    "ticker": p.ticker,
                    "asset_type": p.asset_type,
                    "shares": round(p.shares, 6),
                    "entry_price": round(p.entry_price, 4),
                    "current_price": round(p.current_price, 4),
                    "cost_basis": round(p.cost_basis, 2),
                    "market_value": round(p.shares * p.current_price, 2),
                    "unrealized_pnl": round(p.unrealized_pnl, 2),
                    "unrealized_pnl_pct": round(p.unrealized_pnl_pct, 2),
                    "entry_date": p.entry_date.isoformat(),
                    "highest_price": round(p.highest_price, 4),
                    "trailing_stop_active": p.trailing_stop_active,
                    "trailing_stop_pct": round(p.trailing_stop_pct, 2),
                    "trailing_stop_price": round(p.trailing_stop_price, 4) if p.trailing_stop_price else None,
                }
                for p in self.positions
            ],
        }


def load_portfolio_state(db: Session) -> PortfolioState:
    cash = compute_cash(db)
    open_positions = db.query(Position).filter(Position.is_open.is_(True)).all()
    views: list[PositionView] = []
    invested_value = 0.0
    unrealized_pnl = 0.0
    for p in open_positions:
        mv = p.shares * p.current_price
        invested_value += mv
        unrealized_pnl += (p.current_price - p.entry_price) * p.shares
        views.append(
            PositionView(
                ticker=p.ticker,
                asset_type=p.asset_type,
                shares=p.shares,
                entry_price=p.entry_price,
                current_price=p.current_price,
                cost_basis=p.cost_basis,
                unrealized_pnl=(p.current_price - p.entry_price) * p.shares,
                unrealized_pnl_pct=((p.current_price / p.entry_price) - 1) * 100.0 if p.entry_price else 0.0,
                entry_date=p.entry_date,
                highest_price=p.highest_price,
                trailing_stop_active=p.trailing_stop_active,
                trailing_stop_pct=p.trailing_stop_pct,
                trailing_stop_price=p.trailing_stop_price,
            )
        )

    return PortfolioState(
        cash=cash,
        total_nav=cash + invested_value,
        invested_value=invested_value,
        unrealized_pnl=unrealized_pnl,
        positions=views,
    )


def update_position_prices(db: Session, price_map: dict[str, float]) -> None:
    """Update current_price, highest_price, and unrealized PnL for all open positions."""
    for p in db.query(Position).filter(Position.is_open.is_(True)).all():
        price = price_map.get(p.ticker)
        if price is None:
            continue
        p.current_price = price
        if price > p.highest_price:
            p.highest_price = price
        p.unrealized_pnl = (price - p.entry_price) * p.shares
        p.unrealized_pnl_pct = ((price / p.entry_price) - 1) * 100.0 if p.entry_price else 0.0
    db.commit()
