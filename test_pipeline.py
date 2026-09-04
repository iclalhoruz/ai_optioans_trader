"""
Integration test for workflow/pipeline.py.

The 4 services are still empty folders so there's nothing real to hit.
Instead this spins up a fake transport that answers like the 4 services
will, per the contracts everyone already agreed on, and drives the real
orchestrator against it. That proves the sequencing, retry/backoff, veto
short-circuit, and Redis durability all actually work - so whoever writes
the first real service main.py is building on a pipeline that's already
known-good. Once a service exists for real, point PipelineSettings at its
real URL and this same orchestrator hits it over the network instead.

Needs a real Redis reachable at REDIS_URL (default localhost:6379) -
`docker compose up -d redis` first.

Writes to db 1 on that Redis instance, never db 0 - PipelineSettings()'s
default redis_url (and .env's) points at db 0, the same keyspace the real
running stack persists real runs to. This test used to connect there
directly, which meant every run of this file left its 3 fixed mock
proposals (AAPL/TSLA/NVDA, strategy_id "mock-dialectic-v1") sitting in
`pipeline:runs:index` indistinguishable from real trade history in the
frontend - confirmed live: 27 of them had accumulated there from earlier
sessions and were mistaken for real executed trades before being found and
cleaned up (see CLAUDE.md, 2026-09-04).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from typing import Awaitable, Callable

import httpx
import redis.asyncio as redis

from workflow.pipeline import PipelineOrchestrator, PipelineSettings, PipelineStatus

TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/1")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mock_market_context(ticker: str) -> dict:
    return {
        "ticker": ticker,
        "spot_price": 189.50,
        "implied_volatility": 0.27,
        "chain_summary": {"calls_volume": 1200, "puts_volume": 900, "put_call_ratio": 0.75},
        "timestamp": _now(),
    }


def _mock_trade_proposal(ticker: str) -> dict:
    return {
        "strategy_id": "mock-dialectic-v1",
        "action": "BUY",
        "symbol": ticker,
        "generated_code": "def analyze_option(spot, strike, iv, dte):\n    return {'estimated_premium': round(max(spot - strike, 0) + iv * 10, 2)}\n",
        "conviction_score": 0.82,
        "order_details": {"quantity": 1, "limit_price": 5.10, "strike": 190, "days_to_expiry": 30},
    }


def _mock_chaos_result(refined_proposal: dict) -> dict:
    return {
        "is_safe": True,
        "stress_score": 0.14,
        "logs": ["injected 500% spread widening", "injected IV crush -80%", "generated_code survived both"],
        "refined_proposal": refined_proposal,
    }


def _mock_risk_result(final_proposal: dict, *, approved: bool) -> dict:
    return {
        "is_approved": approved,
        "veto_reason": None if approved else "mock hard veto: allocation exceeds portfolio limit",
        "final_proposal": final_proposal if approved else None,
    }


def _mock_execution_response() -> dict:
    return {
        "status": "FILLED",
        "order_id": "mock-order-0001",
        "filled_avg_price": 5.12,
        "timestamp": _now(),
    }


def build_mock_transport(
    *, chaos_failures_before_success: int = 0, risk_approved: bool = True
) -> tuple[httpx.MockTransport, dict[str, int]]:
    call_counts = {"stress_test": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        match True:
            case _ if path.startswith("/market-context/"):
                ticker = path.rsplit("/", 1)[-1]
                return httpx.Response(200, json=_mock_market_context(ticker))
            case _ if path == "/generate-proposal":
                body = json.loads(request.content)
                return httpx.Response(200, json=_mock_trade_proposal(body["ticker"]))
            case _ if path == "/stress-test":
                call_counts["stress_test"] += 1
                if call_counts["stress_test"] <= chaos_failures_before_success:
                    return httpx.Response(500, json={"detail": "simulated transient failure"})
                proposal = json.loads(request.content)
                return httpx.Response(200, json=_mock_chaos_result(proposal))
            case _ if path == "/validate-risk":
                chaos = json.loads(request.content)
                return httpx.Response(200, json=_mock_risk_result(chaos["refined_proposal"], approved=risk_approved))
            case _ if path == "/execute-order":
                return httpx.Response(200, json=_mock_execution_response())
            case _:
                return httpx.Response(404, json={"detail": f"unmocked path {path}"})

    return httpx.MockTransport(handler), call_counts


async def _new_orchestrator(transport: httpx.MockTransport, redis_client: redis.Redis) -> PipelineOrchestrator:
    settings = PipelineSettings(step_timeout_seconds=5.0, step_max_retries=3)
    http_client = httpx.AsyncClient(transport=transport)
    return PipelineOrchestrator(settings=settings, http_client=http_client, redis_client=redis_client)


async def test_happy_path(redis_client: redis.Redis) -> None:
    transport, _ = build_mock_transport(risk_approved=True)
    orchestrator = await _new_orchestrator(transport, redis_client)
    try:
        state = await orchestrator.run("AAPL")
        assert state.status == PipelineStatus.SUCCESS, f"expected SUCCESS, got {state.status}"
        assert state.execution_response is not None, "execution_response should be populated on success"
        assert state.execution_response.order_id == "mock-order-0001"
        persisted = await redis_client.get(f"pipeline:run:{state.run_id}")
        assert persisted is not None, "final state must be persisted to redis"
        assert json.loads(persisted)["status"] == "SUCCESS"
    finally:
        await orchestrator.aclose()


async def test_veto_path(redis_client: redis.Redis) -> None:
    transport, _ = build_mock_transport(risk_approved=False)
    orchestrator = await _new_orchestrator(transport, redis_client)
    try:
        state = await orchestrator.run("TSLA")
        assert state.status == PipelineStatus.VETOED, f"expected VETOED, got {state.status}"
        assert state.execution_response is None, "a vetoed run must never reach execution"
        assert state.risk_result is not None and state.risk_result.is_approved is False
    finally:
        await orchestrator.aclose()


async def test_retry_recovers(redis_client: redis.Redis) -> None:
    transport, call_counts = build_mock_transport(chaos_failures_before_success=1)
    orchestrator = await _new_orchestrator(transport, redis_client)
    try:
        state = await orchestrator.run("NVDA")
        assert state.status == PipelineStatus.SUCCESS, f"expected retry to recover to SUCCESS, got {state.status}"
        assert call_counts["stress_test"] == 2, "chaos-sandbox should have been hit twice (1 failure + 1 success)"
    finally:
        await orchestrator.aclose()


async def _run_check(name: str, coro: Awaitable[None]) -> bool:
    try:
        await coro
        print(f"  PASS  {name}")
        return True
    except AssertionError as exc:
        print(f"  FAIL  {name} - {exc}")
        return False
    except Exception as exc:  # noqa: BLE001 - surfaced as a failed check, not a crash
        print(f"  ERROR {name} - {exc!r}")
        return False


async def main() -> int:
    settings = PipelineSettings()
    redis_client = redis.from_url(TEST_REDIS_URL, decode_responses=True)

    try:
        await redis_client.ping()
    except Exception as exc:
        print(f"Cannot reach Redis at {TEST_REDIS_URL}: {exc}")
        print("Start it with: docker compose up -d redis")
        return 1

    print("Running pipeline orchestrator checks against a mocked service transport...\n")
    checks: list[tuple[str, Callable[[], Awaitable[None]]]] = [
        ("happy path reaches SUCCESS and fills the order", lambda: test_happy_path(redis_client)),
        ("risk veto short-circuits before execute-order", lambda: test_veto_path(redis_client)),
        ("transient chaos-sandbox failure is retried and recovers", lambda: test_retry_recovers(redis_client)),
    ]

    results = [await _run_check(name, check()) for name, check in checks]
    await redis_client.aclose()

    passed, total = sum(results), len(results)
    print(f"\n{passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
