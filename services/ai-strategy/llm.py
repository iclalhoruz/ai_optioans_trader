"""LLM decision layer - Featherless (OpenAI-compatible) picks a direction and
a spread only. Every number in the resulting TradeProposal (strikes, IV,
bid/ask, days to expiry, net debit) is looked up from the real market data
the model was shown, never taken from the model's own arithmetic - it can be
wrong about which spread looks good, it can't be wrong about what that
spread actually costs.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Literal, Optional

import httpx
from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel, Field, ValidationError

from contracts.interfaces import BaseStrategyEngine
from contracts.schemas import MarketContext, TradeProposal

from settings import Settings

logger = logging.getLogger("ai-strategy")

SYSTEM_PROMPT = """You are the strategy engine of an autonomous options trading system.

You analyze real market data for one ticker and decide whether to buy a defined-risk
vertical spread (a bull call spread for a bullish view, or a bear put spread for a
bearish view) or do nothing this cycle. You do not execute trades yourself - a separate
deterministic risk system has final veto power over anything you propose, so give your
honest, best-effort read of the data rather than hedging your answer.

Each spread you're shown has a long leg (deep in-the-money - this system's risk gate
stress-tests every proposal against a sharp adverse move, and only a deep-ITM long leg
survives that realistically) and a short leg that funds part of the cost and caps the
maximum loss at the net debit paid. Don't second-guess why the legs are structured this
way - just decide whether the underlying's setup and trend support a bullish or bearish
bet, or neither.

You're also given recent price trend data for the underlying (percent change over the
last 5 and 20 trading days, position relative to the recent high/low, and realized
volatility). Use it as real evidence for your directional view instead of guessing.
Don't hold out for an unusually strong or obvious trend before acting - a modest but
real lean (a consistent 5-day and 20-day move in the same direction, or sitting clearly
toward one end of the recent high/low range) is real evidence and is enough to act on.
You are not the only safeguard here: a deterministic risk engine independently checks
position size, portfolio delta, and a worst-case stress test on every proposal you make
and can veto it regardless of your conviction, so lean toward giving your honest
directional read rather than defaulting to "HOLD" whenever the picture isn't perfectly
clean.

Respond with a single JSON object and nothing else, matching exactly this shape:
{
  "action": "BUY" or "HOLD",
  "spread_id": the exact "spread_id" string of one spread from the list you were given (required if action is "BUY", omit or null if "HOLD"),
  "conviction_score": a number from 0.0 to 1.0,
  "reasoning": one or two sentences explaining the call
}

Rules:
- Only ever propose "BUY" (a bull call spread or a bear put spread) - never "SELL",
  this system has no short-margin/naked-selling support.
- "HOLD" is a completely valid, often correct answer when nothing in the data stands out.
- spread_id must be copied exactly from the list you're given - never invent one.
- Base your reasoning only on the numbers you're given (spot price, IV, trend, the
  spread's net debit and max gain) - do not invent news, earnings, or events you have
  no data for.
