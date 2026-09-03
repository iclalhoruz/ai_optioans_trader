# Aegis-OptionAI — broker-gateway

The only service in the whole system that talks to Alpaca directly — via
Alpaca's own official **CLI** (`alpacahq/cli`, the `alpaca` binary), not a
Python SDK. Every other service only ever sees `contracts/` shapes — none of
them know Alpaca exists. Also hosts the HTTP surface over
`workflow/pipeline.py`'s `PipelineOrchestrator`, so a run can be
triggered/watched over the network (by the frontend, the scheduler, or curl)
instead of only from the CLI entrypoint in `workflow/pipeline.py`.

## Endpoints

| Method & path | What it does |
|---|---|
| `GET /market-context/{ticker}` | Real spot price + a strike-windowed option chain (bid/ask/IV/Greeks) for `ticker`. |
| `POST /execute-order` | Submits a real order from a `TradeProposal` — single-contract or multi-leg (see below). |
| `GET /account` | Real Alpaca paper account info (portfolio value, cash, buying power, options trading level). |
| `GET /clock` | Real market hours. `workflow/scheduler.py` polls this before triggering a run, so it stays true that this is the only service that ever talks to Alpaca. |
| `GET /health` | Liveness check. |
| `POST /runs` | Starts a pipeline run (`PipelineOrchestrator.start`), returns a `runId` immediately — non-blocking. |
| `GET /runs/active` | The most recently *started* run's full detail (not necessarily still running — matches the frontend's own semantics for "the run to show on Dashboard"). |
| `GET /runs/recent` | Last 20 runs as summaries. Self-heals: a stale id (state expired past its 24h Redis TTL, index entry left behind) is skipped and pruned instead of 500ing. |
| `GET /runs/{run_id}` | One run's full detail. |
| `GET /positions` | Real open positions (`alpaca position list`). |
| `POST /positions/manage` | Checks every open position against deterministic exit rules (take-profit/stop-loss/expiring-soon) and closes any that trigger. `workflow/scheduler.py` calls this once per autonomous cycle. |
| `GET /trades` | Recent trade log entries (opens and closes) — see "Trade log & P&L" below. |
| `GET /pnl` | Aggregated realized P&L across the trade log. |

`runs.py` also translates `PipelineState` (snake_case, backend-internal)
into the exact camelCase shape `frontend/src/types/domain.ts` expects
(`RunDetail`/`RunSummary`) — the frontend was built against those types
before this service existed, so the adaptation lives here rather than
changing either side to match the other.

## Why the Alpaca CLI, not the SDK or the MCP server

The hackathon's core requirements are explicit: *"MCP or CLI — projects
must utilize either Alpaca's MCP server or its CLI tools."* Using
`alpaca-py` (the Python SDK) directly, as an earlier version of this service
did, doesn't satisfy that literally — it's neither of the two named options.

Between the two real choices:

- **MCP server** (`alpacahq/alpaca-mcp-server`) exists to give an LLM chat
  client *direct tool-calling execution access* to Alpaca. Its own docs
  (docs.alpaca.markets/us/docs/alpaca-mcp-server) list only AI chat/IDE
  clients as supported (Claude Desktop, Cursor, VS Code, PyCharm, Claude
  Code, Gemini CLI) — nothing about calling it from a plain backend service.
  It also doesn't fit this project's own architecture: `ai-strategy`'s LLM
  deliberately never gets direct execution access to Alpaca (it only
  returns a structured `TradeProposal`), specifically so risk-engine's hard
  veto stays real. Giving the LLM MCP tool-calling would undo that.
- **CLI** (`alpacahq/cli`) is a separate, official Go binary explicitly
  built "for AI agents, scripts, and automation pipelines" — exactly what
  this service is. It's what `alpaca_client.py` actually shells out to.

Verified live against a real paper account before writing any code: `alpaca
account get`, `alpaca clock`, `alpaca data latest-trade`, `alpaca data
option chain` (confirmed it returns real Greeks + IV, same shape the
service needs), and `alpaca order submit` with `--order-class mleg --legs
'[...]'` (confirmed via `--dry-run` that the request body comes out
correctly, `ratio_qty` has to be a JSON *string*, not a number, or the CLI
rejects it).

## How it actually works

`alpaca_client.py` has one private helper, `_cli(*args)`, that runs
`subprocess.run(["alpaca", *args], capture_output=True, text=True)` and
parses the result:

