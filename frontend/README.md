# Aegis-OptionAI — frontend

Dashboard UI for the trading pipeline. Vite + React + TypeScript + Tailwind CSS v3.

## Routing

Each screen owns its own route (`react-router-dom`) - no manually-tracked
"active tab" state anywhere.

- `App.tsx` — declares every route. Adding a screen = one `<Route>` here.
- `components/layout/AppLayout.tsx` — the layout route: renders `Sidebar` +
  `TopBar` once, and `<Outlet/>` for whichever page matched.
- `components/layout/Sidebar.tsx` — nav links use `NavLink`, so "active" is
  derived from the actual URL, never passed down as a prop.
- `pages/ComingSoonPage.tsx` — placeholder for a route that exists (so the
  sidebar link actually navigates) but has no real screen yet.

## Data fetching

Nothing in a component is a hardcoded number, except static labels. Every
number/table row comes from a `@tanstack/react-query` hook, which currently
resolves to mock data but is structured exactly like it'll look once a real
backend exists:

```
api/client.ts        thin fetch() wrapper (base URL from VITE_API_BASE_URL)
api/<resource>.ts     one function per resource (getActiveRun,
                       getRecentRuns, ...) - returns mock data or calls
                       api/client.ts depending on VITE_USE_MOCKS
api/mocks/            the actual mock payloads + a delay() helper so loading
                       states are real, not instant
hooks/use*.ts         react-query hooks - this is what components call
```

To point a screen at a real backend: set `VITE_USE_MOCKS=false` and
`VITE_API_BASE_URL` in `.env.local` (see `.env.example`) — no component code
changes, since they only ever call the hooks, never `api/mocks/` directly.

## Design system

Every screen is built from the same set of tokens and primitives - no screen
should hardcode a hex color, a button style, or table cell padding directly.

- `tailwind.config.js` — the single source of truth for colors, fonts, and
  spacing. Tokens were lifted from the approved Stitch mockup so the compiled
  app matches it exactly.
- `src/components/ui/` — base primitives (`Button`, `Badge`, `GlassPanel`,
  `Table.*`, `Icon`, `LoadingState`, `ErrorState`). Variant-driven via
  `class-variance-authority` (e.g. `<Button variant="primary" size="sm">`)
  instead of one-off className strings, so a style change happens in one
  file, not on every screen that uses it.
- `src/components/<feature>/` — screen-specific components (e.g.
  `components/dashboard/`, `components/rundetail/`) built out of the `ui/`
  primitives.
- `src/lib/cn.ts` — the `cn()` helper (clsx + tailwind-merge) every component
  uses to merge classNames safely, including our custom font tokens.

Import paths use the `@/` alias (`@/components/ui/Button`) instead of
relative `../../..` chains — configured in `vite.config.ts` and
`tsconfig.app.json`.

