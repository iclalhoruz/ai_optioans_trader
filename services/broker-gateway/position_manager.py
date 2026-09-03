"""
Deterministic (no LLM) position-exit rules - the counterpart to
ai-strategy's entry logic. Without this, a filled position just sits held
until expiration regardless of P&L, which isn't risk management, it's
"buy and forget."

Kept entirely separate from workflow/pipeline.py's entry pipeline (market
context -> proposal -> stress test -> risk gate -> execute) on purpose:
closing an existing position is risk-reducing, not risk-increasing, so it
doesn't need a fresh proposal/stress-test/veto cycle the way opening a new
one does - it's a simple, deterministic rule check against a live position.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from alpaca_client import AlpacaBrokerGateway, AlpacaCLIError, _parse_occ_symbol
from trade_log import TradeLog

logger = logging.getLogger("position-manager")

TAKE_PROFIT_PCT = float(os.environ.get("TAKE_PROFIT_PCT", "0.25"))
STOP_LOSS_PCT = float(os.environ.get("STOP_LOSS_PCT", "0.20"))
MIN_DAYS_BEFORE_CLOSE = int(os.environ.get("MIN_DAYS_BEFORE_CLOSE", "14"))


def _exit_reason(position: dict) -> Optional[str]:
    plpc = float(position["unrealized_plpc"])
    if plpc >= TAKE_PROFIT_PCT:
        return f"take-profit ({plpc:.1%} >= {TAKE_PROFIT_PCT:.0%})"
    if plpc <= -STOP_LOSS_PCT:
        return f"stop-loss ({plpc:.1%} <= -{STOP_LOSS_PCT:.0%})"

    try:
        days_to_expiry = _parse_occ_symbol(position["symbol"])["days_to_expiry"]
    except (ValueError, IndexError):
        # Not a real OCC option symbol (e.g. underlying shares left over
        # from an ITM assignment) - only the P&L rules above apply to it.
        return None
    if days_to_expiry <= MIN_DAYS_BEFORE_CLOSE:
        return f"expiring soon ({days_to_expiry}d <= {MIN_DAYS_BEFORE_CLOSE}d)"
    return None


async def manage_positions(gateway: AlpacaBrokerGateway, trade_log: TradeLog) -> list[dict]:
    """Checks every open position against the exit rules above and closes
    any that trigger. Returns one entry per triggered position, closed or
    not - workflow/scheduler.py calls this once per autonomous cycle, and
    a failed close (e.g. a transient rejection right after closing another
    leg of the same former multi-leg position, seen live) needs to be
    visible in the response, not just a server-side log line, or a caller
    has no way to know a stop-loss didn't actually go through."""
    positions = await gateway.list_positions()
    results = []
    for position in positions:
        reason = _exit_reason(position)
        if reason is None:
            continue

        symbol = position["symbol"]
        qty = float(position["qty"])
        realized_pnl = float(position["unrealized_pl"])
        try:
            await gateway.close_position(symbol)
        except AlpacaCLIError as exc:
            # A real rejection shouldn't crash the whole cycle - log it,
            # report it, and keep checking the rest.
            logger.warning("failed to close %s (%s): %s", symbol, reason, exc)
            results.append({"symbol": symbol, "reason": reason, "closed": False, "error": exc.message})
            continue

        await trade_log.record_close(symbol, qty, float(position["current_price"]), realized_pnl, reason)
        results.append({"symbol": symbol, "reason": reason, "closed": True, "realizedPnl": realized_pnl})
        logger.info("closed %s: %s (realized P&L $%.2f)", symbol, reason, realized_pnl)

    return results
