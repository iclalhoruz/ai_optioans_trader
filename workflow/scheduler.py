"""
The autonomous piece of the pipeline. Loops over a fixed watchlist and
triggers a run per ticker on an interval, with no human involved - this is
what makes the system an "autonomous agent" rather than a demo tool someone
has to click.

Talks to broker-gateway over HTTP (same as the frontend does) instead of
importing PipelineOrchestrator directly, so there's exactly one way a run
ever gets started and broker-gateway stays the system's single front door -
including for checking whether the market is even open, which is why this
script never opens its own Alpaca connection.

Usage: python workflow/scheduler.py
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger("aegis.scheduler")

BROKER_GATEWAY_URL = os.environ.get("BROKER_GATEWAY_URL", "http://localhost:8001")
WATCHLIST = [
    ticker.strip().upper()
    for ticker in os.environ.get("WATCHLIST_TICKERS", "AAPL,TSLA,NVDA,SPY,MSFT").split(",")
    if ticker.strip()
]
INTERVAL_SECONDS = float(os.environ.get("SCHEDULER_INTERVAL_MINUTES", "15")) * 60


async def is_market_open(client: httpx.AsyncClient) -> bool:
    try:
        response = await client.get(f"{BROKER_GATEWAY_URL}/clock", timeout=10.0)
        response.raise_for_status()
        return response.json()["isOpen"]
    except httpx.HTTPError as exc:
        logger.warning("couldn't reach broker-gateway's /clock, assuming market closed: %s", exc)
        return False


async def trigger_run(client: httpx.AsyncClient, ticker: str) -> None:
    try:
        response = await client.post(f"{BROKER_GATEWAY_URL}/runs", json={"ticker": ticker}, timeout=10.0)
        response.raise_for_status()
        logger.info("started run for %s -> run_id=%s", ticker, response.json()["runId"])
    except httpx.HTTPError as exc:
        logger.error("couldn't start a run for %s: %s", ticker, exc)


async def run_forever() -> None:
    logger.info("watchlist=%s interval=%.0fs broker_gateway=%s", WATCHLIST, INTERVAL_SECONDS, BROKER_GATEWAY_URL)

    async with httpx.AsyncClient() as client:
        while True:
            if await is_market_open(client):
                for ticker in WATCHLIST:
                    await trigger_run(client, ticker)
            else:
                logger.info("market closed - skipping this cycle")

            await asyncio.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(run_forever())
