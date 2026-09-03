"""LLM decision layer - Featherless (OpenAI-compatible) picks a contract and
a direction only. Every number in the resulting TradeProposal (strike, IV,
bid/ask, days to expiry) is looked up from the real market data the model
was shown, never taken from the model's own arithmetic - it can be wrong
about which contract looks good, it can't be wrong about what that contract
actually costs.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Literal, Optional

from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel, Field, ValidationError

from contracts.interfaces import BaseStrategyEngine
from contracts.schemas import MarketContext, TradeProposal

from settings import Settings

logger = logging.getLogger("ai-strategy")

SYSTEM_PROMPT = """You are the strategy engine of an autonomous options trading system.

You analyze real market data for one ticker and decide whether to buy a single option
contract (a call or a put) or do nothing this cycle. You do not execute trades yourself -
a separate deterministic risk system has final veto power over anything you propose, so
give your honest, best-effort read of the data rather than hedging your answer.

The contracts you're shown are deliberately all deep in-the-money and several months
out - this system's risk gate stress-tests every proposal against a sharp adverse move,
and only contracts that behave close to owning the underlying itself (rather than a
highly leveraged bet) can realistically survive that test. Pick the direction and
contract, don't second-guess why every option offered is deep ITM.

Respond with a single JSON object and nothing else, matching exactly this shape:
{
  "action": "BUY" or "HOLD",
  "contract_symbol": the exact "symbol" string of one contract from the list you were given (required if action is "BUY", omit or null if "HOLD"),
  "conviction_score": a number from 0.0 to 1.0,
  "reasoning": one or two sentences explaining the call
}

Rules:
- Only ever propose "BUY" (buying a call for a bullish view, or a put for a bearish
  view) - never "SELL", this system has no short-option support.
- "HOLD" is a completely valid, often correct answer when nothing in the data stands out.
- contract_symbol must be copied exactly from the list you're given - never invent one.
- Base your reasoning only on the numbers you're given (spot price, IV, delta, bid/ask,
  days to expiry) - do not invent news, earnings, or events you have no data for.
