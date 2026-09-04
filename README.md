# Aegis-OptionAI

Autonomous AI US options trading system, built for the Alpaca-sponsored
lablab.ai hackathon. Neuro-symbolic hybrid: an LLM proposes trades, a
deterministic scenario/stress test checks them under simulated market
shocks before anything touches real capital, and a deterministic, non-LLM
risk engine has final veto power.

```
Market Data → AI Strategy → Chaos Sandbox → Hard-Veto Risk → Execution
```

- **Neuro/Agentic layer** — an LLM (via Featherless AI) reasons over real
  market data (spot price, option chain Greeks/IV, 40-day price trend) and
  proposes a defined-risk vertical spread (bull call / bear put). It does
  **not** generate or execute code, and never gets direct execution access —
  a structured decision only (direction, contracts, conviction, reasoning).
- **Chaos Sandbox layer** — the proposal's numbers get run through fixed
  stress scenarios (spread blowout, IV crush, adverse price move) via a
  hand-rolled Black-Scholes pricing model, before anything is trusted.
- **Symbolic/Risk layer** — a deterministic hard-veto gate (allocation/delta
  bounds, conviction threshold). No LLM involved, on purpose — nothing
  overrides it, not even the AI that made the proposal.

All four services plus the autonomous scheduler and the frontend dashboard
are built and have been exercised against a real Alpaca paper account. See
**Known limitations** below before treating this as a finished product, and
`CLAUDE.md` for the full build history and every live-verification detail.

## Layout

| Path | Port | Purpose |
|---|---|---|
| `contracts/` | — | Shared Pydantic v2 schemas + hexagonal port interfaces. Every service depends on this and nothing else. |
| `services/broker-gateway/` | 8001 | Real Alpaca connectivity via the official **Alpaca CLI** (not the SDK — see its README for why) for market data + order execution, position exit management, a Redis-backed trade log, plus the HTTP surface for triggering/watching pipeline runs (`/runs`, `/account`, `/clock`). |
| `services/ai-strategy/` | 8002 | LLM decision (Featherless AI) — proposes vertical spreads sized against real portfolio value and conviction. No code generation, no execution access. |
| `services/chaos-sandbox/` | 8003 | Deterministic scenario/stress test on the proposal's real numbers (own Black-Scholes pricing, no external deps). |
| `services/risk-engine/` | 8004 | Deterministic hard-veto risk gate — chaos-safety, allocation limit, conviction threshold, portfolio-delta limit. |
| `workflow/pipeline.py` | — | Cross-service async orchestrator: config-driven step registry, retry/backoff, Redis-backed durable state, non-blocking `start()`/`get_state()` for HTTP triggering. |
| `workflow/scheduler.py` | — | The autonomous piece — polls `broker-gateway`'s `/clock` and, while the market's open, triggers a run per ticker in `WATCHLIST_TICKERS` on an interval, and calls `/positions/manage` every cycle to close positions that hit take-profit/stop-loss/expiring-soon. Runs as its own always-on container. |
| `frontend/` | 5173 | Dashboard UI (Vite + React + TS + Tailwind) — Dashboard, History, Run Detail. See `frontend/README.md`. |

## Why it's split this way

Contract-first, hexagonal architecture: every service only ever depends on
`contracts/`, never on another service's internals. That means:

- 4 people can work in 4 service folders at once without stepping on each
  other's code or git diffs.
- Any service can be swapped or dropped without the others (or the
  orchestrator) needing to change — `workflow/pipeline.py` drives services
  through a config-driven step list, not hardcoded calls.

## Running it

```bash
cp .env.example .env
# fill in ALPACA_API_KEY / ALPACA_SECRET_KEY (a free Alpaca paper account
# works) and FEATHERLESS_API_KEY / FEATHERLESS_MODEL (Featherless is this
# hackathon's LLM partner — see .env.example for the signup notes)

python verify_alpaca_key.py   # confirms the Alpaca keys actually work
```

### Option A — full stack in one command (what a judge should run)

```bash
docker compose up -d --build
```

Brings up Redis, all 4 services, and the autonomous scheduler, fully wired
to talk to each other over the compose network. Then:

