from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.database import Base
from db import models  # noqa: F401
from db.models import Position
from portfolio.simulator import (
    MAX_SINGLE_POSITION_PCT,
    MIN_CASH_RESERVE_PCT,
    OrderInput,
    apply_orders,
    write_snapshot,
)
from portfolio.state import STARTING_CAPITAL, load_portfolio_state
from portfolio.stops import check_and_apply_stops


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    s = TestSession()
    yield s
    s.close()


def test_initial_state_is_starting_capital(db):
    state = load_portfolio_state(db)
    assert state.cash == STARTING_CAPITAL
    assert state.invested_value == 0
    assert state.total_nav == STARTING_CAPITAL


def test_buy_respects_max_single_position(db):
    today = date(2026, 4, 18)
    orders = [OrderInput(ticker="AAPL", action="BUY", asset_type="stock", price=100.0, allocation_pct=50.0)]
    applied = apply_orders(db, orders, today)
    assert applied[0].rejected is False
    assert applied[0].total_value <= STARTING_CAPITAL * MAX_SINGLE_POSITION_PCT / 100.0 + 0.01


def test_buy_respects_min_cash_reserve(db):
    today = date(2026, 4, 18)
    orders = [
        OrderInput(ticker="A", action="BUY", asset_type="stock", price=100, allocation_pct=25),
        OrderInput(ticker="B", action="BUY", asset_type="stock", price=100, allocation_pct=25),
        OrderInput(ticker="C", action="BUY", asset_type="stock", price=100, allocation_pct=25),
        OrderInput(ticker="D", action="BUY", asset_type="stock", price=100, allocation_pct=25),
    ]
    apply_orders(db, orders, today)
    state = load_portfolio_state(db)
    assert state.cash >= state.total_nav * MIN_CASH_RESERVE_PCT / 100.0 - 0.01


def test_sell_closes_position(db):
    today = date(2026, 4, 18)
    apply_orders(db, [OrderInput(ticker="AAPL", action="BUY", asset_type="stock", price=100.0, allocation_pct=20)], today)
    apply_orders(db, [OrderInput(ticker="AAPL", action="SELL", asset_type="stock", price=110.0)], today)
    pos = db.query(Position).filter(Position.ticker == "AAPL").first()
    assert pos.is_open is False
    assert pos.realized_pnl > 0


def test_snapshot_records_total_return(db):
    today = date(2026, 4, 18)
    snap = write_snapshot(db, today)
    assert snap.total_nav == STARTING_CAPITAL
    assert snap.total_return_pct == 0.0


def test_trailing_stop_activates_and_triggers(db):
    today = date(2026, 4, 18)
    apply_orders(db, [OrderInput(ticker="AAPL", action="BUY", asset_type="stock", price=100.0, allocation_pct=20)], today)
    pos = db.query(Position).filter(Position.ticker == "AAPL").first()
    # push price up 25%
    pos.current_price = 125.0
    pos.highest_price = 125.0
    db.commit()
    check_and_apply_stops(db, today)
    pos = db.query(Position).filter(Position.ticker == "AAPL").first()
    assert pos.trailing_stop_active is True

    # drop 15% — triggers 12% default stop
    pos.current_price = 105.0
    db.commit()
    check_and_apply_stops(db, today)
    pos = db.query(Position).filter(Position.ticker == "AAPL").first()
    assert pos.is_open is False
    assert pos.exit_reason.startswith("trailing_stop")