- **Success**: exit code `0`, the command's JSON result on **stdout**.
- **Failure**: non-zero exit code, a JSON error object (`{"status":
  ..., "error": ...}`) on **stderr** — raised as `AlpacaCLIError`, which
  `main.py` catches and turns into a clean HTTP 4xx (verified live with a
  malformed ticker: `400`, Alpaca's own `"invalid symbol: ..."` message).

Every method on `AlpacaBrokerGateway` is just a thin wrapper that builds the
right `alpaca ...` argument list and shapes the JSON that comes back into
`contracts/schemas.py` types:

- `get_market_context` → `alpaca data latest-trade` (spot price) +
  `alpaca data option chain --strike-price-gte/-lte ...`, paginated via
  `_fetch_option_chain` — see "Option chain pagination" below.
- `execute_order` → `alpaca order submit`, with `--legs '[...]'` +
  `--order-class mleg` when `order_details["legs"]` is present, a plain
  `--symbol/--side` order otherwise.
- `get_account` → `alpaca account get`.
- `get_clock` → `alpaca clock`.

## Option chain pagination

`alpaca data option chain` paginates past 100 results by default (server
max per page is 1000). A single call can't be trusted to have the whole
±`STRIKE_WINDOW` chain — checked live and found **SPY returns 834
contracts and QQQ 748** within just a ±$10 window, both comfortably past
what an earlier fixed `--limit 500` was silently truncating to (both
tickers are in the default `WATCHLIST_TICKERS`, so this would have quietly
fed `ai-strategy` an incomplete chain for two of five watchlist tickers,
forever, with no error anywhere). `_fetch_option_chain` now always follows
`next_page_token` until it's empty instead of trusting one page.

## Two chain windows, not one

`get_market_context` fetches **two separate strike windows**, merged into
one `chain_summary.contracts` list:

1. **Near-the-money** (±`STRIKE_WINDOW`, $10): general market snapshot,
   also what `MarketContext.implied_volatility` (the top-level field) is
   averaged from.
2. **Deep-ITM, long-dated** (`ITM_STRIKE_LOW_PCT`-`ITM_STRIKE_HIGH_PCT` of
   spot, i.e. 60%-140%, filtered server-side to `ITM_MIN_DAYS_TO_EXPIRY`+
   days via `--expiration-date-gte`): added because `ai-strategy`'s
   strategy specifically needs these (a near-the-money option
   mathematically can't survive chaos-sandbox's stress test regardless of
   expiry — see `services/ai-strategy/README` or `CLAUDE.md` for the real
   Black-Scholes numbers behind that). Without this second fetch, those
   contracts simply wouldn't be in the data `ai-strategy` receives at all.

The two windows overlap for long-dated contracts already near the money -
harmless, the merge just re-writes identical data for those symbols.

## Price trend — `chain_summary.price_trend`

`get_market_context` also fetches `PRICE_TREND_LOOKBACK_DAYS` (40) of daily
bars (`alpaca data bars`) and reduces them to a few real numbers -
`change_5d_pct`, `change_20d_pct`, `change_period_pct`, `pct_from_high`,
`pct_from_low`, `realized_volatility_annualized` - instead of handing
`ai-strategy` raw bars to compute trend from itself. Before this,
`ai-strategy`'s model only ever saw a single point-in-time snapshot with no
basis at all to form a directional view; this gives it real, if modest,
momentum/trend evidence instead. Computed in code, not by the model, for
the same reason every other number in this system is - LLMs are unreliable
at doing precise arithmetic over a table of rows.

## Position management — exit rules, not just entries

`services/broker-gateway/position_manager.py` is the counterpart to
`ai-strategy`'s entry decision: without it, a filled position just sits
held until expiration regardless of P&L, which isn't risk management, it's
"buy and forget." `POST /positions/manage` groups every open position by
`(underlying, expiration_date)`, checks each group against three
deterministic (no LLM) rules using its **net** P&L across all its
positions, and closes the whole group together if one triggers:

- **Take-profit**: net `unrealized_plpc >= TAKE_PROFIT_PCT` (25% default)
- **Stop-loss**: net `unrealized_plpc <= -STOP_LOSS_PCT` (20% default)
- **Expiring soon**: `days_to_expiry <= MIN_DAYS_BEFORE_CLOSE` (14 default) -
  parsed from each position's own OCC symbol via `_parse_occ_symbol`, no
  extra API call needed

**Grouping (not per-position evaluation) is load-bearing, not a nicety —
found and fixed live, not in review.** Alpaca lists each leg of a filled
multi-leg spread as its own separate position with its own independent
`unrealized_pl`/`unrealized_plpc`. An earlier version of this evaluated
and closed positions independently, which can trigger take-profit on one
leg while leaving the other open — turning a *defined-risk* spread into an
accidental naked position with *unbounded* risk. This actually happened in
testing: it closed exactly the profitable leg of a real spread and left
the losing leg (-57%) open.

**Close order within a group matters too — also found live, not in
review.** Closing the long leg first while the short leg is still open
leaves an "uncovered" short position; Alpaca rejected that outright
(`account not eligible to trade uncovered option contracts`) on a real
order, and the pre-fix code then went ahead and closed the *short* leg
anyway — leaving the wrong leg (a naked long) open instead of a flat
position. Short legs are now closed first (always safe — a long remaining
alone is never "uncovered"), and if a short leg's close fails, the group's
long leg(s) are deliberately **not** attempted (would create the exact
uncovered position above) — the group is left in its original, still-
hedged shape for the next cycle instead.

Deliberately **not** wired into `workflow/pipeline.py`'s entry pipeline
(market context → proposal → stress test → risk gate → execute) - closing
an existing position is risk-*reducing*, not a new bet, so it doesn't need
a fresh proposal/stress-test/veto cycle the way opening one does.
`workflow/scheduler.py` calls this once per autonomous cycle, right
alongside triggering new-entry runs.

**Verified live end-to-end after both fixes**: opened a real 2-leg AAPL
spread, forced a stop-loss trigger (temporary threshold override, not
mocked), and confirmed the short leg closed first, the long leg closed
second, and the account ended fully flat (zero open positions) — plus one
aggregated `trade_log` entry with the correct net realized P&L (see below),
not two misleadingly-independent ones. `manage_positions()` still reports
`closed: false` with the error for any leg that doesn't actually close,
rather than only ever reporting successes.

## Trade log & P&L — `services/broker-gateway/trade_log.py`

A Redis-backed record of what this system actually did - not a backtest,
a real forward trade log. `POST /execute-order` records one "open" entry
per trade (already correct - one proposal, one entry). `POST
/positions/manage` records **one "close" entry per closed group, not one
per leg** - summing all its legs' realized P&L into a single net figure.
This wasn't the original behavior and was a real bug, not a style choice:
logging per-leg closes meant a single net-profitable spread trade (one
leg down individually, the other up more) could count as "1 win + 1 loss"
in `GET /pnl`'s `winCount`/`winRatePct`, understating a system that's
actually working. `GET /pnl` aggregates the closed entries into
`totalRealizedPnl`/`closedTradeCount`/`winCount`/`winRatePct` - now
one-count-per-trade, matching what "trade" actually means for this
strategy. This is what makes "is the autonomous system actually making
money" answerable with real, trustworthy numbers instead of "the pipeline
ran successfully" - those are different claims, and a wrong win-rate would
have undermined the first one specifically.

## Order execution — `order_details` conventions

`TradeProposal.order_details` is a loose `dict` by design
(`contracts/schemas.py`) — these are the keys `alpaca_client.py` actually
reads, i.e. what `ai-strategy`'s author needs to populate:

- **Single-contract order** (the common case): `symbol`, `qty` (or
  `quantity`), `direction`, `description`, `reasoning`, optionally
  `limit_price` (omit for a market order) and `time_in_force` (defaults to
  `"day"`).
- **Multi-leg order** (a spread — call spread, straddle, etc.): a `legs` key
  holding a list of `{symbol, ratio_qty, side, position_intent}` dicts,
  Alpaca's real `mleg` order shape (`side` is `"buy"`/`"sell"`,
  `position_intent` is `"buy_to_open"`/`"buy_to_close"`/`"sell_to_open"`/
  `"sell_to_close"`) — up to 4 legs, matching the Saga-compensation hooks
  already wired into `workflow/pipeline.py`'s `StepConfig` for unwinding a
  partially-filled spread.

