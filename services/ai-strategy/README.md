# Aegis-OptionAI — ai-strategy

The LLM decision layer. Takes `broker-gateway`'s `MarketContext` for one
ticker and decides whether to buy a single option contract (a call or a
put) or do nothing this cycle. Never generates or executes code, never
talks to Alpaca itself, never has execution access — `chaos-sandbox` and
`risk-engine` are the independent, deterministic checks that keep this
proposal honest before anything real happens.

## Endpoints

| Method & path | What it does |
|---|---|
| `POST /generate-proposal` | Takes a `MarketContext`, returns a `TradeProposal`. Where `workflow/pipeline.py` calls this service. |
| `GET /health` | Liveness check. |

## Why every offered contract is deep ITM and long-dated

This wasn't a style choice — it's the direct consequence of a real
calculation. `chaos-sandbox`'s stress test vetoes any proposal whose
worst-case loss under its `ADVERSE_MOVE` scenario (a 10% move in the
underlying, against the position) exceeds 35%. Checked live with
`chaos_sandbox/pricing.py`'s actual Black-Scholes function before writing
any selection logic:

| DTE | ATM (0% ITM) | 20% ITM | 30% ITM | 40% ITM |
|---|---|---|---|---|
| 30 | 62% loss | 46% | 33% | 25% |
| 90 | 56% | 43% | 32% | 25% |
| 180 | 46% | 38% | 30% | 24% |
| 365 | 37% | 32% | 27% | 23% |

A single long option is extremely leveraged — an at-the-money call loses
roughly 60–100% of its value under a 10% adverse move **regardless of
expiry**, and even a 40%-deep-ITM 30-day call still loses ~25%. Only
contracts deep enough ITM and far enough dated (where the option behaves
close to owning the underlying itself, rather than a highly leveraged bet)
realistically clear the 35% threshold with real margin. A near-the-money
or short-dated strategy would have been architecturally correct but would
never have actually gotten a trade past `chaos-sandbox` — bad for the
hackathon's P&L judging criterion even though everything else "worked."

**This is a real, deliberate scope limitation of the system today, not a
permanent one.** `broker-gateway` already supports multi-leg (spread)
orders — live-tested with a real filled call spread — because a defined-risk
spread's max loss is capped at the net debit paid, so it would survive
`ADVERSE_MOVE` at much shorter dates and closer-to-the-money strikes.
`chaos-sandbox` doesn't model multi-leg P&L yet (explicitly scoped to
single-leg long options in its own README), so `ai-strategy` doesn't
propose spreads — not because the architecture can't, but because the one
service that would need to evaluate the risk of one doesn't yet.

**Does `ai-strategy` support spreads? No — deliberately not, and it's not
a gap in this service specifically.** `broker-gateway`'s `execute_order`
already accepts a `legs` list in `order_details` and genuinely executes a
multi-leg order (verified live). But `chaos-sandbox`'s `OptionStressInputs`
has no `legs` field at all and uses `extra="forbid"` — sending one would
get the whole proposal rejected with `422 extra_forbidden` before it ever
reached risk-engine or execution. So even though the *execution* layer is
ready, proposing a spread today would just break the pipeline one step
later. `ai-strategy` only ever builds single-leg `order_details` for
exactly this reason. Adding spread support here would be pointless without
`chaos-sandbox` growing multi-leg P&L modeling first.

## How contract selection actually works

`llm.py`'s `_select_contracts_for_prompt`:

1. Filters `MarketContext.chain_summary.contracts` to ones with a live
   bid/ask and `days_to_expiry >= MIN_DAYS_TO_EXPIRY` (180 by default).
2. Groups by option type and, within each, keeps **one contract per
   distinct strike** — whichever expiration is longest-dated for that
   strike (more time value cushion, more margin under the stress test).
   Without this, a single strike listed across many expirations (common in
   real chains) would crowd out genuinely different strikes.
3. Ranks each group by closeness to `TARGET_ITM_PCT` (25% by default) —
   `spot * (1 - 0.25)` for calls, `spot * (1 + 0.25)` for puts.
4. Takes half of `CONTRACTS_IN_PROMPT` from calls and half from puts, so
   the model gets a genuine bullish-or-bearish choice instead of whichever
   side happened to have a strike land closer to target.

This depends on `broker-gateway` actually having deep-ITM contracts to
offer in the first place — its `get_market_context` fetches a second,
targeted strike band (60%–140% of spot, filtered server-side to 180+ days
out) specifically for this; see `services/broker-gateway/README.md`.

## What the model actually decides — and what it doesn't

The model is shown a JSON payload (ticker, spot price, IV, and the
selected contracts — symbol, type, strike, DTE, bid/ask, IV, delta) and
asked to return:

```json
{
  "action": "BUY" or "HOLD",
  "contract_symbol": "<one of the symbols it was shown, or omitted for HOLD>",
  "conviction_score": 0.0-1.0,
  "reasoning": "one or two sentences"
}
```