```bash
curl http://localhost:8001/health        # broker-gateway is up
curl http://localhost:8001/account       # real paper-account balance
curl -X POST http://localhost:8001/runs -d '{"ticker":"AAPL"}'
#   -> {"runId": "..."} - poll it:
curl http://localhost:8001/runs/<runId>  # watch it move through the pipeline
```

The scheduler container is already doing this automatically every
`SCHEDULER_INTERVAL_MINUTES` for every ticker in `WATCHLIST_TICKERS`,
whenever the market's open — no manual trigger needed for the autonomous
story, the `curl` above is just for watching one run happen on demand.

### Option B — run services individually (for development / per-service logs)

```bash
docker compose up -d redis
python -m venv .venv && source .venv/bin/activate
pip install -r workflow/requirements.txt
python test_pipeline.py                  # orchestrator vs. mocks, no services needed

# each in its own terminal:
pip install -r services/broker-gateway/requirements.txt
PYTHONPATH="$(pwd):$(pwd)/services/broker-gateway" \
  uvicorn main:app --app-dir services/broker-gateway --port 8001

pip install -r services/ai-strategy/requirements.txt
PYTHONPATH="$(pwd):$(pwd)/services/ai-strategy" \
  uvicorn main:app --app-dir services/ai-strategy --port 8002

pip install -r services/chaos-sandbox/requirements.txt
PYTHONPATH="$(pwd):$(pwd)/services/chaos-sandbox" \
  uvicorn chaos_sandbox.main:app --app-dir services/chaos-sandbox --port 8003

pip install -r services/risk-engine/requirements.txt
PYTHONPATH="$(pwd):$(pwd)/services/risk-engine" \
  uvicorn main:app --app-dir services/risk-engine --port 8004

# the autonomous loop, once the 4 above are up:
PYTHONPATH="$(pwd)" python workflow/scheduler.py
```

### Frontend

```bash
cd frontend
npm install
npm run dev    # http://localhost:5173
# set VITE_USE_MOCKS=false in frontend/.env to point it at the real
# broker-gateway above instead of mock data
```

## Known limitations — stated honestly, not glossed over

This system is safe to run against a paper account and demonstrates the
full pipeline end-to-end, but real gaps are still open (all reported,
none hidden — see `CLAUDE.md` for full technical detail and live
reproductions of each):

- **`chaos-sandbox`'s `direction` field isn't cross-validated** against the
  spread's actual leg structure — a mislabeled proposal could get stress-
  tested in the wrong (favorable, not adverse) direction. Not an active
  risk today (`ai-strategy` always sets it correctly), but a real gap in
  the service meant to be the trustworthy, independent check.
- **`risk-engine`'s allocation and portfolio-delta hard-vetoes only
  evaluate the new trade in isolation, not cumulative exposure across
  already-open positions.** Both checks compare the proposed trade against
  a fixed cap on its own (`current_portfolio_delta_pct` is hardcoded to
  `0.0`) rather than adding it to what's already open. Each individual
  trade is small and bounded (`TARGET_ALLOCATION_PCT` targets 3% of
  portfolio, capped well under the 5%/50% hard limits), and open positions
  get closed on a regular cycle, so this isn't believed to be a live risk
  today — but it means many simultaneously-open small positions could in
  principle add up past what either cap was meant to prevent. A real fix
  needs `broker-gateway` to expose real-time aggregate delta/allocation
  across open positions (Alpaca already returns live per-position Greeks,
  no extra pricing model needed) for `risk-engine` to check against -
  deliberately deprioritized given the deadline rather than built
  unverified.
- **Whether the trading strategy itself has a real, positive expectancy is
  honestly unproven, not disproven.** Per-trade risk management (bounded-
  loss spreads, correct position grouping/exit ordering, portfolio-scaled
  sizing, the hard-veto gate) is genuinely solid. Whether the LLM's
  directional calls beat a coin flip over many trades has never been
  backtested — there's a real forward trade log (`GET /pnl` on
  `broker-gateway`) to eventually find out, but no claim of a demonstrated
  edge should be made today. See `CLAUDE.md`'s "Honest profitability
  assessment" for the full reasoning.
