"""
ai-strategy (:8002) - the LLM decision layer. Takes broker-gateway's
MarketContext and returns a TradeProposal; never generates or executes
code, never talks to Alpaca itself, never has execution access - chaos-
sandbox and risk-engine are the independent checks that keep this proposal
honest before anything real happens.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Must run before llm.py is imported - Settings() reads FEATHERLESS_* from
# os.environ at construction time. Docker doesn't need this (docker-compose's
# env_file already injects them), but a plain local `uvicorn main:app` does.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from fastapi import FastAPI  # noqa: E402

from contracts.schemas import MarketContext, TradeProposal  # noqa: E402
from llm import FeatherlessStrategyEngine, _hold_proposal  # noqa: E402

logger = logging.getLogger("ai-strategy")

app = FastAPI(title="ai-strategy")

engine = FeatherlessStrategyEngine()


@app.post("/generate-proposal", response_model=TradeProposal)
async def generate_proposal(market_context: MarketContext) -> TradeProposal:
    # generate_proposal() already turns every failure mode it knows about
    # (bad LLM output, a dead Featherless API, no eligible contracts) into a
    # safe HOLD - this is the last-resort net for anything it doesn't, e.g.
    # malformed upstream data (chain_summary is a loose, unvalidated dict).
    # An autonomous pipeline step failing outright is worse than a
    # conservative HOLD it can just try again next cycle.
    try:
        return await engine.generate_proposal(market_context)
    except Exception:
        logger.exception("generate_proposal crashed unexpectedly, defaulting to HOLD")
        return _hold_proposal(market_context.ticker, "internal error, defaulted to HOLD")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
