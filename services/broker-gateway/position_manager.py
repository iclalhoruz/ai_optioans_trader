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


def _underlying_from_symbol(symbol: str) -> str:
    """Root ticker from an OCC option symbol - strips the trailing
    date(6)+type(1)+strike(8) = 15 characters, same convention as
    alpaca_client._parse_occ_symbol (parsed from the right since the root
    symbol's own length varies, e.g. AAPL vs SPY)."""
    return symbol[:-15]


def _group_key(position: dict) -> tuple[str, str]:
    """Groups by (underlying, expiration_date). This system only ever
    opens a single 2-leg vertical spread per trade, both legs sharing one
    underlying and one expiration (chaos-sandbox requires that to even
    evaluate the spread) - so any open positions sharing both are the two
    legs of the same trade and must be evaluated, and closed, as one unit.

    This matters more than it might look: Alpaca lists each leg of a
    filled multi-leg order as its own separate position with its own
    independent unrealized_pl/unrealized_plpc. Evaluating and closing
    positions independently - which an earlier version of this module did
    - can trigger take-profit on one leg while leaving the other open,
    turning a *defined-risk* spread into an accidental naked position with
    *unbounded* risk. Verified this is a real, not theoretical, failure
    mode: manage_positions() once closed exactly one leg of a real spread
    (the profitable short leg) while leaving the other (down -57%) open."""
    try:
        parsed = _parse_occ_symbol(position["symbol"])
    except (ValueError, IndexError):
        return (position["symbol"], "")  # not an option symbol - its own group
    return (_underlying_from_symbol(position["symbol"]), parsed["expiration_date"])


def _group_exit_reason(group: list[dict]) -> Optional[str]:
    """Net P&L across every position in the group, not per-leg - a
    profitable short leg and a losing long leg partially offset each
    other, same as they're meant to for a defined-risk spread. cost_basis
    is signed (positive for a long leg, negative for a short one, per
    Alpaca's own convention - confirmed live), so summing it directly
    gives the real net debit paid for the whole position."""
    net_unrealized_pl = sum(float(p["unrealized_pl"]) for p in group)
    net_cost_basis = sum(float(p["cost_basis"]) for p in group)
    if net_cost_basis != 0:
        net_plpc = net_unrealized_pl / abs(net_cost_basis)
        if net_plpc >= TAKE_PROFIT_PCT:
            return f"take-profit (net {net_plpc:.1%} >= {TAKE_PROFIT_PCT:.0%})"
        if net_plpc <= -STOP_LOSS_PCT:
            return f"stop-loss (net {net_plpc:.1%} <= -{STOP_LOSS_PCT:.0%})"

    # A vertical spread's legs share one expiration by construction, but
    # take the minimum defensively rather than assuming a specific leg's
    # symbol parses cleanly.
    days_to_expiry_values = []
    for position in group:
        try:
            days_to_expiry_values.append(_parse_occ_symbol(position["symbol"])["days_to_expiry"])
        except (ValueError, IndexError):
            continue
    if days_to_expiry_values and min(days_to_expiry_values) <= MIN_DAYS_BEFORE_CLOSE:
        return f"expiring soon ({min(days_to_expiry_values)}d <= {MIN_DAYS_BEFORE_CLOSE}d)"
    return None


async def manage_positions(gateway: AlpacaBrokerGateway, trade_log: TradeLog) -> list[dict]:
    """Checks every open position, grouped by (underlying, expiration) so
    a spread's legs are evaluated and closed together, against the exit
    rules above. Returns one entry per closed (or failed-to-close) leg -
    workflow/scheduler.py calls this once per autonomous cycle, and a
    failed close (e.g. a transient rejection right after closing the other
    leg of the same spread, seen live) needs to be visible in the
    response, not just a server-side log line, or a caller has no way to
    know a stop-loss didn't actually go through."""
    positions = await gateway.list_positions()
    groups: dict[tuple[str, str], list[dict]] = {}
    for position in positions:
        groups.setdefault(_group_key(position), []).append(position)

    results = []
    for group in groups.values():
        reason = _group_exit_reason(group)
        if reason is None:
            continue

        # Close short legs before long legs. Verified live this ordering
        # actually matters, not just in theory: closing a spread's long
        # leg first, while its short leg is still open, leaves an
        # "uncovered" short position - Alpaca rejected exactly that with
        # "account not eligible to trade uncovered option contracts," and
        # the old code then went ahead and closed the short leg anyway,
        # leaving the *wrong* leg (a naked long) open instead of the
        # intended flat position. Closing the short leg first is always
        # safe: buying back a short while the long remains never creates
        # an uncovered position.
        ordered_group = sorted(group, key=lambda p: 0 if p.get("side") == "short" else 1)

        closed_legs = []
        for position in ordered_group:
            symbol = position["symbol"]
            try:
                await gateway.close_position(symbol)
            except AlpacaCLIError as exc:
                # If a short leg fails to close, do NOT go on to close the
                # long leg(s) in this group - that would leave the short
                # uncovered, exactly the failure mode above. Leaving the
                # group untouched (its original, still-hedged shape) and
                # retrying next cycle is always the safe choice.
                logger.warning("failed to close %s (%s): %s", symbol, reason, exc)
                results.append({"symbol": symbol, "reason": reason, "closed": False, "error": exc.message})
                break

            closed_legs.append(position)
            results.append(
                {"symbol": symbol, "reason": reason, "closed": True, "realizedPnl": float(position["unrealized_pl"])}
            )
            logger.info("closed %s: %s (leg realized P&L $%.2f)", symbol, reason, float(position["unrealized_pl"]))

        if not closed_legs:
            continue

        # One aggregated trade-log entry for the whole spread, not one per
        # leg - otherwise pnl_summary()'s win-rate counts legs as if they
        # were independent trades, which is misleading: a net-profitable
        # spread can easily have one leg individually "down" even though
        # the position as a whole made money. If a leg failed to close
        # above, this reflects only the legs that actually did.
        net_realized_pnl = sum(float(p["unrealized_pl"]) for p in closed_legs)
        total_qty = sum(abs(float(p["qty"])) for p in closed_legs)
        avg_price = (
            sum(float(p["current_price"]) * abs(float(p["qty"])) for p in closed_legs) / total_qty
            if total_qty
            else 0.0
        )
        symbols = "+".join(p["symbol"] for p in closed_legs)
        await trade_log.record_close(symbols, total_qty, avg_price, net_realized_pnl, reason)
        logger.info("closed group %s: %s (net realized P&L $%.2f)", symbols, reason, net_realized_pnl)

    return results
