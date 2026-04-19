import json
from datetime import date

from ai.prompt_builder import build_system_prompt, build_user_prompt


def test_system_prompt_contains_rules():
    p = build_system_prompt()
    assert "25%" in p
    assert "20%" in p
    assert "STRICT JSON" in p
    assert "trailing_stop" in p.lower()


def test_user_prompt_contains_all_sections():
    p = build_user_prompt(
        today=date(2026, 4, 18),
        portfolio_state={"cash": 10000, "total_nav": 10000, "positions": []},
        signal_result={"extreme_fear": False, "active_count": 0},
        market_context={"vix": 15.0},
        asset_universe={"AAPL": 180.0},
        recent_decisions=[{"date": "2026-04-17", "action": "HOLD"}],
        stop_events_today=[],
    )
    assert "Portfolio State" in p
    assert "Signal Evaluation" in p
    assert "Available Universe" in p
    assert "Prior Decisions" in p
    assert "2026-04-18" in p


def test_user_prompt_json_parseable_blocks():
    # ensure each JSON block we embed is actually valid
    state = {"cash": 10000}
    p = build_user_prompt(
        today=date(2026, 4, 18),
        portfolio_state=state,
        signal_result={"a": 1},
        market_context={"vix": 15},
        asset_universe={"AAPL": 1.0},
        recent_decisions=[],
        stop_events_today=[],
    )
    assert json.dumps(state, indent=2) in p
