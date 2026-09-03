# Aegis-OptionAI

Autonomous AI US options trading system, built for the Alpaca-sponsored
lablab.ai hackathon (deadline: Sep 4, 6:00 PM Türkiye time). Neuro-symbolic
hybrid: an LLM proposes trades, a deterministic scenario/stress test checks
them under simulated market shocks before anything touches real capital, and
a deterministic, non-LLM risk engine has final veto power.

```
Market Data → AI Strategy → Chaos Sandbox → Hard-Veto Risk → Execution
```

- **Neuro/Agentic layer** — an LLM (via Featherless AI) reasons over real
  market data and proposes a trade. It does **not** generate or execute
  code — a structured decision only (action, conviction, reasoning).
- **Chaos Sandbox layer** — the proposal's numbers get run through fixed
  stress scenarios (spread blowout, IV crush, adverse price move) via a
  small hand-rolled options pricing model, before anything is trusted.
- **Symbolic/Risk layer** — pure deterministic hard-veto gate (portfolio
  delta/allocation bounds, conviction threshold). No LLM involved, on purpose
  — nothing overrides it, not even the AI that made the proposal.

## Status

**`broker-gateway` and the autonomous `scheduler` are both done and verified
against a real Alpaca paper account.** The other 3 services are
architecturally decided but not yet written; the frontend
(Dashboard/History/Run Detail) is done and running on mock data, ready to
point at `broker-gateway` for real. See `CLAUDE.md` for the full state of
things and what's still missing.

## Layout

| Path | Port | Purpose |
|---|---|---|
| `contracts/` | — | Shared Pydantic v2 schemas + hexagonal port interfaces. Every service depends on this and nothing else. |
| `services/broker-gateway/` | 8001 | **Done.** Real Alpaca connectivity (market data + order execution via `alpaca-py`) + the HTTP surface for triggering/watching pipeline runs (`/runs`) + `/account` and `/clock`. |
| `services/ai-strategy/` | 8002 | LLM decision (Featherless AI), no code generation. *(architecture decided, not written)* |
| `services/chaos-sandbox/` | 8003 | Scenario/stress test on the proposal's numbers. *(architecture decided, not written)* |
| `services/risk-engine/` | 8004 | Deterministic hard-veto risk gate. *(architecture decided, not written)* |
| `workflow/pipeline.py` | — | Cross-service async orchestrator + non-blocking `start()`/`get_state()` for HTTP triggering, with a self-pruning Redis index behind `list_recent_run_ids()`. |
| `workflow/scheduler.py` | — | **Done.** The autonomous piece — polls `broker-gateway`'s `/clock` and, while the market's open, triggers a run per ticker in `WATCHLIST_TICKERS` on a `SCHEDULER_INTERVAL_MINUTES` interval. Runs as its own `scheduler` container (`restart: unless-stopped`). |
| `frontend/` | 5173 | Dashboard UI (Vite + React + TS + Tailwind). Done, running on mocks, see `frontend/README.md`. |

## Why it's split this way

Contract-first, hexagonal architecture: every service only ever depends on
`contracts/`, never on another service's internals. That means:

- 4 people can work in 4 service folders at once without stepping on each other's
  code or git diffs.
- Any service can be swapped or dropped without the others (or the orchestrator)
  needing to change — `workflow/pipeline.py` drives services through a config-driven
  step list, not hardcoded calls.

## Running it

```bash
cp .env.example .env
# fill in ALPACA_API_KEY / ALPACA_SECRET_KEY (see CLAUDE.md for how to get
# them) and FEATHERLESS_API_KEY / FEATHERLESS_MODEL

python verify_alpaca_key.py   # confirms the Alpaca keys actually work

docker compose up -d redis

python -m venv .venv && source .venv/bin/activate
pip install -r workflow/requirements.txt
python test_pipeline.py       # proves the orchestrator works against mocks

pip install -r services/broker-gateway/requirements.txt
PYTHONPATH="$(pwd):$(pwd)/services/broker-gateway" \
  uvicorn main:app --app-dir services/broker-gateway --port 8001
# curl http://localhost:8001/account
# curl http://localhost:8001/clock
# curl http://localhost:8001/market-context/AAPL

# in another terminal, once broker-gateway is up - the autonomous loop:
PYTHONPATH="$(pwd)" python workflow/scheduler.py
```

Or, to run `broker-gateway` + `scheduler` + `redis` together as containers:
`docker compose up -d redis broker-gateway scheduler`.

Once `ai-strategy`/`chaos-sandbox`/`risk-engine` exist, add each to
`docker-compose.yml`'s build step and a `POST /runs` on `broker-gateway`
will run the full pipeline for real instead of failing after step 1.

For the frontend:

```bash
cd frontend
npm install
npm run dev    # http://localhost:5173
```
