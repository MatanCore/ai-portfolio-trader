"""yfinance wrappers for stock/ETF prices, VIX, and SPY history."""
from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def fetch_vix() -> float | None:
    try:
        hist = yf.Ticker("^VIX").history(period="5d", auto_adjust=False)
        if hist.empty:
            return None
        return float(hist["Close"].iloc[-1])
    except Exception as e:
        logger.warning(f"VIX fetch failed: {e}")
        return None


def fetch_spy_history(days: int = 10) -> pd.DataFrame:
    try:
        hist = yf.Ticker("SPY").history(period=f"{days + 5}d", auto_adjust=False)
        return hist.tail(days)
    except Exception as e:
        logger.warning(f"SPY history fetch failed: {e}")
        return pd.DataFrame()


def batch_fetch_prices(tickers: list[str], chunk_size: int = 25) -> dict[str, float]:
    """Return {ticker: last_close_price}. Chunks to avoid yfinance rate limits."""
    prices: dict[str, float] = {}
    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i:i + chunk_size]
        try:
            df = yf.download(
                tickers=" ".join(chunk),
                period="5d",
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
                    if not close.empty:
                        prices[t] = float(close.iloc[-1])
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Chunk fetch failed for {chunk[:3]}...: {e}")
            continue
    return prices


def compute_spy_n_day_return(spy_hist: pd.DataFrame, n: int) -> float | None:
    if spy_hist is None or spy_hist.empty or len(spy_hist) < n + 1:
        return None
    closes = spy_hist["Close"].tolist()
    return (closes[-1] / closes[-1 - n] - 1.0) * 100.0


def three_red_days(spy_hist: pd.DataFrame) -> bool:
    """True if the last 3 trading days all closed lower than the previous day."""
    if spy_hist is None or spy_hist.empty or len(spy_hist) < 4:
        return False
    closes = spy_hist["Close"].tail(4).tolist()
    return closes[1] < closes[0] and closes[2] < closes[1] and closes[3] < closes[2]