A `HOLD` proposal never reaches Alpaca — `execute_order` returns a
`NO_ACTION` `ExecutionResponse` instead of attempting a broken order.

**Idempotency**: every submission passes `--client-order-id
<proposal.strategy_id>`. `workflow/pipeline.py`'s HTTP client times out
after `STEP_TIMEOUT_SECONDS` (10s default) and retries, but this service's
own internal CLI call timeout is 30s - a slow call could still be in
flight when the pipeline retries, which without this would risk submitting
the same trade twice. Since a retry of the same pipeline step reuses the
same `TradeProposal` (same `strategy_id`), Alpaca rejects the duplicate
client_order_id instead of placing a second real order; a genuinely new
proposal always gets a new `strategy_id`. Verified live: submitting the
same `strategy_id` twice — second call came back `422 client_order_id must
be unique`, first one went through normally.

## Running it

```bash
# the alpaca CLI itself, once per machine (not a pip package)
brew install alpacahq/tap/cli      # or: go install github.com/alpacahq/cli/cmd/alpaca@latest
alpaca doctor                      # confirms it can see ALPACA_API_KEY/ALPACA_SECRET_KEY and reach Alpaca

pip install -r requirements.txt

# from the repo root - PYTHONPATH must include both the root (for
# contracts/ and workflow/) and this directory (--app-dir alone isn't enough)
PYTHONPATH="$(pwd):$(pwd)/services/broker-gateway" \
  uvicorn main:app --app-dir services/broker-gateway --port 8001
```

