# AI Portfolio Simulation — Project Context

## What This Is
A paper-trading simulation where Claude AI makes one BUY/SELL/HOLD decision per day after US market close. Every decision is logged with full reasoning. This is a research/transparency tool, not a real trading bot.

## Key Rules
- Starting capital: $10,000 (100% cash)
- Max single position: 25% of portfolio value
- Min cash reserve: 20% at all times
- Preferred holding: 5–30 days (swing trades)
- Scheduler fires at 4:30 PM ET on trading days only

## Trailing Stop Logic
- Trigger at +20% unrealized profit
- Default trailing stop: 12% from highest price
- Claude can override stop % with written justification
- Stops are checked BEFORE Claude's daily run

## Four Buy Signals
| Signal | Condition |
|---|---|
| Extreme Fear | Fear & Greed < 10 |
| VIX Spike | VIX > 30 |
| S5FI Breadth | S5FI < 20 |
| 3 Red Days | SPY down 3 consecutive days |

## Running Locally
```bash
pip install -r requirements.txt
cp .env.example .env  # fill in keys
python main.py         # starts FastAPI + scheduler on :8000
```

## Manual Trigger
```bash
curl -X POST http://localhost:8000/api/run-now \
  -H "X-Admin-Token: <ADMIN_TOKEN>"
```

## Directory Layout
- `config/` — settings (Pydantic BaseSettings)
- `db/` — SQLAlchemy models + engine
- `data/` — market data fetchers
- `signals/` — 4-signal detector
- `portfolio/` — state, simulator, trailing stops
- `ai/` — prompt builder + Claude client
- `notifications/` — email + Telegram
- `scheduler/` — daily job orchestrator
- `web/` — FastAPI app, routes, Jinja2 templates
- `tests/` — unit tests (no API key needed)
- `data_cache/` — S5FI pickle, Fear/Greed cache, lock file
