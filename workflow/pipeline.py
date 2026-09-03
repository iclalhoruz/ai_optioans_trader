"""
Cross-service orchestrator for the Aegis-OptionAI trade pipeline.

Runs the 5-step chain end to end:
  market-context -> generate-proposal -> stress-test -> validate-risk -> execute-order

Nothing in here knows *how* any service does its job, only its contract (see
contracts/schemas.py) and its URL. That's on purpose so this orchestrator has to
keep working no matter what any of them look like inside. Steps live in the
STEPS tuple below; adding, removing, or reordering a service in the pipeline
is a one-line change there, not a rewrite of the run loop.

Durability: every step's result gets written to Redis under the run's id, so
a crash mid-pipeline doesn't lose the trade's state. Saga-style compensation
hooks are wired into StepConfig for when a step needs to undo a side effect
of an earlier step (relevant once multi-leg orders exist) - right now only
`execute-order` has a side effect and it's the last step, so compensation is
a no-op in practice, but the plumbing is there.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Awaitable, Callable, Optional

import httpx
import redis.asyncio as redis
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

from contracts.schemas import (
    ChaosTestResult,
    ExecutionResponse,
    MarketContext,
    RiskResult,
    TradeProposal,
)

logger = logging.getLogger("aegis.pipeline")


class PipelineSettings(BaseSettings):
    """Where to find everything. Defaults match the ports docker-compose maps to localhost."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    broker_gateway_url: str = "http://localhost:8001"
    ai_strategy_url: str = "http://localhost:8002"
    chaos_sandbox_url: str = "http://localhost:8003"
    risk_engine_url: str = "http://localhost:8004"
    redis_url: str = "redis://localhost:6379/0"

    step_timeout_seconds: float = 10.0
    step_max_retries: int = 3
    redis_state_ttl_seconds: int = 86400

    # Human-in-the-loop gate before execute-order fires. Off by default so the
    # pipeline runs fully autonomous out of the box; flip it on once there's
    # somewhere for the approval to actually surface (dashboard, Slack, etc).
    hitl_enabled: bool = False
    hitl_notional_threshold: float = 10_000.0


class PipelineStatus(StrEnum):
    STARTED = "STARTED"
    RUNNING = "RUNNING"
    PENDING_HUMAN_APPROVAL = "PENDING_HUMAN_APPROVAL"
    VETOED = "VETOED"
    FAILED = "FAILED"
    SUCCESS = "SUCCESS"


class PipelineStepError(RuntimeError):
    """Raised when a step exhausts its retries. Carries enough context to log and compensate."""

    def __init__(self, step_name: str, detail: str) -> None:
        super().__init__(f"step '{step_name}' failed: {detail}")
        self.step_name = step_name
        self.detail = detail


def _dump(model: Optional[BaseModel]) -> Optional[dict]:
    return model.model_dump() if model is not None else None


def _parse(model_cls: type[BaseModel], data: Optional[dict]) -> Optional[BaseModel]:
    return model_cls.model_validate(data) if data is not None else None

# Hangi adımda hangi veri oluşuyor
@dataclass
class PipelineState:
    run_id: str
    ticker: str
    status: PipelineStatus = PipelineStatus.STARTED
    market_context: Optional[MarketContext] = None
    trade_proposal: Optional[TradeProposal] = None
    chaos_result: Optional[ChaosTestResult] = None
    risk_result: Optional[RiskResult] = None
    execution_response: Optional[ExecutionResponse] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # step name -> attribute name, so set_result doesn't need an if/elif ladder
    _RESULT_SLOTS = {
        "market_context": "market_context",
        "trade_proposal": "trade_proposal",
        "chaos_result": "chaos_result",
        "risk_result": "risk_result",
        "execution": "execution_response",
    }

    def set_result(self, step_name: str, value: BaseModel) -> None:
        setattr(self, self._RESULT_SLOTS[step_name], value)
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "ticker": self.ticker,
            "status": self.status.value,
            "market_context": _dump(self.market_context),
            "trade_proposal": _dump(self.trade_proposal),
            "chaos_result": _dump(self.chaos_result),
            "risk_result": _dump(self.risk_result),
            "execution_response": _dump(self.execution_response),
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PipelineState":
        return cls(
            run_id=data["run_id"],
            ticker=data["ticker"],
            status=PipelineStatus(data["status"]),
            market_context=_parse(MarketContext, data.get("market_context")),
            trade_proposal=_parse(TradeProposal, data.get("trade_proposal")),
            chaos_result=_parse(ChaosTestResult, data.get("chaos_result")),
            risk_result=_parse(RiskResult, data.get("risk_result")),
            execution_response=_parse(ExecutionResponse, data.get("execution_response")),
            error=data.get("error"),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )


