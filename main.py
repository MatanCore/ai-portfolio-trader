"""Entry point — starts FastAPI + APScheduler on port 8000."""
import os
import uvicorn

os.environ.setdefault("PYTHONUNBUFFERED", "1")

from web.app import app  # noqa: F401 — imported to initialize app + scheduler


if __name__ == "__main__":
    uvicorn.run("web.app:app", host="0.0.0.0", port=8000, reload=False)
