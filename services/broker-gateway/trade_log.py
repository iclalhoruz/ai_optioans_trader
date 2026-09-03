"""
Redis-backed record of what this system actually did - opens and closes,
with realized P&L on closes. This is what makes "did the autonomous system
make money" answerable with real numbers instead of "the pipeline ran
successfully" - a working pipeline and a profitable one are different
claims, and this is the evidence for the second one.

Not a backtest - a forward-looking, real trade log. Redis was already a
dependency of this service (this instance is separate from
workflow/pipeline.py's, on purpose - trade history belongs to
broker-gateway, the one service that actually knows a fill happened).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import redis.asyncio as redis

# Bounded so this never grows without limit - a demo/hackathon system
# doesn't need more than a few hundred trades of history kept live.
MAX_LOG_ENTRIES = 500
REDIS_KEY = "broker_gateway:trade_log"


class TradeLog:
    def __init__(self, redis_client: redis.Redis | None = None) -> None:
        self._redis = redis_client or redis.from_url(
            os.environ.get("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True
        )

    async def record_open(self, symbol: str, qty: float, price: float, order_id: str) -> None:
        await self._append(
            {
                "event": "open",
                "symbol": symbol,
                "qty": qty,
                "price": price,
                "order_id": order_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def record_close(self, symbol: str, qty: float, price: float, realized_pnl: float, reason: str) -> None:
        await self._append(
            {
                "event": "close",
                "symbol": symbol,
                "qty": qty,
                "price": price,
                "realized_pnl": realized_pnl,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def _append(self, entry: dict) -> None:
        await self._redis.lpush(REDIS_KEY, json.dumps(entry))
        await self._redis.ltrim(REDIS_KEY, 0, MAX_LOG_ENTRIES - 1)

    async def recent(self, limit: int = 100) -> list[dict]:
        raw = await self._redis.lrange(REDIS_KEY, 0, limit - 1)
        return [json.loads(entry) for entry in raw]

    async def pnl_summary(self) -> dict:
        # Reads the whole bounded log rather than maintaining running
        # counters - simpler, and MAX_LOG_ENTRIES keeps this cheap.
        entries = await self.recent(MAX_LOG_ENTRIES)
        closes = [e for e in entries if e["event"] == "close"]
        wins = [c for c in closes if c["realized_pnl"] > 0]
        return {
            "totalRealizedPnl": sum(c["realized_pnl"] for c in closes),
            "closedTradeCount": len(closes),
            "winCount": len(wins),
            "winRatePct": round(len(wins) / len(closes) * 100, 1) if closes else 0.0,
        }