@dataclass(frozen=True)
class StepConfig:
    name: str
    method: str
    build_url: Callable[[PipelineSettings, PipelineState], str]
    build_payload: Optional[Callable[[PipelineState], dict]]
    response_model: type[BaseModel]
    compensate: Optional[Callable[[PipelineState, PipelineSettings, httpx.AsyncClient], Awaitable[None]]] = None


# The registry. This is the thing to edit when a service gets added, dropped,
# or reordered - the run loop below never changes.
STEPS: tuple[StepConfig, ...] = (
    StepConfig(
        name="market_context",
        method="GET",
        build_url=lambda s, st: f"{s.broker_gateway_url}/market-context/{st.ticker}",
        build_payload=None,
        response_model=MarketContext,
    ),
    StepConfig(
        name="trade_proposal",
        method="POST",
        build_url=lambda s, st: f"{s.ai_strategy_url}/generate-proposal",
        build_payload=lambda st: st.market_context.model_dump(),
        response_model=TradeProposal,
    ),
    StepConfig(
        name="chaos_result",
        method="POST",
        build_url=lambda s, st: f"{s.chaos_sandbox_url}/stress-test",
        build_payload=lambda st: st.trade_proposal.model_dump(),
        response_model=ChaosTestResult,
    ),
    StepConfig(
        name="risk_result",
        method="POST",
        build_url=lambda s, st: f"{s.risk_engine_url}/validate-risk",
        build_payload=lambda st: st.chaos_result.model_dump(),
        response_model=RiskResult,
    ),
    StepConfig(
        name="execution",
        method="POST",
        build_url=lambda s, st: f"{s.broker_gateway_url}/execute-order",
        build_payload=lambda st: st.risk_result.final_proposal.model_dump(),
        response_model=ExecutionResponse,
    ),
)


def _notional_value(proposal: TradeProposal) -> float:
    details = proposal.order_details
    return float(details.get("quantity", 0)) * float(details.get("limit_price", 0))


def requires_human_approval(state: PipelineState, settings: PipelineSettings) -> bool:
    if not settings.hitl_enabled or state.risk_result is None or state.risk_result.final_proposal is None:
        return False
    return _notional_value(state.risk_result.final_proposal) >= settings.hitl_notional_threshold


