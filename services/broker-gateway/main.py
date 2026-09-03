"""
broker-gateway (:8001) - the only service that talks to Alpaca directly,
plus the HTTP surface over workflow/pipeline.py's orchestrator (runs.py) so
a run can be triggered/watched over the network instead of only from the
CLI entrypoint in workflow/pipeline.py.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Must run before alpaca_client is imported - it reads ALPACA_API_KEY etc.
# from os.environ at import time. Docker doesn't need this (docker-compose's
# env_file already injects them into the container), but a plain local
# `uvicorn main:app` does - .env sits at the repo root, three levels up.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from alpaca_client import AlpacaBrokerGateway, AlpacaCLIError  # noqa: E402
from contracts.schemas import ExecutionResponse, MarketContext, TradeProposal  # noqa: E402
from position_manager import manage_positions  # noqa: E402
from runs import router as runs_router  # noqa: E402
from trade_log import TradeLog  # noqa: E402

app = FastAPI(title="broker-gateway")

# Only matters once the frontend talks to this service directly from a
# browser (VITE_USE_MOCKS=false) - server-to-server callers (scheduler,
# workflow/pipeline.py) aren't subject to CORS at all.
_allowed_origins = [origin.strip() for origin in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(runs_router)

gateway = AlpacaBrokerGateway()
trade_log = TradeLog()


@app.exception_handler(AlpacaCLIError)
async def handle_alpaca_cli_error(_: Request, exc: AlpacaCLIError) -> JSONResponse:
    # Every gateway method can raise this (Alpaca itself rejecting a bad
    # symbol/order, the CLI binary missing, a timeout, ...) - one handler
    # instead of a try/except in every endpoint means none of them can
    # forget to catch it and leak an unhandled 500.
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.get("/market-context/{ticker}", response_model=MarketContext)
async def get_market_context(ticker: str) -> MarketContext:
    return await gateway.get_market_context(ticker.upper())


@app.post("/execute-order", response_model=ExecutionResponse)
async def execute_order(proposal: TradeProposal) -> ExecutionResponse:
    response = await gateway.execute_order(proposal)
    if proposal.action != "HOLD" and response.status != "NO_ACTION":
        # Records what we intended to pay (order_details' limit_price) at
        # submission time - execute_order returns right after submission,
        # often before a fill is confirmed, so a live "filled_avg_price" of
        # 0.0 isn't yet meaningful to log as the open price.
        details = proposal.order_details
        qty = float(details.get("quantity", details.get("qty", 1)))
        price = float(details.get("limit_price", response.filled_avg_price))
        await trade_log.record_open(proposal.symbol, qty, price, response.order_id)
    return response


@app.get("/positions")
async def list_positions() -> list[dict]:
    return await gateway.list_positions()


@app.post("/positions/manage")
async def manage_positions_endpoint() -> list[dict]:
    # workflow/scheduler.py calls this once per autonomous cycle alongside
    # triggering new-entry runs - deterministic take-profit/stop-loss/
    # expiring-soon rules, no LLM, no risk-engine/chaos-sandbox involved
    # (closing an existing position is risk-reducing, not a new bet).
    return await manage_positions(gateway, trade_log)


@app.get("/trades")
async def list_trades(limit: int = 100) -> list[dict]:
    return await trade_log.recent(limit)


@app.get("/pnl")
async def get_pnl() -> dict:
    return await trade_log.pnl_summary()


@app.get("/account")
async def get_account() -> dict:
    # snake_case, matching Alpaca's own field names and the project's
    # backend-to-backend convention (contracts/schemas.py) - unlike
    # /runs/*, nothing here needs a frontend-camelCase translation: the
    # frontend dropped its Portfolio/balance screens and never calls this
    # endpoint, and risk-engine (a backend service, per CLAUDE.md's own
    # "call broker-gateway's GET /account" note) is the real consumer.
    # Money fields come back as strings (Alpaca's wire format), converted
    # to float here at the boundary.
    account = await gateway.get_account()
    return {
        "status": account["status"],
        "account_number": account["account_number"],
        "currency": account["currency"],
        "portfolio_value": float(account["portfolio_value"]),
        "cash": float(account["cash"]),
        "buying_power": float(account["buying_power"]),
        "options_trading_level": account["options_trading_level"],
    }


@app.get("/clock")
async def get_clock() -> dict:
    # workflow/scheduler.py polls this before triggering a run - keeps "only
    # broker-gateway talks to Alpaca directly" true even for the autonomous
    # loop, instead of it opening its own Alpaca connection just for this.
    clock = await gateway.get_clock()
    return {
        "isOpen": clock["is_open"],
        "timestamp": clock["timestamp"],
        "nextOpen": clock["next_open"],
        "nextClose": clock["next_close"],
    }


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
