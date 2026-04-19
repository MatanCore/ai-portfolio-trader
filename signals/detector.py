"""Pure signal evaluation — takes raw market data, returns a SignalResult."""
from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class SignalResult:
    extreme_fear: bool
    vix_spike: bool
    s5fi_breadth: bool
    three_red_days: bool

    fear_greed_value: float | None
    vix_value: float | None
    s5fi_value: float | None
    spy_3_day_red: bool

    @property
    def active_count(self) -> int:
        return sum([self.extreme_fear, self.vix_spike, self.s5fi_breadth, self.three_red_days])

    def to_dict(self) -> dict:
        d = asdict(self)
        d["active_count"] = self.active_count
        return d

    def summary(self) -> str:
        parts = []
        if self.extreme_fear:
            parts.append(f"Extreme Fear (F&G={self.fear_greed_value:.0f})")
        if self.vix_spike:
            parts.append(f"VIX Spike (VIX={self.vix_value:.1f})")
        if self.s5fi_breadth:
            parts.append(f"S5FI Breadth Washout (S5FI={self.s5fi_value:.1f})")
        if self.three_red_days:
            parts.append("3 Red Days on SPY")
        if not parts:
            return "No active buy signals"
        return " | ".join(parts)


def evaluate_signals(
    fear_greed_value: float | None,
    vix_value: float | None,
    s5fi_value: float | None,
    spy_three_red: bool,
) -> SignalResult:
    return SignalResult(
        extreme_fear=(fear_greed_value is not None and fear_greed_value < 10),
        vix_spike=(vix_value is not None and vix_value > 30),
        s5fi_breadth=(s5fi_value is not None and s5fi_value < 20),
        three_red_days=bool(spy_three_red),
        fear_greed_value=fear_greed_value,
        vix_value=vix_value,
        s5fi_value=s5fi_value,
        spy_3_day_red=bool(spy_three_red),
    )