"""


class _LLMDecision(BaseModel):
    """What we actually ask the model to produce - deliberately minimal."""

    action: Literal["BUY", "HOLD"]
    contract_symbol: Optional[str] = None
    conviction_score: float = Field(ge=0, le=1)
    reasoning: str


def _target_strike(spot_price: float, option_type: str, target_itm_pct: float) -> float:
    return spot_price * (1 - target_itm_pct) if option_type == "call" else spot_price * (1 + target_itm_pct)


def _best_per_strike(contracts: list[dict]) -> list[dict]:
    """One contract per distinct strike, keeping whichever expiration is
    longest-dated - more time value cushion means more margin under
    chaos-sandbox's stress test, not just barely clearing it. Without this,
    a single strike listed across many expirations (common for real chains)
    would crowd out genuinely different strikes from the ranked result."""
    best: dict[float, dict] = {}
    for c in contracts:
        current = best.get(c["strike"])
        if current is None or c["days_to_expiry"] > current["days_to_expiry"]:
            best[c["strike"]] = c
    return list(best.values())


def _select_contracts_for_prompt(context: MarketContext, settings: Settings) -> list[dict]:
    """Deep-ITM, long-dated candidates only - a near-the-money or short-dated
    option is mathematically guaranteed to fail chaos-sandbox's ADVERSE_MOVE
    veto (verified with the real pricing model before writing this, see
    settings.py's comment), so there's no point ever offering those to the
    model. Ranks by closeness to target_itm_pct ITM (25% by default),
    balanced evenly between calls (strike below spot) and puts (strike
    above spot) so the model has a genuine bullish-or-bearish choice - not
    just whichever side happened to have a strike land closer to target."""
    contracts = context.chain_summary.get("contracts", [])
    # chaos-sandbox's OptionStressInputs requires implied_volatility as a
    # real, strictly-positive float and ask >= bid > 0 - Alpaca genuinely
    # returns implied_volatility=None (and zeroed Greeks) for some illiquid
    # contracts (confirmed live), and a crossed/zero quote is always
    # possible on a thin market. Filtering here means an unlucky pick can
    # never reach chaos-sandbox and crash the pipeline with a 422 instead
    # of a clean HOLD.
    usable = [
        c
        for c in contracts
        if c.get("bid") is not None
        and c.get("ask") is not None
        and c.get("implied_volatility") is not None
        and c["ask"] > 0
        and c["ask"] >= c["bid"]
    ]
    eligible = [c for c in usable if c["days_to_expiry"] >= settings.min_days_to_expiry]
    if not eligible:
        return []

    half = max(1, settings.contracts_in_prompt // 2)
    calls = _best_per_strike([c for c in eligible if c["option_type"] == "call"])
    puts = _best_per_strike([c for c in eligible if c["option_type"] == "put"])
    calls.sort(key=lambda c: abs(c["strike"] - _target_strike(context.spot_price, "call", settings.target_itm_pct)))
    puts.sort(key=lambda c: abs(c["strike"] - _target_strike(context.spot_price, "put", settings.target_itm_pct)))
    return calls[:half] + puts[:half]


def _build_user_message(context: MarketContext, contracts: list[dict]) -> str:
    simplified = [
        {
            "symbol": c["symbol"],
            "option_type": c["option_type"],
            "strike": c["strike"],
            "days_to_expiry": c["days_to_expiry"],
            "bid": c["bid"],
            "ask": c["ask"],
            "implied_volatility": c["implied_volatility"],
            "delta": (c.get("greeks") or {}).get("delta"),
        }
        for c in contracts
    ]
    payload = {
        "ticker": context.ticker,
        "spot_price": context.spot_price,
        "implied_volatility": context.implied_volatility,
        "contracts": simplified,
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


def _hold_proposal(ticker: str, reason: str) -> TradeProposal:
    return TradeProposal(
        strategy_id=str(uuid.uuid4()),
        action="HOLD",
        symbol=ticker,
        generated_code="",
        conviction_score=0.0,
        order_details={"reasoning": reason},
    )


class FeatherlessStrategyEngine(BaseStrategyEngine):
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or Settings()
        self._client = AsyncOpenAI(
            api_key=self.settings.featherless_api_key, base_url=self.settings.featherless_base_url
        )

    async def _ask_llm(self, messages: list[dict]) -> _LLMDecision:
        response = await self._client.chat.completions.create(
            model=self.settings.featherless_model, messages=messages, temperature=0.3
        )
        if not response.choices:
            raise ValueError("LLM response had no choices (possibly content-filtered)")
        return _LLMDecision.model_validate_json(_extract_json(response.choices[0].message.content))

    async def generate_proposal(self, market_context: MarketContext) -> TradeProposal:
        contracts = _select_contracts_for_prompt(market_context, self.settings)
        if not contracts:
            return _hold_proposal(market_context.ticker, "no contracts with a live bid/ask in the fetched chain")

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_message(market_context, contracts)},
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

        if decision.action == "HOLD" or decision.contract_symbol is None:
            return _hold_proposal(market_context.ticker, decision.reasoning)

        contract = next((c for c in contracts if c["symbol"] == decision.contract_symbol), None)
        if contract is None:
            logger.warning("LLM picked a contract not in the offered list: %s", decision.contract_symbol)
            return _hold_proposal(
                market_context.ticker, f"model picked an unlisted contract ({decision.contract_symbol})"
            )

        return TradeProposal(
            strategy_id=str(uuid.uuid4()),
            action="BUY",
            symbol=contract["symbol"],
            generated_code="",
            conviction_score=decision.conviction_score,
            # Only chaos-sandbox's exact OptionStressInputs field list - no
            # symbol/direction/description/reasoning here, those collide
            # with its extra="forbid" schema (verified live, see CLAUDE.md).
            order_details={
                "option_type": contract["option_type"],
                "quantity": 1,
                "limit_price": contract["ask"],
                "spot_price": market_context.spot_price,
                "strike": contract["strike"],
                "implied_volatility": contract["implied_volatility"],
                "days_to_expiry": contract["days_to_expiry"],
                "bid": contract["bid"],
                "ask": contract["ask"],
            },
        )
