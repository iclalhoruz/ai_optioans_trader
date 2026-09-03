# Aegis-OptionAI — ai-strategy

The LLM decision layer. Takes `broker-gateway`'s `MarketContext` for one
ticker and decides whether to buy a defined-risk vertical spread (a bull
call spread or a bear put spread) or do nothing this cycle. Never
generates or executes code, never talks to Alpaca itself, never has
execution access — `chaos-sandbox` and `risk-engine` are the independent,
deterministic checks that keep this proposal honest before anything real
happens.

## Endpoints

| Method & path | What it does |
|---|---|
| `POST /generate-proposal` | Takes a `MarketContext`, returns a `TradeProposal`. Where `workflow/pipeline.py` calls this service. |
| `GET /health` | Liveness check. |

## Why a spread, not a single contract

This service originally proposed a single deep-ITM, long-dated long option.
Checked exhaustively with `chaos_sandbox/pricing.py`'s real Black-Scholes
function (ITM% × DTE grid) that **there is no combination for a
higher-priced ticker (the whole watchlist: AAPL/TSLA/NVDA/SPY/MSFT) that
clears both `chaos-sandbox`'s 35% stress-test threshold and risk-engine's
5% `MAX_ALLOCATION_PCT` cap at once** — a single deep-ITM contract on a
$300+ stock can cost $10,000+, well over 5% of a $100k account regardless
of expiry.

A defined-risk **vertical spread** fixes both problems at once: the short
leg funds part of the cost (cheaper) and caps the maximum loss at the net
debit paid (safer), so it clears both constraints with real margin at a
fraction of the capital. `chaos-sandbox` added multi-leg net-debit spread
support (`SpreadStressInputs`/`calculate_spread_scenarios`, see
`services/chaos-sandbox/README.md`) specifically to unlock this —
`broker-gateway`'s multi-leg execution was already ready and live-tested
before that.

## How spread selection actually works

`llm.py`'s `_select_spread_candidates` builds **up to two candidates** — one
bull call spread, one bear put spread — so the model gets a genuine
bullish-or-bearish choice, or neither:

1. Filters `MarketContext.chain_summary.contracts` to ones with a live,
   non-crossed bid/ask, a real `implied_volatility`, and
   `days_to_expiry >= SPREAD_MIN_DAYS_TO_EXPIRY` (90 default).
2. Picks the expiration closest to `SPREAD_TARGET_DAYS_TO_EXPIRY` (270
   default) and a long leg near `SPREAD_LONG_ITM_PCT` ITM (15% default).
3. Picks a short leg further out of the money on the *same* expiration
   (chaos-sandbox's `SpreadStressInputs` requires every leg to share one
   `days_to_expiry` for a debit spread to be evaluable at all) — but not
   just the nearest strike to a target width. **Real strike increments
   (e.g. $10 apart on AAPL's far-dated chain) are coarser than a naive
   width target** — checked live and found the nearest-to-target short
   strike could leave a net debit consuming almost the entire width (a
   real case: $9.47 debit on a $10-wide spread, $0.53 max gain — an
   unusably bad risk/reward). So it walks short-strike candidates ordered
   by closeness to `SPREAD_WIDTH_PCT` of spot (10% default) and keeps the
   first one where the net debit doesn't exceed
   `SPREAD_MAX_DEBIT_TO_WIDTH_RATIO` (68% default) of the strike width.

**That ratio cap was itself tuned against live, moving market data, not
guessed.** Tested the same AAPL long leg against five different short
strikes on one consistent snapshot: a narrower spread (debit ~80-90% of
width) scored close to the 35% veto line (29-31%) — fine on that exact
snapshot, but a same-shaped spread failed outright (45.5%) a few minutes
later once real IV/price had moved. Wider spreads (debit ~65-69% of width)
scored consistently better (23-25%) with real margin against that kind of
noise, which is why the ratio is capped where it is.

## Price trend — real evidence for the model's directional call

`broker-gateway` fetches `chain_summary.price_trend` (recent % change over
a few windows, distance from the recent high/low, realized volatility -
all computed in code, not handed to the model as raw bars) and it's
included in the prompt. Still no guarantee of real predictive edge, but
it's the difference between reasoning over real, if modest, momentum
evidence and reasoning over nothing at all. Verified this is genuinely
used, not decorative: a real `INTC` run produced a `HOLD` explicitly
citing "negative momentum over both 5 and 20 days."

## Position sizing — not always 1 spread

`quantity` used to be hardcoded to `1`. `_size_quantity` now computes a
real number: `portfolio_value * TARGET_ALLOCATION_PCT * conviction_score`,
divided by the spread's net debit (`ask - bid`, not a single option's
cost), capped at `MAX_CONTRACTS_PER_TRADE` (5 default). `portfolio_value`
comes from a live call to `broker-gateway`'s `GET /account` right before
sizing (falls back to a conservative 1 spread if that call fails - a
portfolio-value hiccup shouldn't block a trade the model already decided
on). **If even 1 spread costs more than the computed budget, the proposal
degrades to `HOLD`** with a clear reason, rather than forcing an oversized
position or crashing.

