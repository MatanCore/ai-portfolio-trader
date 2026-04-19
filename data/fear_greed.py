"""Fear & Greed Index from alternative.me (crypto-wide) AND CNN-style classification."""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

CACHE_DIR = Path("data_cache")
CACHE_DIR.mkdir(exist_ok=True)


def _cache_path(d: date) -> Path:
    return CACHE_DIR / f"fear_greed_{d.isoformat()}.json"


def _classify(value: float) -> str:
    if value < 25:
        return "Extreme Fear"
    if value < 45:
        return "Fear"
    if value < 55:
        return "Neutral"
    if value < 75:
        return "Greed"
    return "Extreme Greed"


def fetch_fear_greed() -> dict | None:
    today = date.today()
    cached = _cache_path(today)
    if cached.exists():
        try:
            return json.loads(cached.read_text())
        except Exception:
            pass

    try:
        r = httpx.get("https://api.alternative.me/fng/?limit=1", timeout=15.0)
        r.raise_for_status()
        payload = r.json()
        datum = payload["data"][0]
        result = {
            "value": float(datum["value"]),
            "label": datum.get("value_classification") or _classify(float(datum["value"])),
            "timestamp": datum.get("timestamp"),
        }
        cached.write_text(json.dumps(result))
        return result
    except Exception as e:
        logger.warning(f"Fear & Greed fetch failed: {e}")
        return None
