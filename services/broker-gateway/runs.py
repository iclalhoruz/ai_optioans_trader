"""
HTTP surface over workflow/pipeline.py's PipelineOrchestrator - lets the
frontend (or anyone) trigger a run and poll its progress instead of only
being usable from the CLI entrypoint.

Also translates PipelineState (the backend's internal shape) into the JSON
shapes frontend/src/types/domain.ts expects (RunDetail/RunSummary,
camelCase). The frontend was built against those types before this service
existed, so the adaptation lives here rather than changing either side to
match the other - contracts/schemas.py stays the real inter-service
contract, this is just a read-model for the UI.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException

from contracts.schemas import TradeProposal
from workflow.pipeline import PipelineOrchestrator, PipelineState, PipelineStatus

router = APIRouter()
orchestrator = PipelineOrchestrator()

# workflow/pipeline.py's PipelineStatus -> frontend's RunStatus.
# PENDING_HUMAN_APPROVAL maps to "running" since HITL is off by default
# (HITL_ENABLED=false) and the frontend has no distinct state for it yet -
# revisit this mapping if HITL gets turned on.
_RUN_STATUS = {
    PipelineStatus.STARTED: "running",
    PipelineStatus.RUNNING: "running",
    PipelineStatus.PENDING_HUMAN_APPROVAL: "running",
    PipelineStatus.VETOED: "vetoed",
    PipelineStatus.FAILED: "failed",
    PipelineStatus.SUCCESS: "success",
}

_STEP_ORDER = ["market_context", "trade_proposal", "chaos_result", "risk_result", "execution"]
_STEP_META = {
    "market_context": {"label": "Market Data", "icon": "monitoring"},
    "trade_proposal": {"label": "AI Strategy", "icon": "psychology"},
    "chaos_result": {"label": "Chaos Sandbox", "icon": "science"},
    "risk_result": {"label": "Risk Gate", "icon": "gavel"},
    "execution": {"label": "Execute", "icon": "send"},
}


def _step_slots(state: PipelineState) -> dict[str, object]:
    return {
        "market_context": state.market_context,
        "trade_proposal": state.trade_proposal,
        "chaos_result": state.chaos_result,
        "risk_result": state.risk_result,
        "execution": state.execution_response,
    }


def _build_steps(state: PipelineState) -> list[dict]:
    slots = _step_slots(state)
    # The STEPS loop in workflow/pipeline.py stops the instant a step
    # exhausts its retries, so the first still-empty slot is exactly the
    # one that's either running now or the one that failed.
    first_empty = next((name for name in _STEP_ORDER if slots[name] is None), None)

    steps = []
    for name in _STEP_ORDER:
        if slots[name] is not None:
            status = "success"
        elif name != first_empty:
            status = "pending"
        elif state.status == PipelineStatus.FAILED:
            status = "failed"
        elif state.status in (PipelineStatus.RUNNING, PipelineStatus.STARTED):
            status = "running"
        else:
            status = "pending"

        steps.append({"id": name, "status": status, **_STEP_META[name]})
    return steps


def _latest_proposal(state: PipelineState) -> Optional[TradeProposal]:
    """The most up-to-date version of the proposal - risk-engine's final
    approved version if there is one, else chaos-sandbox's refined version,
    else the original from ai-strategy."""
    if state.risk_result and state.risk_result.final_proposal:
        return state.risk_result.final_proposal
    if state.chaos_result and state.chaos_result.refined_proposal:
        return state.chaos_result.refined_proposal
    return state.trade_proposal


def _duration_seconds(state: PipelineState) -> float:
    created = datetime.fromisoformat(state.created_at)
    updated = datetime.fromisoformat(state.updated_at)
    return max(0.0, (updated - created).total_seconds())


def _strategy_decision(proposal: Optional[TradeProposal]) -> dict:
    if proposal is None:
        return {
            "symbol": "",
            "action": "HOLD",
            "direction": "bullish",
            "description": "Awaiting proposal",
            "convictionPct": 0,
            "reasoning": "",
        }

    # order_details is a loose dict by design (contracts/schemas.py) - these
    # keys are the convention ai-strategy should populate; anything missing
    # degrades to a reasonable default instead of breaking the response.
    details = proposal.order_details
    direction = details.get("direction") or ("bearish" if proposal.action == "SELL" else "bullish")

    return {
        "symbol": proposal.symbol,
        "action": proposal.action,
        "direction": direction,
        "description": details.get("description", f"{proposal.action} {proposal.symbol}"),
        "convictionPct": round(proposal.conviction_score * 100),
        "reasoning": details.get("reasoning", ""),
    }


def _chaos_sandbox_state(state: PipelineState) -> dict:
    result = state.chaos_result
    if result is None:
        in_progress = (
            state.status in (PipelineStatus.RUNNING, PipelineStatus.STARTED) and state.trade_proposal is not None
        )
        return {"status": "running" if in_progress else "pending", "logs": []}

    return {
        "status": "complete",
        "logs": result.logs,
        # ChaosTestResult.stress_score is LOW=safe (contracts/schemas.py) -
        # the frontend's survivalScorePct is the inverse, HIGH=survived well.
        "survivalScorePct": round((1 - result.stress_score) * 100),
        "summary": "Passed stress tests." if result.is_safe else "Failed stress tests.",
    }


def _risk_gate_state(state: PipelineState) -> dict:
    result = state.risk_result
    if result is None:
        return {"status": "pending"}
    return {"status": "approved" if result.is_approved else "vetoed", "reason": result.veto_reason}


def to_run_detail(state: PipelineState) -> dict:
    proposal = _latest_proposal(state)
    return {
        "runId": state.run_id,
        "symbol": state.ticker,
        "status": _RUN_STATUS[state.status],
        "initiatedAt": state.created_at,
        "durationSeconds": _duration_seconds(state),
        "steps": _build_steps(state),
        "strategy": _strategy_decision(proposal),
        "chaosSandbox": _chaos_sandbox_state(state),
        "riskGate": _risk_gate_state(state),
    }


def to_run_summary(state: PipelineState) -> dict:
    proposal = _latest_proposal(state)
    return {
        "id": state.run_id,
        "symbol": state.ticker,
        "status": _RUN_STATUS[state.status],
        "action": proposal.action if proposal else "HOLD",
        "convictionPct": round(proposal.conviction_score * 100) if proposal else 0,
    }


@router.post("/runs")
async def start_run(payload: dict) -> dict:
    ticker = payload.get("ticker", "").strip().upper()
    if not ticker:
        raise HTTPException(status_code=422, detail="ticker is required")
    run_id = await orchestrator.start(ticker)
    return {"runId": run_id}


@router.get("/runs/active")
async def get_active_run() -> dict:
    recent_ids = await orchestrator.list_recent_run_ids(limit=1)
    if not recent_ids:
        raise HTTPException(status_code=404, detail="no runs yet")
    state = await orchestrator.get_state(recent_ids[0])
    return to_run_detail(state)


@router.get("/runs/recent")
async def get_recent_runs() -> list[dict]:
    run_ids = await orchestrator.list_recent_run_ids(limit=20)
    summaries = []
    for run_id in run_ids:
        try:
            state = await orchestrator.get_state(run_id)
        except KeyError:
            # State expired from Redis (24h TTL) but the index still had it
            # - clean up instead of letting one stale id 500 the whole list.
            await orchestrator.forget_run(run_id)
            continue
        summaries.append(to_run_summary(state))
    return summaries


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict:
    try:
        state = await orchestrator.get_state(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found") from exc
    return to_run_detail(state)
