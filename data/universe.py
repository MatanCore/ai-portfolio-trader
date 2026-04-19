"""Asset universe — curated list of liquid stocks, ETFs, and major cryptos."""

STOCKS = [
    # Mega-cap tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AVGO", "ORCL", "NFLX",
    # Finance
    "JPM", "BAC", "GS", "MS", "V", "MA",
    # Healthcare
    "UNH", "JNJ", "LLY", "PFE", "ABBV", "MRK",
    # Consumer
    "WMT", "COST", "HD", "NKE", "MCD", "SBUX", "DIS",
    # Energy & industrials
    "XOM", "CVX", "CAT", "BA", "GE",
    # Semiconductors
    "AMD", "INTC", "QCOM", "TSM", "ASML", "MU",
    # Other growth
    "CRM", "ADBE", "SHOP", "UBER", "PLTR", "COIN",
]

ETFS = [
    "SPY", "QQQ", "IWM", "DIA",        # broad market
    "XLK", "XLF", "XLE", "XLV", "XLY", "XLI",  # sector
    "GLD", "SLV", "TLT",                # safe-havens / bonds
]

CRYPTOS = [
    # CoinGecko IDs
    "bitcoin", "ethereum", "solana", "ripple", "cardano",
    "avalanche-2", "chainlink", "polkadot", "dogecoin", "litecoin",
]

CRYPTO_SYMBOL_MAP = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "solana": "SOL",
    "ripple": "XRP",
    "cardano": "ADA",
    "avalanche-2": "AVAX",
    "chainlink": "LINK",
    "polkadot": "DOT",
    "dogecoin": "DOGE",
    "litecoin": "LTC",
}


def all_stock_tickers() -> list[str]:
    return STOCKS + ETFS


def all_crypto_ids() -> list[str]:
    return CRYPTOS


def crypto_symbol(coingecko_id: str) -> str:
    return CRYPTO_SYMBOL_MAP.get(coingecko_id, coingecko_id.upper())
