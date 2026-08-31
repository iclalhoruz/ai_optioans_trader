# Aegis-OptionAI

Autonomous AI US options trading system, built for an Alpaca-sponsored hackathon.
Neuro-symbolic hybrid: an agentic layer proposes trades, a chaos sandbox stress-tests
them under injected market chaos before anything touches real capital, and a
deterministic, non-LLM risk engine has final veto power.

```
Market Data → AI Strategy → Chaos Sandbox → Hard-Veto Risk → Execution
```

- **Neuro/Agentic layer** — LangGraph-style Bull vs. Bear dialectic committee
  synthesizes trade hypotheses and generates the Python code that analyzes them.
- **Chaos Sandbox layer** — the generated code runs in an isolated sandbox under
  injected chaos (500% spread widening, instant IV crush) before it's trusted.
- **Symbolic/Risk layer** — pure deterministic hard-veto gate (portfolio delta
  bounds, max allocation per trade). No LLM involved, on purpose.

## Status

**Shell built, services not written yet, frontend has its first screen.**
`contracts/` and `workflow/pipeline.py` are done and verified against a mocked
service transport. The 4 service folders under `services/` are intentionally
empty — the team hasn't picked each service's internal architecture yet, and
everyone works on their own service folder in parallel once that's decided.
`frontend/` has a Portfolio dashboard screen built against mock data, matching
an approved design and ready for real screens/data to be added on top of the
same component system. See `CLAUDE.md` for the full state of things and the
decisions already locked in.

## Layout

| Path | Port | Purpose |
|---|---|---|
| `contracts/` | — | Shared Pydantic v2 schemas + hexagonal port interfaces. Every service depends on this and nothing else. |
| `services/broker-gateway/` | 8001 | Alpaca connectivity — market data + order execution. *(pending)* |
| `services/ai-strategy/` | 8002 | Agentic strategy generation. *(pending)* |
| `services/chaos-sandbox/` | 8003 | Runs generated code under injected market stress. *(pending)* |
| `services/risk-engine/` | 8004 | Deterministic hard-veto risk gate. *(pending)* |
| `workflow/pipeline.py` | — | Cross-service async orchestrator, chains the 4 services end to end. |
| `frontend/` | 5173 | Dashboard UI (Vite + React + TS + Tailwind). Portfolio screen done, see `frontend/README.md`. |

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
cp .env.example .env          # fill in real values later, mock mode works empty

docker compose up -d redis    # only redis actually comes up right now —
                               # service Dockerfiles don't exist yet

python -m venv .venv && source .venv/bin/activate
pip install -r workflow/requirements.txt

python test_pipeline.py       # runs the real orchestrator against mocked
                               # service responses — proves the pipeline works
                               # end to end even with no services deployed
```

Once a service exists (own `requirements.txt` + `Dockerfile` + `main.py`), add it
to `docker-compose.yml`'s build step and `python -m workflow.pipeline <TICKER>`
will start hitting it for real instead of the mocks.

For the frontend:

```bash
cd frontend
npm install
npm run dev    # http://localhost:5173
```
