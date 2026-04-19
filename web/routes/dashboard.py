"""Jinja2 dashboard routes."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import DailyDecision, MarketContextLog, Order, PortfolioSnapshot, Position
from portfolio.state import STARTING_CAPITAL, load_portfolio_state

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    state = load_portfolio_state(db)

    snapshots = (
        db.query(PortfolioSnapshot).order_by(PortfolioSnapshot.snapshot_date.asc()).all()
    )
    equity_dates = [s.snapshot_date.isoformat() for s in snapshots]
    equity_values = [float(s.total_nav) for s in snapshots]

    today_decision = (
        db.query(DailyDecision).order_by(DailyDecision.decision_date.desc()).first()
    )
    today_orders = []
    if today_decision:
        today_orders = (
            db.query(Order).filter(Order.decision_date == today_decision.decision_date).all()
        )

    latest_mcl = (
        db.query(MarketContextLog).order_by(MarketContextLog.log_date.desc()).first()
    )

    total_return_pct = (state.total_nav / STARTING_CAPITAL - 1) * 100.0

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "state": state,
            "total_return_pct": total_return_pct,
            "starting_capital": STARTING_CAPITAL,
            "equity_dates_json": json.dumps(equity_dates),
            "equity_values_json": json.dumps(equity_values),
            "today_decision": today_decision,
            "today_orders": today_orders,
            "mcl": latest_mcl,
        },
    )


@router.get("/positions", response_class=HTMLResponse)
def positions_page(request: Request, db: Session = Depends(get_db)):
    open_positions = (
        db.query(Position).filter(Position.is_open.is_(True)).order_by(Position.entry_date.desc()).all()
    )
    closed_positions = (
        db.query(Position).filter(Position.is_open.is_(False)).order_by(Position.exit_date.desc()).limit(50).all()
    )
    return templates.TemplateResponse(
        request,
        "positions.html",
        {"open_positions": open_positions, "closed_positions": closed_positions},
    )


@router.get("/decisions", response_class=HTMLResponse)
def decisions_page(
    request: Request,
    action: str | None = None,
    page: int = 1,
    page_size: int = 30,
    db: Session = Depends(get_db),
):
    q = db.query(DailyDecision)
    if action and action.upper() in ("BUY", "SELL", "HOLD"):
        q = q.filter(DailyDecision.action == action.upper())
    total = q.count()
    decisions = (
        q.order_by(DailyDecision.decision_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "decisions.html",
        {
            "decisions": decisions,
            "filter_action": action,
            "page": page,
            "page_size": page_size,
            "total": total,
            "has_next": page * page_size < total,
        },
    )


@router.get("/decisions/{decision_date}", response_class=HTMLResponse)
def decision_detail(request: Request, decision_date: date, db: Session = Depends(get_db)):
    decision = (
        db.query(DailyDecision).filter(DailyDecision.decision_date == decision_date).first()
    )
    orders = db.query(Order).filter(Order.decision_date == decision_date).all()
    mcl = db.query(MarketContextLog).filter(MarketContextLog.log_date == decision_date).first()

    raw_json_pretty = ""
    if decision and decision.raw_json:
        try:
            raw_json_pretty = json.dumps(json.loads(decision.raw_json), indent=2)
        except Exception:
            raw_json_pretty = decision.raw_json

    return templates.TemplateResponse(
        request,
        "decision_detail.html",
        {
            "decision": decision,
            "orders": orders,
            "mcl": mcl,
            "raw_json_pretty": raw_json_pretty,
        },
    )
