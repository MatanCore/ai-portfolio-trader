"""FastAPI application factory."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from db.database import init_db
from scheduler.jobs import start_scheduler
from web.routes import api as api_routes
from web.routes import dashboard as dashboard_routes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

BASE_DIR = Path(__file__).resolve().parent


def create_app() -> FastAPI:
    app = FastAPI(title="AI Portfolio Simulation", version="1.0.0")

    app.mount(
        "/static",
        StaticFiles(directory=BASE_DIR / "static"),
        name="static",
    )

    app.include_router(api_routes.router, prefix="/api")
    app.include_router(dashboard_routes.router)

    @app.on_event("startup")
    def _startup() -> None:
        from config.settings import settings
        init_db()
        app.state.scheduler = start_scheduler()
        if settings.telegram_bot_enabled and settings.telegram_bot_token:
            from notifications.telegram_bot import start_bot
            try:
                start_bot(settings.telegram_bot_token, settings.telegram_chat_id)
            except Exception as e:
                logging.getLogger(__name__).error(f"Failed to start Telegram bot: {e}")
        else:
            logging.getLogger(__name__).info("Telegram bot disabled (set TELEGRAM_BOT_ENABLED=true to enable)")

    @app.on_event("shutdown")
    def _shutdown() -> None:
        from notifications.telegram_bot import stop_bot
        sched = getattr(app.state, "scheduler", None)
        if sched is not None:
            sched.shutdown(wait=False)
        try:
            stop_bot()
        except Exception as e:
            logging.getLogger(__name__).error(f"Error stopping bot: {e}")

    return app


app = create_app()