## Running it

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # type-checks (tsc -b) then builds to dist/
```

## Layout width is each page's own call

`AppLayout`'s `<main>` only owns padding/scroll - it does **not** constrain
content width. `HistoryPage` wraps itself in `max-w-5xl mx-auto`;
`DashboardPage`/`RunDetailPage` use the full available width for their
multi-column layouts. Pick whichever fits a new screen — don't add a width
constraint to the shared layout.

## Status

`Dashboard` (`/dashboard`), `History` (`/history`,
`src/pages/HistoryPage.tsx`), and a run's detail view (`/history/:runId`)
all have real content, fully wired through the react-query + mock-API layer
above. `Settings` is routed but shows `ComingSoonPage` until it's built.
`RecentRunsTable`'s rows (Dashboard) and `RunsTable` (History) both link to
`/history/:runId` - both actually pull from
`src/components/dashboard/RunsTable.tsx`, the shared bare table, so the
column rendering only exists once.

**No Portfolio screen, and no account summary anywhere** - it would have
shown positions/balance/equity curve, but that's exactly what Alpaca's own
paper-trading dashboard already shows; a second copy of the same numbers
wasn't worth building or maintaining. TopBar's small Balance/P&L readout
(originally kept "since it's cheap") was removed too on a second look - the
same redundancy argument applied at a smaller scale, and keeping it meant
carrying `api/portfolio.ts` / `hooks/usePortfolio.ts` / a `PortfolioSummary`
type just to show two numbers nobody critically needed while looking at
Dashboard or History. None of that exists in the codebase anymore.

**Sidebar's top slot is the collapse/expand toggle**, not a static "A" logo
- the app name is already prominent in TopBar, so a decorative logo there
was redundant; a chevron button that actually does something was a better
use of that spot (and removed the need for the separate toggle that used to
live at the bottom).

**Sidebar collapse/expand**: `AppLayout` owns the collapsed/expanded state
(`hooks/useSidebarCollapsed.ts`, persisted to localStorage) and passes it to
both `Sidebar` (width) and `TopBar` (left offset) so they can't drift out of
sync - width/margin/offset class names all come from `lib/layout.ts`, one
source instead of three hardcoded `w-16`/`ml-16`/`left-16` literals.

**TopBar buttons are real, not decorative**: the settings icon (a gear, not
a profile icon - there's no multi-user auth system) navigates to
`/settings`. The notifications bell and the old wallet/Portfolio shortcut
were both removed - a button that goes nowhere (no notification system
exists; there's no Portfolio screen to go to anymore) is exactly the kind
of non-functional stub this project's house rules forbid.

**Run Detail has no "Override veto" action, deliberately.** The mockup had
one; it was removed rather than left disabled, because the risk gate's
whole premise (`contracts/schemas.py`'s `RiskResult`, the "hard veto power
over everything" pitch in root `CLAUDE.md`) is that nothing overrides it -
a button that lets a human bypass a hard veto contradicts that story.
`components/rundetail/RunActions.tsx`'s "Modify Parameters" button stayed
(still presentational - no backend endpoint to resubmit edited parameters
yet) but only renders for a `vetoed`/`failed` run - there's nothing to
modify on an already-executed or still-running trade.

**The header search box actually navigates.** Submitting it (Enter or the
search icon) treats `run-...`-prefixed input as a run id and jumps straight
to `/history/:runId`; anything else is treated as a ticker and navigates to
`/history?symbol=TICKER`, which `HistoryPage` reads via `useSearchParams`
and filters `RunsTable`'s rows by client-side (no new endpoint needed - the
data's already fetched).

**"New Run" is a working mock flow, not a dead button**: clicking it opens
`NewRunDialog` (ticker input), which calls `useStartRun()` →
`api/dashboard.ts`'s `startRun()`. In mock mode this creates a real entry in
the mock run store and schedules its pipeline steps to progress over ~8s via
`setTimeout` (see `api/mocks/dashboard.ts`'s `scheduleProgress`) - standing
in for what a real backend + poll/websocket will do once
`workflow/pipeline.py` is exposed over HTTP. `useActiveRun`/`useRunDetail`
poll every 2s (`refetchInterval`) while a run's status is `"running"` and
stop automatically once it finishes, so Dashboard shows it actually
advancing without any manual refresh.

`/history/:runId` is nested under `/history` (not a sibling top-level
route) specifically so the Sidebar's "History" link stays highlighted while
looking at one run's detail — a small but deliberate routing choice, worth
matching for any future drill-down page.

A few components introduced along the way are meant for reuse anywhere, not
just where they first appeared: `components/ui/RadialGauge` (circular %
gauge), `components/ui/ProgressBar` (linear % bar, `tone` prop for cyan/
primary/success fills), `components/ui/StatusDot` (dot+label status
indicator), `components/ui/InfoChip` (label-over-value box) — all
data-driven (a status/tone → style map), not per-usage one-offs.

## Plain language + technical depth, on the same screen

Every screen keeps its technical/branded vocabulary ("Chaos Sandbox", "Risk
Gate", "Hard Gate") front and center — that's the hackathon's own pitch
terminology and shouldn't be hidden. What was missing was a plain-language
layer *next to* it for a non-technical viewer:

- `src/lib/glossary.ts` — one dictionary, term → one-sentence plain
  explanation. Single source so the same term reads identically everywhere.
- `components/ui/InfoTooltip.tsx` — a small `(?)` next to a technical term;
  hover/focus (so touch-via-tap and keyboard both work) reveals the
  glossary explanation. The term itself never moves or gets replaced.
  Built on `@floating-ui/react` (portal + dynamic position, not a plain
  `position: absolute` span) - several `GlassPanel`s use `overflow-hidden`
  to clip a decorative background icon, which was also clipping a
  non-portaled tooltip nested inside them. Same root cause class as the New
  Run modal's positioning bug: an ancestor's CSS constraining something
  that's supposed to float above everything.
- `components/ui/PlainSummary.tsx` — a one-sentence "here's what's
  happening" callout used at the top of Dashboard and Run Detail, driven by
  `lib/runSummary.ts`'s `buildRunPlainSummary(run)` (one status → sentence
  map, shared by both screens so the same run status always reads the same
  way).

"Conviction" was renamed to "Confidence" everywhere (Dashboard, Run Detail,
History) — an exact plain synonym, no explanation needed, so it's just the
better word, not a tooltip candidate. Pipeline stage names are also now
identical across Dashboard's horizontal stepper and Run Detail's vertical
timeline (`src/api/mocks/dashboard.ts`) — they used to differ ("Data
Ingestion" vs "Market Data" for the same step), which was its own source of
confusion independent of jargon.

**Multiple Stitch mockups, one design system:** when a new mockup's shared
chrome (Sidebar/TopBar/body background) drifts slightly from what's already
built, the already-built version wins — don't re-litigate global chrome for
every new mockup, only adopt genuinely new page-specific content. Only add a
mockup's custom CSS effect (e.g. `.step-line`, `.cyber-chip`) if it's
actually used in the markup given — several defined-but-unused classes
(`.amber-alert`, `.neon-blur`) were deliberately left out for exactly this
reason.

Next screens should follow the same pattern: a `hooks/use*` query, an
`api/*` resource module, and a page that composes `components/<feature>/`
sections — never fetch or hardcode data directly inside a component.
