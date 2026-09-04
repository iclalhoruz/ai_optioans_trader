# Aegis-OptionAI — risk-engine

The deterministic "hard-veto" layer of the system. Takes a `ChaosTestResult` (including the refined trade proposal and its stress test score) and applies non-negotiable portfolio constraints before any order reaches the broker. No LLMs, no external market data calls (other than fetching the live portfolio balance), no probabilistic guesswork. If a proposal fails a rule here, the pipeline stops.

## Endpoints

| Method & path | What it does |
|---|---|
| `POST /validate-risk` | Takes a `ChaosTestResult`, returns a `RiskResult` (`is_approved`, `veto_reason`, and the `final_proposal`). Where `workflow/pipeline.py` calls this service. |

## How the rules actually work

`rules.py` implements four independent, unweighted checks. A failure in *any* of them triggers an immediate hard veto.

1. **Chaos Safety Check:** Reads the `is_safe` boolean directly from the `ChaosTestResult`. If `chaos-sandbox` decided the trade exceeds the maximum drawdown threshold (e.g., in an IV crush or spread blowout scenario), this engine does not second-guess it. Veto is automatic.
2. **Allocation Limit (`MAX_ALLOCATION_PCT`):** Checks the proposed `amount` (parsed from `order_details`) against the live portfolio value. Defaults to 5% of the total account. **If the broker call fails, it falls back to a $100k mock balance** rather than crashing the pipeline, ensuring a conservative but functional limit remains in place.
3. **AI Conviction Score (`MIN_CONVICTION_SCORE`):** Ensures the LLM's own self-reported confidence clears a baseline (default 0.80). Even if a trade looks mathematically safe, a low-conviction guess from the strategy layer is blocked.
4. **Portfolio Delta Limit (`MAX_PORTFOLIO_DELTA`):** A placeholder check to prevent the overall account from becoming excessively long or short the market. Currently compares the proposal's `trade_delta` against a static limit (default 0.5) and an assumed 0.0 existing portfolio delta.

**If multiple rules fail simultaneously, the `veto_reason` strings are concatenated via pipes (`|`) into a single rejection message** rather than just returning the first failure. This ensures full visibility into why a trade was blocked when reviewing the dashboard history.

## Architecture and Contract Adherence

This service was originally built with its own local Pydantic models. It has since been strictly aligned with `contracts/schemas.py` to match the orchestrator's expectations:

- **Single Source of Truth:** `ChaosTestResult`, `RiskResult`, and `TradeProposal` are imported directly from the root `contracts.schemas` module.
- **Expansion Joints:** `amount` and `trade_delta` are not top-level fields on the proposal. They are extracted via `.get()` from the `order_details` dict, respecting the intentional flexibility of the contract design.
- **Dynamic Configuration:** Thresholds are loaded dynamically from the root `.env` via `pydantic-settings`. Using `extra="ignore"` ensures that the presence of other services' keys (like Alpaca or Featherless API keys) does not break Pydantic validation on startup.

## Running it

    pip install -r services/risk-engine/requirements.txt

    # from the repo root - PYTHONPATH must include both the root (for
    # contracts/) and this directory
    PYTHONPATH="$(pwd):$(pwd)/services/risk-engine" \
      uvicorn main:app --app-dir services/risk-engine --port 8004

Needs `MAX_ALLOCATION_PCT`, `MIN_CONVICTION_SCORE`, and `MAX_PORTFOLIO_DELTA` in the repo-root `.env`. It also expects `broker-gateway` to be reachable at `BROKER_GATEWAY_URL` (default `http://localhost:8001`) to fetch the live portfolio value for the allocation check.

    curl -X POST http://localhost:8004/validate-risk \
      -H "Content-Type: application/json" \
      -d '{
        "is_safe": true,
        "stress_score": 0.1,
        "logs": ["Spread blowout survived"],
        "refined_proposal": {
          "strategy_id": "test-run-123",
          "action": "BUY",
          "symbol": "AAPL",
          "generated_code": "def evaluate(): pass",
          "conviction_score": 0.85,
          "order_details": {
            "amount": 4000,
            "trade_delta": 0.2
          }
        }
      }'