"""CoinGecko price fetch for a batch of crypto IDs."""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

BASE = "https://api.coingecko.com/api/v3"


def fetch_crypto_prices(ids: list[str]) -> dict[str, float]:
    """Return {coingecko_id: usd_price}."""
    if not ids:
        return {}
    try:
        r = httpx.get(
            f"{BASE}/simple/price",
            params={"ids": ",".join(ids), "vs_currencies": "usd"},
            timeout=20.0,
        )
        r.raise_for_status()
        data = r.json()
        return {k: float(v["usd"]) for k, v in data.items() if "usd" in v}
    except Exception as e:
        logger.warning(f"CoinGecko fetch failed: {e}")
        return {}
