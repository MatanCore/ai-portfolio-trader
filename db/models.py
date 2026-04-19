from datetime import date, datetime
from sqlalchemy import Date, DateTime, Float, Integer, String, Text, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column
from db.database import Base


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    total_nav: Mapped[float] = mapped_column(Float, nullable=False)
    cash: Mapped[float] = mapped_column(Float, nullable=False)
    invested_value: Mapped[float] = mapped_column(Float, nullable=False)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    daily_return_pct: Mapped[float] = mapped_column(Float, default=0.0)
    total_return_pct: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(10), nullable=False)  # stock | crypto
    shares: Mapped[float] = mapped_column(Float, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    current_price: Mapped[float] = mapped_column(Float, nullable=False)
    cost_basis: Mapped[float] = mapped_column(Float, nullable=False)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)
    highest_price: Mapped[float] = mapped_column(Float, nullable=False)
    trailing_stop_pct: Mapped[float] = mapped_column(Float, default=12.0)
    trailing_stop_active: Mapped[bool] = mapped_column(Boolean, default=False)
    trailing_stop_price: Mapped[float] = mapped_column(Float, nullable=True)
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)
    exit_price: Mapped[float] = mapped_column(Float, nullable=True)
    exit_date: Mapped[date] = mapped_column(Date, nullable=True)
    realized_pnl: Mapped[float] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[str] = mapped_column(String(50), nullable=True)
    thesis: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class DailyDecision(Base):
    __tablename__ = "daily_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    decision_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False)  # BUY | SELL | HOLD
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    market_assessment: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    raw_json: Mapped[str] = mapped_column(Text, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    signals_active: Mapped[int] = mapped_column(Integer, default=0)
    fear_greed_value: Mapped[float] = mapped_column(Float, nullable=True)
    vix_value: Mapped[float] = mapped_column(Float, nullable=True)
    s5fi_value: Mapped[float] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    decision_date: Mapped[date] = mapped_column(Date, nullable=False)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False)  # BUY | SELL
    shares: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    total_value: Mapped[float] = mapped_column(Float, nullable=False)
    allocation_pct: Mapped[float] = mapped_column(Float, nullable=False)
    thesis: Mapped[str] = mapped_column(Text, nullable=True)
    risk_note: Mapped[str] = mapped_column(Text, nullable=True)
    trailing_stop_override_pct: Mapped[float] = mapped_column(Float, nullable=True)
    trailing_stop_justification: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class MarketContextLog(Base):
    __tablename__ = "market_context_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    log_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    fear_greed_value: Mapped[float] = mapped_column(Float, nullable=True)
    fear_greed_label: Mapped[str] = mapped_column(String(30), nullable=True)
    vix: Mapped[float] = mapped_column(Float, nullable=True)
    spy_close: Mapped[float] = mapped_column(Float, nullable=True)
    spy_1d_return: Mapped[float] = mapped_column(Float, nullable=True)
    spy_5d_return: Mapped[float] = mapped_column(Float, nullable=True)
    s5fi: Mapped[float] = mapped_column(Float, nullable=True)
    signal_extreme_fear: Mapped[bool] = mapped_column(Boolean, default=False)
    signal_vix_spike: Mapped[bool] = mapped_column(Boolean, default=False)
    signal_s5fi_breadth: Mapped[bool] = mapped_column(Boolean, default=False)
    signal_three_red_days: Mapped[bool] = mapped_column(Boolean, default=False)
    signals_active_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
