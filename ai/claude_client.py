"""Claude client — uses claude-agent-sdk (local auth via Claude Code).

This routes calls through the user's Claude Pro/Max subscription via Claude Code's
bundled CLI, avoiding paid API billing. One-shot, no tools, JSON response expected.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Literal

import anyio
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)
from pydantic import BaseModel, Field, ValidationError, confloat

from config.settings import settings

logger = logging.getLogger(__name__)


class PositionSchema(BaseModel):
    ticker: str
    strategy: Literal["BREAKOUT", "CONSOLIDATION_BREAKOUT", "TREND_CONTINUATION", "OVERSOLD_REVERSAL", "EVENT_MOMENTUM"]
    entry_reason: str
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    risk_level: Literal["low", "medium", "high"]
    risk_pct: confloat(ge=1.0, le=3.0) = 2.0
    confidence: confloat(ge=0.0, le=1.0)


class WatchlistItem(BaseModel):
    ticker: str
    setup: str
    trigger: str
    notes: str = ""


class DecisionSchema(BaseModel):
    action: Literal["BUY", "SELL", "HOLD"]
    confidence: confloat(ge=0.0, le=1.0) = Field(...)
    positions: list[PositionSchema] = []
    watchlist: list[WatchlistItem] = []
    reasoning: str


@dataclass
class ClaudeResult:
    decision: DecisionSchema
    raw_text: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    duration_seconds: float


def _extract_json(text: str) -> str:
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        return fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return text.strip()


async def _query_claude(system: str, user: str) -> tuple[str, dict]:
    """Run one query via the local Claude Code session, return (text, usage)."""
    options = ClaudeAgentOptions(
        system_prompt=system,
        max_turns=1,
        allowed_tools=[],  # pure text response, no tool calls
        model=settings.claude_model if settings.claude_model else None,
    )

    text_parts: list[str] = []
    usage: dict = {}

    async for message in query(prompt=user, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    text_parts.append(block.text)
        elif isinstance(message, ResultMessage):
            # ResultMessage carries cost/usage info — attribute names vary by SDK version
            for attr in ("usage", "total_tokens_input", "input_tokens", "total_cost_usd"):
                if hasattr(message, attr):
                    val = getattr(message, attr)
                    if attr == "usage" and isinstance(val, dict):
                        usage.update(val)
                    else:
                        usage[attr] = val

    return "".join(text_parts), usage


def _extract_usage_counts(usage: dict) -> tuple[int, int, int, int]:
    """Return (input_tokens, output_tokens, cache_read, cache_creation) from SDK usage dict."""
    input_tok = (
        usage.get("input_tokens")
        or usage.get("total_tokens_input")
        or (usage.get("usage", {}) or {}).get("input_tokens")
        or 0
    )
    output_tok = (
        usage.get("output_tokens")
        or usage.get("total_tokens_output")
        or (usage.get("usage", {}) or {}).get("output_tokens")
        or 0
    )
    cache_read = usage.get("cache_read_input_tokens", 0) or 0
    cache_creation = usage.get("cache_creation_input_tokens", 0) or 0
    return int(input_tok or 0), int(output_tok or 0), int(cache_read or 0), int(cache_creation or 0)


def get_decision(system_prompt: str, user_prompt: str) -> ClaudeResult:
    """Synchronous entry point — wraps the async SDK call via anyio.run.

    Retries once on JSON parse / validation failure with a stricter reminder.
    Safe to call from a threadpool (FastAPI BackgroundTasks / APScheduler threads).
    """
    start = time.time()
    last_err: Exception | None = None
    raw_text = ""
    usage: dict = {}
    decision: DecisionSchema | None = None

    current_user = user_prompt
    for attempt in range(2):
        try:
            text, u = anyio.run(_query_claude, system_prompt, current_user)
            raw_text = text
            usage = u
            payload = _extract_json(text)
            data = json.loads(payload)
            decision = DecisionSchema.model_validate(data)
            break
        except (json.JSONDecodeError, ValidationError) as e:
            last_err = e
            logger.warning(f"Claude response invalid (attempt {attempt + 1}): {e}")
            current_user = (
                user_prompt
                + "\n\nREMINDER: Return STRICT JSON only. No prose, no markdown, no code fences."
            )
            continue
        except Exception as e:
            last_err = e
            logger.warning(f"Claude SDK error (attempt {attempt + 1}): {e}")
            time.sleep(2)

    if decision is None:
        raise RuntimeError(f"Claude decision failed after retry: {last_err}")

    in_tok, out_tok, cache_r, cache_c = _extract_usage_counts(usage)
    return ClaudeResult(
        decision=decision,
        raw_text=raw_text,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cache_read_tokens=cache_r,
        cache_creation_tokens=cache_c,
        duration_seconds=time.time() - start,
    )