async def call_service(
    client: httpx.AsyncClient,
    step: StepConfig,
    url: str,
    payload: Optional[dict],
    *,
    timeout: float,
    retries: int,
) -> dict:
    """One retrying HTTP call, shared by every step so nobody hand-rolls their own backoff loop."""
    last_error: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            response = await client.request(step.method, url, json=payload, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            last_error = exc
            backoff = min(2 ** (attempt - 1), 8)
            logger.warning(
                "step=%s attempt=%d/%d failed: %s (retrying in %ss)",
                step.name, attempt, retries, exc, backoff,
            )
            if attempt < retries:
                await asyncio.sleep(backoff)
    raise PipelineStepError(step.name, str(last_error))


class PipelineOrchestrator:
    def __init__(
        self,
        settings: Optional[PipelineSettings] = None,
        http_client: Optional[httpx.AsyncClient] = None,
        redis_client: Optional[redis.Redis] = None,
    ) -> None:
        # http_client/redis_client are injectable so tests can swap in a
        # mocked transport / fake redis without touching the run loop.
        self.settings = settings or PipelineSettings()
        self._http = http_client or httpx.AsyncClient()
        self._redis = redis_client or redis.from_url(self.settings.redis_url, decode_responses=True)

    async def aclose(self) -> None:
        await self._http.aclose()
        await self._redis.aclose()

    async def _persist(self, state: PipelineState) -> None:
        key = f"pipeline:run:{state.run_id}"
        await self._redis.set(key, json.dumps(state.to_dict()), ex=self.settings.redis_state_ttl_seconds)
        # Sorted set keyed by last-persisted time - re-persisting the same
        # run_id (happens once per step) just bumps its score instead of
        # creating duplicate index entries, so "recent runs" stays correct
        # without any special-casing at the call site.
        await self._redis.zadd("pipeline:runs:index", {state.run_id: datetime.now(timezone.utc).timestamp()})

    async def _load(self, run_id: str) -> PipelineState:
        raw = await self._redis.get(f"pipeline:run:{run_id}")
        if raw is None:
            raise KeyError(f"no persisted state for run_id={run_id}")
        return PipelineState.from_dict(json.loads(raw))

    async def get_state(self, run_id: str) -> PipelineState:
        """Public read - for an HTTP layer (broker-gateway) to poll a run's state."""
        return await self._load(run_id)

    async def list_recent_run_ids(self, limit: int = 20) -> list[str]:
        return await self._redis.zrevrange("pipeline:runs:index", 0, limit - 1)

    async def forget_run(self, run_id: str) -> None:
        """Drop a run_id from the recent-runs index. Individual run state
        expires from Redis after redis_state_ttl_seconds (24h default), but
        nothing was pruning the index itself - with the scheduler generating
        a run every few minutes for days, list_recent_run_ids() would start
        returning ids whose state is already gone. Callers should call this
        when get_state() raises KeyError for an id pulled from the index."""
        await self._redis.zrem("pipeline:runs:index", run_id)

    async def _compensate(self, completed_steps: list[StepConfig], state: PipelineState) -> None:
        for step in reversed(completed_steps):
            if step.compensate is None:
                continue
            logger.info("compensating step=%s for run_id=%s", step.name, state.run_id)
            await step.compensate(state, self.settings, self._http)

    async def _run_step(self, step: StepConfig, state: PipelineState) -> None:
        url = step.build_url(self.settings, state)
        payload = step.build_payload(state) if step.build_payload else None
        raw = await call_service(
            self._http, step, url, payload,
            timeout=self.settings.step_timeout_seconds,
            retries=self.settings.step_max_retries,
        )
        state.set_result(step.name, step.response_model.model_validate(raw))

    async def run(self, ticker: str) -> PipelineState:
        """Blocks until the run reaches a terminal (or HITL-paused) state -
        what test_pipeline.py and the CLI entrypoint below use."""
        state = PipelineState(run_id=str(uuid.uuid4()), ticker=ticker)
        return await self._execute(state)

    async def start(self, ticker: str) -> str:
        """Non-blocking version for an HTTP caller (broker-gateway's POST
        /runs): persists the run immediately so a GET right after never
        404s, then executes it as a background task instead of holding the
        HTTP request open for however long the whole pipeline takes."""
        state = PipelineState(run_id=str(uuid.uuid4()), ticker=ticker)
        await self._persist(state)
        asyncio.create_task(self._execute(state))
        return state.run_id

    async def _execute(self, state: PipelineState) -> PipelineState:
        state.status = PipelineStatus.RUNNING
        await self._persist(state)

        completed: list[StepConfig] = []
        try:
            for step in STEPS:
                if step.name == "execution":
                    if not state.risk_result.is_approved:
                        state.status = PipelineStatus.VETOED
                        break
                    if requires_human_approval(state, self.settings):
                        state.status = PipelineStatus.PENDING_HUMAN_APPROVAL
                        await self._persist(state)
                        logger.info("run_id=%s paused for human approval", state.run_id)
                        return state

                await self._run_step(step, state)
                completed.append(step)
                await self._persist(state)

            if state.status == PipelineStatus.RUNNING:
                state.status = PipelineStatus.SUCCESS

        except PipelineStepError as exc:
            state.status = PipelineStatus.FAILED
            state.error = str(exc)
            await self._compensate(completed, state)

        await self._persist(state)
        return state

    async def resume(self, run_id: str) -> PipelineState:
        """Continue a run that was parked at PENDING_HUMAN_APPROVAL once a human signs off."""
        state = await self._load(run_id)
        if state.status != PipelineStatus.PENDING_HUMAN_APPROVAL:
            raise ValueError(f"run_id={run_id} is not pending approval (status={state.status})")

        execution_step = next(s for s in STEPS if s.name == "execution")
        state.status = PipelineStatus.RUNNING
        try:
            await self._run_step(execution_step, state)
            state.status = PipelineStatus.SUCCESS
        except PipelineStepError as exc:
            state.status = PipelineStatus.FAILED
            state.error = str(exc)

        await self._persist(state)
        return state


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"

    orchestrator = PipelineOrchestrator()
    try:
        state = await orchestrator.run(ticker)
        print(json.dumps(state.to_dict(), indent=2))
    finally:
        await orchestrator.aclose()


if __name__ == "__main__":
    asyncio.run(main())