Needs `ALPACA_API_KEY`/`ALPACA_SECRET_KEY` in the repo-root `.env` — both
`python-dotenv` (loaded at the top of `main.py`) and the `alpaca` CLI itself
read these same two env var names directly, nothing extra to configure.
Docker gets them from `docker-compose.yml`'s `env_file` instead, and its
`Dockerfile` installs the same pinned CLI version into the image.
`verify_alpaca_key.py` at the repo root is a quick way to sanity-check the
keys before starting this.

```bash
curl http://localhost:8001/health
curl http://localhost:8001/account
curl http://localhost:8001/clock
curl http://localhost:8001/market-context/AAPL
curl -X POST http://localhost:8001/runs -d '{"ticker":"AAPL"}'
# will fail at trade_proposal until ai-strategy exists - expected, not a bug
```

## Hardening pass (2026-09-03)

Once the core build was verified against real Alpaca data, went back
through it looking for what would actually break before the deadline —
each of these was found and confirmed via a live `curl`, not just read
through:

- **CORS.** No middleware existed at all — the moment the frontend flips
  `VITE_USE_MOCKS=false` and calls this service directly from a browser,
  every request would've been silently blocked. Added `CORSMiddleware`,
  origins from `CORS_ALLOWED_ORIGINS` (repo-root `.env` /
  `.env.example`, defaults to the frontend's dev origin
  `http://localhost:5173`). Server-to-server callers (the scheduler,
  `workflow/pipeline.py`) were never affected either way — CORS only
  applies to browser requests.
- **Unhandled 500s on a bad ticker.** `GET /market-context/123INVALID#`
  used to throw a raw, unhandled 500. Now `AlpacaCLIError` is caught in
  both `/market-context/{ticker}` and `/execute-order` and turned into a
  clean 4xx with Alpaca's real error message.
- **Blocking calls inside `async def`.** The CLI subprocess call is
  synchronous by nature — every call
  (`get_market_context`/`execute_order`/`get_account`/`get_clock`) runs its
  `subprocess.run` inside `asyncio.to_thread(...)` so it doesn't block the
  event loop for however long the process takes.
- **No multi-leg order support.** `execute_order` could only ever submit a
  single-contract order — a real gap given the project's own thesis is
  options *strategies*, not single contracts, and the Saga-compensation
  hooks in `pipeline.py` exist specifically for multi-leg unwinding. Added
  the `legs` convention described above.
- **Switched from the `alpaca-py` SDK to the official CLI entirely**, for
  every Alpaca call this service makes — see "Why the Alpaca CLI" above.
  This was the biggest change of the pass: `alpaca-py` is no longer a
  dependency of this service at all (removed from `requirements.txt`); the
  `Dockerfile` now installs the `alpaca` binary instead.

**Multi-leg order — now live-tested for real (2026-09-03).** A real 1-lot
`AAPL` call spread (buy 260904C00330000 / sell 260904C00332500) was
submitted through the actual `POST /execute-order` endpoint end-to-end —
not `--dry-run`, a real order. Alpaca accepted and **filled** both legs
(`buy_to_open` @ $2.00, `sell_to_open` @ $1.04, net debit $0.96 matching
`ExecutionResponse.filled_avg_price`); confirmed independently via `alpaca
order get` and `alpaca position list` that both legs and the resulting
positions are really there. Portfolio value moved from $100,000.00 to
$99,995.95, exactly as expected. Multi-leg is no longer a "not yet tested"
item.

## Full re-audit after the CLI migration (2026-09-03)

Went back through `alpaca_client.py`/`main.py` once more looking for gaps
the migration itself might have introduced, and ran a 17-point live test
pass (health, account, clock, market-context on two different tickers, a
malformed ticker, a well-formed-but-nonexistent ticker, CORS, a HOLD order,
a full `POST /runs` cycle, `/runs/recent`, `/runs/active`, a missing
run id, `docker compose config`, and confirming no `alpaca-py` import or
dependency remained anywhere) — all passed. Found and fixed two real gaps:

- **`_cli()` didn't catch `FileNotFoundError`/`subprocess.TimeoutExpired`.**
  If the `alpaca` binary isn't on `PATH`, or a call takes longer than 30s,
  either would have propagated as an unhandled 500 instead of a clean
  error. Both now map to `AlpacaCLIError` (500 and 504 respectively) -
  verified in isolation that Python really does raise these two exception
  types for these two cases.
- **`/account` and `/clock` never caught `AlpacaCLIError` at all** - only
  `/market-context` and `/execute-order` did, so a CLI failure on those two
  endpoints would have leaked as an unhandled 500. Rather than repeat the
  same try/except a third and fourth time, replaced all four with one
  `@app.exception_handler(AlpacaCLIError)` - no endpoint can forget to
  catch it now, by construction.