## What the model actually decides — and what it doesn't

The model is shown a JSON payload (ticker, spot price, IV, price trend, and
the candidate spreads — each with its long/short leg symbols and strikes,
days to expiry, net debit, and max gain) and asked to return:

```json
{
  "action": "BUY" or "HOLD",
  "spread_id": "<one of the spread_id values it was shown, or omitted for HOLD>",
  "conviction_score": 0.0-1.0,
  "reasoning": "one or two sentences"
}
```

It only ever picks **which spread** (bullish or bearish) and a
**conviction** — never `SELL` (this system has no short-margin/naked-sell
support). **Every number in the resulting `TradeProposal.order_details` is
looked up from the real market data the model was shown, never taken from
the model's own arithmetic** — it can be wrong about which spread looks
good, it can't be wrong about what that spread actually costs.

`order_details` for a `BUY` matches `chaos-sandbox`'s `SpreadStressInputs`
exactly: `direction` (`bullish`/`bearish`), `quantity`, a positive net
`limit_price`, `spot_price`, and `legs` (2 entries — each with its own
`symbol`, `option_type`, `strike`, `implied_volatility`, `days_to_expiry`,
`bid`/`ask`, `ratio_qty`, `side`, `position_intent`). `TradeProposal.symbol`
is the **underlying ticker** (e.g. `"AAPL"`), not an option symbol —
`chaos-sandbox` cross-checks every leg's OCC symbol against this field.
Both `SpreadStressInputs` and `SpreadLegInputs` use `extra="forbid"`, so no
extra keys (`description`/`reasoning`, etc.) are added at either level.

## Reliability — never a crash, never a hallucinated number

- **Invalid JSON / wrong shape / empty response**: one retry, with the
  validation error fed back to the model and an instruction to send only
  the corrected JSON. Still invalid after that → falls back to `HOLD`.
- **The Featherless API call itself fails** (network error, rate limit,
  timeout, bad key, provider outage - anything `openai.OpenAIError`) - one
  bare retry (no corrective message makes sense for a transport failure),
  then `HOLD`. Verified live with a deliberately invalid API key: two real
  401s, then a clean `HOLD` - never an unhandled exception.
- **Model picks a `spread_id` not in the list it was shown** (i.e. invents
  one): falls back to `HOLD`.
- **A leg has data `chaos-sandbox`'s strict schema would reject** -
  `implied_volatility: None` (confirmed live: Alpaca genuinely returns this
  for some illiquid contracts, alongside zeroed Greeks), a zero or crossed
  `ask`/`bid` - filtered out of the candidate pool entirely before the LLM
  ever sees it, not just before submission.
- **No viable spread exists** (nothing survives the filters above, no long
  leg clears `SPREAD_MIN_DAYS_TO_EXPIRY`, or no short leg keeps the net
  debit under `SPREAD_MAX_DEBIT_TO_WIDTH_RATIO` of the width): falls back
  to `HOLD` before ever calling the LLM.
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
gets them from `docker-compose.yml`'s `env_file` instead). Position sizing
also needs `broker-gateway` reachable at `BROKER_GATEWAY_URL` for its
`GET /account` call - falls back to sizing 1 spread if that fails, so this
service still works standalone, just less precisely.

```bash
curl http://localhost:8002/health
curl -X POST http://localhost:8002/generate-proposal \
  -H "Content-Type: application/json" \
  -d @<(curl -s http://localhost:8001/market-context/AAPL)
```

## Verified live, at every level (2026-09-03)

Not just unit-tested against mocks:

- Fetched real `MarketContext`s from a running `broker-gateway` for
  multiple tickers (AAPL, TSLA, NVDA, F, INTC) and got real Featherless
  completions back.
- Submitted the generated candidate spreads directly to `chaos-sandbox`'s
  real `/stress-test` - confirmed both `SAFE` (AAPL bull call spread, 30.3%
  worst-case loss; AAPL bear put spread, 22.4%) and `VETO` outcomes (a
  narrower AAPL spread at 45.5%; a TSLA call spread at 40.0% - real,
  ticker-specific IV differences, not a bug) against real, moving market
  data - not assumed to pass.
- Ran full `POST /runs` cycles through `broker-gateway` with `ai-strategy`
  and `chaos-sandbox` both actually running, across five tickers:
  `market_context` → `trade_proposal` → `chaos_result` all succeed in every
  case. A real `INTC` run produced a genuine `HOLD` driven by the new
  price-trend data ("negative momentum over both 5 and 20 days"); other
  runs correctly judged neither spread had a strong enough signal. Stops at
  `risk_result`, `risk-engine`'s known, already-tracked contract-mismatch
  gap (its author is mid-fix) — the only thing left between this and a
  fully real, executed autonomous spread trade.
