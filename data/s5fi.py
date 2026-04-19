"""S5FI: % of S&P 500 components trading above their 50-day moving average.

Slow (~30-90s) — results pickled daily to data_cache/s5fi_YYYY-MM-DD.pkl.
"""
from __future__ import annotations

import logging
import pickle
from datetime import date
from pathlib import Path

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

CACHE_DIR = Path("data_cache")
CACHE_DIR.mkdir(exist_ok=True)

SP500_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"


def _cache_path(d: date) -> Path:
    return CACHE_DIR / f"s5fi_{d.isoformat()}.pkl"


def _load_sp500_tickers() -> list[str]:
    tickers_cache = CACHE_DIR / "sp500_constituents.csv"
    try:
        if tickers_cache.exists():
            df = pd.read_csv(tickers_cache)
        else:
            df = pd.read_csv(SP500_URL)
            df.to_csv(tickers_cache, index=False)
        symbols = df["Symbol"].dropna().astype(str).tolist()
        return [s.replace(".", "-") for s in symbols]
    except Exception as e:
        logger.warning(f"S&P 500 constituents load failed: {e}")
        return []


def compute_s5fi() -> float | None:
    today = date.today()
    cached = _cache_path(today)
    if cached.exists():
        try:
            return float(pickle.loads(cached.read_bytes()))
        except Exception:
            pass

    tickers = _load_sp500_tickers()
    if not tickers:
        return None

    above = 0
    total = 0
    chunk_size = 50
    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i:i + chunk_size]
        try:
            df = yf.download(
                tickers=" ".join(chunk),
                period="75d",
                interval="1d",
                group_by="ticker",
                auto_adjust=False,
                progress=False,
                threads=True,
            )
            for t in chunk:
                try:
                    if len(chunk) == 1:
                        close = df["Close"].dropna()
                    else:
                        close = df[t]["Close"].dropna()
                    if len(close) < 50:
                        continue
                    ma50 = close.tail(50).mean()
                    if close.iloc[-1] > ma50:
                        above += 1
                    total += 1
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"S5FI chunk {i} failed: {e}")
            continue

    if total == 0:
        return None
    value = (above / total) * 100.0
    try:
        cached.write_bytes(pickle.dumps(value))
    except Exception:
        pass
    return value
