"""Admin API routes."""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, BackgroundTasks

from config.settings import settings
from scheduler.jobs import daily_job

router = APIRouter()


def _require_admin(token: str | None) -> None:
    if not token or token != settings.admin_token:
        raise HTTPException(status_code=401, detail="invalid admin token")


@router.post("/run-now")
def run_now(
    background_tasks: BackgroundTasks,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
):
    """Manually trigger today's job. Still respects trading-day and idempotency checks."""
    _require_admin(x_admin_token)
    background_tasks.add_task(daily_job)
    return {"status": "scheduled"}


@router.get("/health")
def health():
    return {"status": "ok"}