"""


class _LLMDecision(BaseModel):
    """What we actually ask the model to produce - deliberately minimal."""

    action: Literal["BUY", "HOLD"]
    spread_id: Optional[str] = None
    conviction_score: float = Field(ge=0, le=1)
    reasoning: str


def _usable_contracts(context: MarketContext) -> list[dict]:
    """chaos-sandbox's SpreadLegInputs (like OptionStressInputs before it)
    requires implied_volatility as a real, strictly-positive float and
    ask >= bid > 0 - Alpaca genuinely returns implied_volatility=None (and
    zeroed Greeks) for some illiquid contracts (confirmed live), and a
    crossed/zero quote is always possible on a thin market. Filtering here
    means an unlucky pick can never reach chaos-sandbox and crash the
    pipeline with a 422 instead of a clean HOLD."""
    contracts = context.chain_summary.get("contracts", [])
    return [
        c
        for c in contracts
        if c.get("bid") is not None
        and c.get("ask") is not None
        and c.get("implied_volatility") is not None
        and c["ask"] > 0
        and c["ask"] >= c["bid"]
    ]


def _build_spread_candidate(
    option_type: Literal["call", "put"], pool_by_expiry: dict[int, list[dict]], spot_price: float, settings: Settings
) -> Optional[dict]:
    """One candidate spread for this option_type: the expiration closest to
    spread_target_days_to_expiry, a long leg near spread_long_itm_pct ITM,
    and a short leg roughly spread_width_pct of spot further out (away from
    the money) on the same expiration - chaos-sandbox's SpreadStressInputs
    requires every leg to share one days_to_expiry for a debit spread.

    Real strike increments (e.g. $10 apart for AAPL's far-dated chain) are
    coarser than a naive width target - checked live and found the nearest
    available short strike sometimes left almost no width beyond the net
    debit (a real case: $9.47 debit on a $10-wide spread, $0.53 max gain,
    an unusably bad risk/reward). So this doesn't just take the nearest
    strike to the target width - it walks short-strike candidates ordered
    by closeness to the target width and keeps the first one whose net
    debit doesn't eat past spread_max_debit_to_width_ratio of the width.
    """
    if not pool_by_expiry:
        return None

    best_dte = min(pool_by_expiry, key=lambda dte: abs(dte - settings.spread_target_days_to_expiry))
    pool = pool_by_expiry[best_dte]

    long_target = spot_price * (1 - settings.spread_long_itm_pct if option_type == "call" else 1 + settings.spread_long_itm_pct)
    long_leg = min(pool, key=lambda c: abs(c["strike"] - long_target))

    width_target = spot_price * settings.spread_width_pct
    if option_type == "call":
        # Short leg must sit strictly further OTM than the long leg - only
        # strikes above it are a valid bull call spread.
        same_side = [c for c in pool if c["strike"] > long_leg["strike"]]
        short_candidates = sorted(same_side, key=lambda c: abs((c["strike"] - long_leg["strike"]) - width_target))
    else:
        same_side = [c for c in pool if c["strike"] < long_leg["strike"]]
        short_candidates = sorted(same_side, key=lambda c: abs((long_leg["strike"] - c["strike"]) - width_target))

    for short_leg in short_candidates:
        width = abs(short_leg["strike"] - long_leg["strike"])
        net_debit = long_leg["ask"] - short_leg["bid"]
        if net_debit <= 0 or net_debit > width * settings.spread_max_debit_to_width_ratio:
            continue
        return {
            "spread_id": f"{option_type}_{long_leg['strike']:.0f}_{short_leg['strike']:.0f}_{best_dte}d",
            "direction": "bullish" if option_type == "call" else "bearish",
            "option_type": option_type,
            "long_leg": long_leg,
            "short_leg": short_leg,
            "days_to_expiry": best_dte,
            "net_debit": net_debit,
            "max_gain": width - net_debit,
        }
    return None


def _select_spread_candidates(context: MarketContext, settings: Settings) -> list[dict]:
    """Up to two candidates - one bull call spread, one bear put spread -
    so the model has a genuine bullish-or-bearish choice, or neither."""
    usable = _usable_contracts(context)
    eligible = [c for c in usable if c["days_to_expiry"] >= settings.spread_min_days_to_expiry]

    candidates = []
    for option_type in ("call", "put"):
        pool_by_expiry: dict[int, list[dict]] = {}
        for c in eligible:
            if c["option_type"] == option_type:
                pool_by_expiry.setdefault(c["days_to_expiry"], []).append(c)
        candidate = _build_spread_candidate(option_type, pool_by_expiry, context.spot_price, settings)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _build_user_message(context: MarketContext, candidates: list[dict]) -> str:
    simplified = [
        {
            "spread_id": c["spread_id"],
            "direction": c["direction"],
            "long_leg_symbol": c["long_leg"]["symbol"],
            "long_strike": c["long_leg"]["strike"],
            "short_leg_symbol": c["short_leg"]["symbol"],
            "short_strike": c["short_leg"]["strike"],
            "days_to_expiry": c["days_to_expiry"],
            "net_debit_per_contract": round(c["net_debit"], 2),
            "max_gain_per_contract": round(c["max_gain"], 2),
        }
        for c in candidates
    ]
    payload = {
        "ticker": context.ticker,
        "spot_price": context.spot_price,
        "implied_volatility": context.implied_volatility,
        "price_trend": context.chain_summary.get("price_trend") or {},
        "spreads": simplified,
    }
    return json.dumps(payload, indent=2)


def _extract_json(content: Optional[str]) -> str:
    """Strips a markdown code fence if the model wrapped its JSON in one
    despite being told not to - cheap insurance, real models do this."""
    if not content:
        raise ValueError("empty LLM response")
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


def _size_quantity(portfolio_value: float, conviction_score: float, cost_per_contract: float, settings: Settings) -> int:
    """How many spreads to buy - scales with both the model's conviction
    and the real portfolio value instead of always proposing exactly 1
    regardless of either. Deliberately conservative (TARGET_ALLOCATION_PCT
    default 3%, well under risk-engine's 5% MAX_ALLOCATION_PCT cap) so
    sizing itself isn't why a reasonable proposal gets vetoed downstream."""
    budget = portfolio_value * settings.target_allocation_pct * conviction_score
    quantity = int(budget // (cost_per_contract * 100))
    return min(quantity, settings.max_contracts_per_trade)


def _hold_proposal(ticker: str, reason: str, conviction_score: float = 0.0) -> TradeProposal:
    """conviction_score defaults to 0.0 for the cases where no real model
    decision exists to report (no candidates, LLM call/parse failed twice,
    an invalid spread_id) - but callers that DO have a real _LLMDecision
    should pass its actual conviction_score through instead of discarding
    it. risk-engine never gates on this for a HOLD (nothing to veto), so
    this number is purely for the dashboard's "AI Reasoning" panel to show
    the model's genuine confidence in its own "nothing to do" call."""
    return TradeProposal(
        strategy_id=str(uuid.uuid4()),
        action="HOLD",
        symbol=ticker,
        generated_code="",
        conviction_score=conviction_score,
        order_details={"reasoning": reason},
    )


def _leg_order_details(leg: dict, side: Literal["buy", "sell"]) -> dict:
    return {
        "symbol": leg["symbol"],
        "option_type": leg["option_type"],
        "strike": leg["strike"],
        "implied_volatility": leg["implied_volatility"],
        "days_to_expiry": leg["days_to_expiry"],
        "bid": leg["bid"],
        "ask": leg["ask"],
        "ratio_qty": 1,
        "side": side,
        "position_intent": "buy_to_open" if side == "buy" else "sell_to_open",
    }


class FeatherlessStrategyEngine(BaseStrategyEngine):
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or Settings()
        self._client = AsyncOpenAI(
            api_key=self.settings.featherless_api_key, base_url=self.settings.featherless_base_url
        )
        self._http = httpx.AsyncClient()

    async def _fetch_portfolio_value(self) -> Optional[float]:
        try:
            response = await self._http.get(f"{self.settings.broker_gateway_url}/account", timeout=10.0)
            response.raise_for_status()
            return float(response.json()["portfolio_value"])
        except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
            # broker-gateway being briefly unreachable shouldn't block a
            # trade the model already decided on - fall back to sizing
            # conservatively (1 spread) rather than aborting the proposal.
            logger.warning("couldn't fetch portfolio_value for sizing, defaulting to 1 spread: %s", exc)
            return None

    async def _ask_llm(self, messages: list[dict]) -> _LLMDecision:
        response = await self._client.chat.completions.create(
            model=self.settings.featherless_model, messages=messages, temperature=0.3
        )
        if not response.choices:
            raise ValueError("LLM response had no choices (possibly content-filtered)")
        return _LLMDecision.model_validate_json(_extract_json(response.choices[0].message.content))

    async def generate_proposal(self, market_context: MarketContext) -> TradeProposal:
        candidates = _select_spread_candidates(market_context, self.settings)
        if not candidates:
            return _hold_proposal(market_context.ticker, "no viable bull call or bear put spread in the fetched chain")

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_message(market_context, candidates)},
        ]

        decision: Optional[_LLMDecision] = None
        last_error: Optional[Exception] = None
        for attempt in range(2):
            try:
                decision = await self._ask_llm(messages)
                break
            except OpenAIError as exc:
                # The API call itself failed (network, rate limit, auth,
                # provider outage, ...) - retry the same request as-is,
                # there's no "correction" to send back for a transport
                # failure the way there is for a malformed JSON body.
                last_error = exc
                logger.warning("Featherless API call failed (attempt %d/2): %s", attempt + 1, exc)
            except (ValidationError, ValueError, IndexError) as exc:
                last_error = exc
                logger.warning("LLM output invalid (attempt %d/2): %s", attempt + 1, exc)
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"That response wasn't valid JSON matching the required shape "
                            f"({exc}). Respond with ONLY the corrected JSON object."
                        ),
                    }
                )

        if decision is None:
            return _hold_proposal(
                market_context.ticker, f"LLM call/output failed twice, defaulting to HOLD: {last_error}"
            )

        if decision.action == "HOLD" or decision.spread_id is None:
            return _hold_proposal(market_context.ticker, decision.reasoning, decision.conviction_score)

        candidate = next((c for c in candidates if c["spread_id"] == decision.spread_id), None)
        if candidate is None:
            logger.warning("LLM picked a spread not in the offered list: %s", decision.spread_id)
            return _hold_proposal(market_context.ticker, f"model picked an unlisted spread ({decision.spread_id})")

        portfolio_value = await self._fetch_portfolio_value()
        quantity = (
            _size_quantity(portfolio_value, decision.conviction_score, candidate["net_debit"], self.settings)
            if portfolio_value is not None
            else 1
        )
        if quantity < 1:
            return _hold_proposal(
                market_context.ticker,
                f"{candidate['spread_id']} too expensive for current risk budget "
                f"(portfolio_value=${portfolio_value:,.0f}, conviction={decision.conviction_score:.2f})",
                decision.conviction_score,
            )

        return TradeProposal(
            strategy_id=str(uuid.uuid4()),
            action="BUY",
            # The underlying ticker, not an option symbol - chaos-sandbox's
            # spread handling cross-checks every leg's OCC symbol against
            # this field (option_underlying(leg.option_symbol) == symbol).
            symbol=market_context.ticker,
            generated_code="",
            conviction_score=decision.conviction_score,
            # Matches chaos-sandbox's SpreadStressInputs exactly - direction,
            # quantity, a positive net debit, spot_price, and 2-4 legs, each
            # with its own real strike/IV/DTE/bid/ask. No symbol/description/
            # reasoning at this level or per-leg - extra="forbid" on both
            # models rejects anything not in their own field list.
            order_details={
                "direction": candidate["direction"],
                "quantity": quantity,
                "limit_price": round(candidate["net_debit"], 2),
                "spot_price": market_context.spot_price,
                "legs": [
                    _leg_order_details(candidate["long_leg"], "buy"),
                    _leg_order_details(candidate["short_leg"], "sell"),
                ],
            },
        )
