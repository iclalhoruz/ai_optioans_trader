"""
Real Alpaca integration - the only place in the whole system that talks to
Alpaca directly. Goes through Alpaca's own official CLI (github.com/alpacahq/cli)
rather than the alpaca-py SDK: the hackathon's rules require the project to
genuinely utilize either Alpaca's MCP server or its CLI tools, and the MCP
server's own docs (docs.alpaca.markets/us/docs/alpaca-mcp-server) describe it
as built for AI chat clients (Claude Desktop, Cursor, VS Code, ...), not a
plain backend service like this one - the CLI, on the other hand, is
explicitly built "for AI agents, scripts, and automation pipelines," which is
exactly what this is. Implements BaseBrokerGateway (contracts/interfaces.py)
so every other service only ever depends on contracts/, never on Alpaca.

Every command/flag/response shape here was checked against the real `alpaca`
binary (v0.0.14) run live against a real paper account - including its error
shape (non-zero exit, JSON error object on stderr) - not guessed from docs.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from datetime import datetime, timezone

from contracts.interfaces import BaseBrokerGateway
from contracts.schemas import ExecutionResponse, MarketContext, TradeProposal

# How far around the spot price to pull strikes for chain_summary - a full
# chain can be hundreds of contracts, ai-strategy only needs the ones near
# the money to reason about.
STRIKE_WINDOW = 10.0

# `alpaca data option chain` paginates past 100 results by default, and its
# own server-side max is 1000. A fixed --limit isn't safe on its own - SPY
# and QQQ (both in the default watchlist) came back with 834 and 748
# contracts respectively in just a +-10 strike window (checked live), so
# _fetch_option_chain below always follows next_page_token instead of
# trusting one call to have everything.
CHAIN_PAGE_LIMIT = 1000


class AlpacaCLIError(Exception):
    """The `alpaca` CLI reported a failure - either Alpaca itself rejected
    the request or the CLI rejected malformed input. Carries the same
    status_code/message shape main.py maps to a clean HTTP error."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class AlpacaBrokerGateway(BaseBrokerGateway):
    def __init__(self) -> None:
        # The CLI reads these two straight from the environment (confirmed
        # via `alpaca doctor`) - same vars alpaca-py used, nothing new to
        # configure. Failing fast here beats a cryptic CLI error later.
        if "ALPACA_API_KEY" not in os.environ or "ALPACA_SECRET_KEY" not in os.environ:
            raise RuntimeError("ALPACA_API_KEY / ALPACA_SECRET_KEY must be set")

    async def _cli(self, *args: str) -> dict:
        """Runs `alpaca <args>` and returns its parsed JSON. Verified live:
        on success the result JSON goes to stdout with exit code 0; on
        failure a JSON error object goes to stderr with a non-zero exit."""
        try:
            result = await asyncio.to_thread(
                subprocess.run, ["alpaca", *args], capture_output=True, text=True, timeout=30
            )
        except subprocess.TimeoutExpired as exc:
            raise AlpacaCLIError(504, f"alpaca CLI timed out: {' '.join(args)}") from exc
        except FileNotFoundError as exc:
            raise AlpacaCLIError(500, "alpaca CLI binary not found on PATH - is it installed?") from exc

        if result.returncode != 0:
            try:
                error = json.loads(result.stderr)
                raise AlpacaCLIError(error.get("status") or 400, error.get("error", result.stderr))
            except json.JSONDecodeError:
                raise AlpacaCLIError(500, result.stderr.strip() or "alpaca CLI failed with no output")
        return json.loads(result.stdout)

    async def _fetch_option_chain(self, ticker: str, low: float, high: float) -> dict:
        """Follows next_page_token until it's empty - a single call can't be
        trusted to have the whole chain (see CHAIN_PAGE_LIMIT's comment)."""
        snapshots: dict = {}
        page_token: str | None = None
        while True:
            args = [
                "data", "option", "chain",
                "--underlying-symbol", ticker,
                "--strike-price-gte", str(low),
                "--strike-price-lte", str(high),
                "--limit", str(CHAIN_PAGE_LIMIT),
            ]
            if page_token:
                args += ["--page-token", page_token]
            page = await self._cli(*args)
            snapshots.update(page.get("snapshots", {}))
            page_token = page.get("next_page_token")
            if not page_token:
                return snapshots

    async def get_market_context(self, ticker: str) -> MarketContext:
        trade = await self._cli("data", "latest-trade", "--symbol", ticker)
        spot_price = float(trade["trade"]["p"])

        snapshots = await self._fetch_option_chain(ticker, spot_price - STRIKE_WINDOW, spot_price + STRIKE_WINDOW)

        contracts = []
        ivs = []
        for symbol, snapshot in snapshots.items():
            iv = snapshot.get("impliedVolatility")
            if iv is not None:
                ivs.append(iv)
            quote = snapshot.get("latestQuote") or {}
            contracts.append(
                {
                    "symbol": symbol,
                    "bid": quote.get("bp"),
                    "ask": quote.get("ap"),
                    "implied_volatility": iv,
                    "greeks": snapshot.get("greeks"),
                }
            )

        # Representative IV for the top-level field - average across the
        # near-the-money window rather than picking one arbitrary contract.
        implied_volatility = sum(ivs) / len(ivs) if ivs else 0.0

        return MarketContext(
            ticker=ticker,
            spot_price=spot_price,
            implied_volatility=implied_volatility,
            chain_summary={"contracts": contracts},
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    async def execute_order(self, proposal: TradeProposal) -> ExecutionResponse:
        # The pipeline always calls execute-order as its last step once
        # risk-engine approves - a HOLD proposal can reach here with nothing
        # to actually place, so it's handled as a real, valid outcome
        # instead of trying (and failing) to submit a broken order.
        if proposal.action == "HOLD":
            return ExecutionResponse(
                status="NO_ACTION",
                order_id="none",
                filled_avg_price=0.0,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        details = proposal.order_details
        qty = str(details.get("quantity", details.get("qty", 1)))
        time_in_force = details.get("time_in_force", "day")
        limit_price = details.get("limit_price")
        order_type = "limit" if limit_price is not None else "market"

        # strategy_id as the client order id makes this call idempotent: if
        # workflow/pipeline.py's HTTP-level timeout (STEP_TIMEOUT_SECONDS,
        # 10s default) fires and retries while this CLI call is still in
        # flight (its own timeout is 30s), the retry carries the same
        # strategy_id -> same client_order_id -> Alpaca rejects it as a
        # duplicate instead of silently placing the same trade twice. A
        # genuinely new proposal always gets a new strategy_id.
        args = [
            "order", "submit",
            "--qty", qty,
            "--time-in-force", time_in_force,
            "--type", order_type,
            "--client-order-id", proposal.strategy_id,
        ]
        if limit_price is not None:
            args += ["--limit-price", str(limit_price)]

        # A spread strategy (call spread, straddle, etc.) shows up as an
        # explicit `legs` list in order_details - each leg its own
        # symbol/ratio/side/position_intent, Alpaca's real mleg order shape
        # (see CLAUDE.md's Alpaca MCP section). Anything without `legs` is a
        # plain single-contract order, the common case. ratio_qty has to be
        # a string - the CLI rejects a bare JSON number here (checked live).
        legs = details.get("legs")
        if legs:
            cli_legs = [
                {
                    "symbol": leg["symbol"],
                    "ratio_qty": str(leg.get("ratio_qty", 1)),
                    "side": leg["side"],
                    **({"position_intent": leg["position_intent"]} if leg.get("position_intent") else {}),
                }
                for leg in legs
            ]
            args += ["--order-class", "mleg", "--legs", json.dumps(cli_legs)]
        else:
            symbol = details.get("symbol", proposal.symbol)
            side = "buy" if proposal.action == "BUY" else "sell"
            args += ["--symbol", symbol, "--side", side]

        order = await self._cli(*args)

        return ExecutionResponse(
            status=order["status"],
            order_id=order["id"],
            filled_avg_price=float(order["filled_avg_price"]) if order.get("filled_avg_price") else 0.0,
            timestamp=order.get("submitted_at") or datetime.now(timezone.utc).isoformat(),
        )

    async def get_account(self) -> dict:
        return await self._cli("account", "get")

    async def get_clock(self) -> dict:
        return await self._cli("clock")