It only ever picks **which contract** and **a direction/conviction** —
never `SELL` (chaos-sandbox has no short-margin model, would veto it
regardless, so the prompt doesn't even offer it as an option). **Every
number in the resulting `TradeProposal.order_details` is looked up from
the real chain data the model was shown, never taken from the model's own
arithmetic** — it can be wrong about which contract looks good, it can't
be wrong about what that contract actually costs. `quantity` is fixed at
`1` for this version — no portfolio-aware position sizing yet, deliberately
simple.

`order_details` for a `BUY` contains *only* the fields
`chaos-sandbox`'s `OptionStressInputs` model accepts (`option_type`,
`quantity`, `limit_price`, `spot_price`, `strike`, `implied_volatility`,
`days_to_expiry`, `bid`, `ask`) — no `symbol`/`direction`/`description`/
`reasoning`. Those would collide with `OptionStressInputs`'s
`extra="forbid"` schema (verified live: adding them gets the whole request
rejected with `422 extra_forbidden`). `runs.py`'s `_strategy_decision()`
already degrades gracefully with defaults when they're absent, so the
frontend still renders a (plainer) card — nothing else breaks.

## Reliability — never a crash, never a hallucinated number

- **Invalid JSON / wrong shape / empty response**: one retry, with the
  validation error fed back to the model and an instruction to send only
  the corrected JSON. Still invalid after that → falls back to `HOLD`.
- **The Featherless API call itself fails** (network error, rate limit,
  timeout, bad key, provider outage - anything `openai.OpenAIError`) - one
  bare retry (no corrective message makes sense for a transport failure),
  then `HOLD`. Verified live with a deliberately invalid API key: two real
  401s, then a clean `HOLD` - never an unhandled exception.
- **Model picks a `contract_symbol` not in the list it was shown** (i.e.
  invents one): falls back to `HOLD`.
- **A contract has data chaos-sandbox's strict schema would reject** -
  `implied_volatility: None` (confirmed live: Alpaca genuinely returns this
  for some illiquid contracts, alongside zeroed Greeks), a zero or crossed
  `ask`/`bid` - filtered out of the candidate pool entirely before the LLM
  ever sees it, not just before submission.
- **Chain has nothing eligible** (nothing survives the filters above, or
  nothing clears `MIN_DAYS_TO_EXPIRY`): falls back to `HOLD` before ever
  calling the LLM.
- **Anything else unexpected** (e.g. malformed upstream data -
  `chain_summary` is a loose, unvalidated dict by design): `main.py`'s
  endpoint wraps the whole call in a catch-all that logs and returns
  `HOLD` rather than ever surfacing an unhandled 500 to the pipeline - an
  autonomous step failing outright is worse than a conservative `HOLD` it
  can just try again next cycle.
- A `HOLD` proposal always has `conviction_score=0.0` and a `reasoning`
  field in `order_details` explaining why (visible to `chaos-sandbox`,
  which never validates `order_details` for `HOLD` at all).

## Running it

```bash
pip install -r requirements.txt

# from the repo root - PYTHONPATH must include both the root (for
# contracts/) and this directory
PYTHONPATH="$(pwd):$(pwd)/services/ai-strategy" \
  uvicorn main:app --app-dir services/ai-strategy --port 8002
```

Needs `FEATHERLESS_API_KEY`/`FEATHERLESS_MODEL` in the repo-root `.env`
(loaded via `python-dotenv` at the top of `main.py` for local runs; Docker
gets them from `docker-compose.yml`'s `env_file` instead).

```bash
curl http://localhost:8002/health
curl -X POST http://localhost:8002/generate-proposal \
  -H "Content-Type: application/json" \
  -d @<(curl -s http://localhost:8001/market-context/AAPL)
```

## Verified live, at every level (2026-09-03)

Not just unit-tested against mocks:

- Fetched a real `MarketContext` from a running `broker-gateway` and got a
  real Featherless completion back on the first attempt.
- Fed the resulting `TradeProposal` into `chaos-sandbox`'s real
  `OptionStressInputs.model_validate()` — accepted, zero `extra_forbidden`
  errors — and its real stress engine, which correctly `VETO`'d an early
  near-the-money test proposal (99.9% worst-case loss) and correctly
  `SAFE`'d a later deep-ITM one (a real 470+-DTE ~25%-ITM AAPL call, 77%
  survival score).
- Ran a full `POST /runs` through `broker-gateway` with `ai-strategy` and
  `chaos-sandbox` both actually running: `market_context` → `trade_proposal`
  → `chaos_result` all succeed — the pipeline's first time ever reaching
  past `trade_proposal`, and the first proposal to ever survive the stress
  test. Stops at `risk_result`, `risk-engine`'s known, already-tracked
  contract-mismatch gap (its author is mid-fix) — the only thing left
  between this and a fully real, executed autonomous trade.
