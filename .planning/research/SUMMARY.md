# Project Research Summary

**Project:** MLB Win Forecaster — v2.2 Game Lifecycle, Live Scores & Historical Accuracy
**Domain:** Sports prediction dashboard — game lifecycle completion and historical accuracy tracking
**Researched:** 2026-03-30
**Confidence:** HIGH

## Executive Summary

This milestone adds game lifecycle awareness, live score display, date navigation, and a historical accuracy page to an existing MLB pre-game win probability dashboard. The existing stack (React 19, Vite 8, TanStack Query 5, FastAPI, psycopg3, APScheduler, MLB-StatsAPI 1.9.0) handles all new requirements with minimal additions: only `react-router` is added to the frontend bundle, and zero new Python packages are needed. The backend adds two new API routes, one new scheduler job, and three nullable columns to the predictions table. This is an evolution of an existing system, not a greenfield build.

The recommended approach follows clear dependency ordering: schema migration first (enables all downstream writes), then game visibility and date navigation (foundational UX), then live score polling (most complex), then nightly reconciliation (safety net), and finally the history page (requires accumulated data to be meaningful). Every major architectural decision has a documented anti-pattern to avoid — most critically: do not store mutable game state in the predictions table, do not add WebSocket infrastructure, and do not run model predictions for non-today dates.

The most critical risk is data correctness, not technical complexity. Three specific pitfalls can corrupt historical accuracy data silently: doubleheader prediction collision (the unique constraint is missing `game_id`), UTC/ET date boundary mismatch (affects late West Coast games), and pipeline UPSERT overwriting reconciliation writes (race condition when confirmation run fires after a game goes Final). All three have clear, tested mitigations. Implementing them correctly in the schema migration and reconciliation phases is the difference between a trustworthy accuracy record and a dashboard users stop believing.

## Key Findings

### Recommended Stack

The existing stack requires only one new dependency: `react-router@^7.13.2` for the `/history` client-side route. React Router 7 is the current stable release with confirmed React 19 support, adds ~14kB gzipped, and integrates with the existing `SPAStaticFiles` SPA fallback middleware without any backend routing changes. Every other frontend need is met with native browser APIs: `<input type="date">` for date navigation, inline SVG for the bases diamond component, and `Intl.DateTimeFormat` (already in use) for date formatting. No charting library is added in v2.2 — the history page launches with a styled HTML table; Recharts is deferred until 50+ games accumulate.

On the backend, all new capabilities (live schedule hydration, APScheduler cron jobs, psycopg3 column writes) are already available. New work is code, not dependencies. One critical API detail: `statsapi.schedule()` strips linescore data during its internal parsing; the new live score proxy must use `statsapi.get('schedule', params)` to preserve the full hydrated response.

**Core technologies:**
- `react-router@^7.13.2`: client-side routing for `/history` page — only new package; declarative mode; ~14kB gzipped
- `MLB-StatsAPI==1.9.0` (existing): live score data via `statsapi.get('schedule', {'hydrate': 'linescore,team'})` — raw call required, not `statsapi.schedule()`
- `APScheduler 3.x` (existing): fourth `CronTrigger` job at 2am ET (plus optional 4am ET) for nightly outcome reconciliation
- `psycopg3` (existing): writes `actual_winner`, `prediction_correct`, `reconciled_at` to predictions table
- Inline SVG (no library): `<BasesDiamond>` component — four shapes, conditional amber fill, ~30 lines TSX
- Native `<input type="date">` (no library): date picker for `DateNavigator` and `DateRangePicker` — saves ~22kB vs react-day-picker

### Expected Features

Features are organized around four user needs: seeing all games regardless of status, understanding what is happening in live games, verifying predictions against actual outcomes, and reviewing historical accuracy.

**Must have (table stakes):**
- All-day game visibility — games currently vanish once In Progress or Final; this is a usability bug, not a feature gap
- Game status badges (Pre-Game / Live / FINAL) — users cannot orient themselves without this
- Live score + inning on in-progress cards — every sports dashboard shows this; absent means users leave for ESPN
- Final score on completed cards — required to confirm prediction outcome
- Prediction outcome marker (checkmark/X) — the core value proposition of a prediction tool
- Date navigation (today + past) — users return next day expecting yesterday's results

**Should have (differentiators):**
- Bases diamond on live cards — instantly recognizable to baseball fans; ~30 lines TSX, no library required
- Expanded live card (pitcher/batter/count/outs) — power user feature, collapsed by default using existing `<details>/<summary>` pattern
- Prediction vs. actual overlay on final cards — "Model said 62% home win; home won" — more informative than bare checkmark
- Nightly reconciliation job — safety net ensuring no Final games are missed
- Tomorrow schedule-only mode — show matchups without predictions when no pipeline data exists
- Future-date schedule-only view — "Predictions available on game day" placeholder

**Defer to v2.3+:**
- Rolling accuracy chart (Recharts) — needs 50+ games to be meaningful; table launches first
- Model-specific Brier score trend chart — same data volume requirement
- Edge signal performance tracking — lower priority than core accuracy display
- Tomorrow's preliminary predictions — stale SP data makes this misleading; schedule-only is the correct default

**Explicit anti-features (do not build):**
- In-game win probability updates — different problem, different models, out of scope per PROJECT.md
- WebSocket real-time push — 90s polling is sufficient at this scale; WebSocket adds infrastructure complexity for marginal UX gain
- Historical backfill of predictions — only show predictions actually generated by the live pipeline; backtested results displayed as live predictions is dishonest
- Team logos — licensing, asset management, visual clutter; abbreviations are sufficient

### Architecture Approach

The architecture extends the existing system cleanly with two new API routes and one new scheduler job. A new `api/routes/live.py` handles live score proxying with a 30-second in-memory cache (prevents MLB API amplification from concurrent clients), a new `api/routes/history.py` handles date-range accuracy queries against Postgres, and a new `src/pipeline/reconciler.py` runs as a fourth APScheduler job. The predictions table gets three additive columns applied via idempotent `DO $$ BEGIN ALTER TABLE...EXCEPTION WHEN duplicate_column THEN NULL; END $$` blocks. The key architectural constraint is the write-once semantics of the predictions table: live game state is served from the separate `/games/live` endpoint and never stored in predictions rows; only final outcomes are written once per game.

**Major components:**
1. `api/routes/live.py` (NEW) — proxies MLB Stats API with 30s server-side dict cache; detects Final games and writes outcomes to Postgres; serves `GET /api/v1/games/live?date=YYYY-MM-DD`
2. `api/routes/history.py` (NEW) — aggregation queries (accuracy %, Brier score, per-model breakdown) over date ranges; serves `GET /api/v1/history?start_date=X&end_date=Y`
3. `src/pipeline/reconciler.py` (NEW) — nightly safety net job at 2am ET; writes outcomes for Final games the live poller missed; idempotent via `WHERE actual_winner IS NULL`
4. `frontend/src/components/DateNavigator.tsx` (NEW) — left/right arrows, date display, "Today" button; date is `selectedDate` state in `App.tsx`, not a URL route
5. `frontend/src/components/LiveScoreOverlay.tsx` (NEW) — renders score, inning, bases diamond on in-progress game cards
6. `frontend/src/components/HistoryPage.tsx` (NEW) — date range picker, accuracy summary card, prediction records table; accessed via `/history` route
7. `GameCard.tsx` (MODIFIED) — card state machine: PRE_GAME / IN_PROGRESS / FINAL / POSTPONED, each with distinct hero display and polling behavior

### Critical Pitfalls

All 11 pitfalls identified are grounded in direct codebase analysis. The five requiring design decisions before writing code:

1. **Doubleheader collision on unique constraint** — the predictions table unique key `(game_date, home_team, away_team, prediction_version, is_latest)` is missing `game_id`; add `game_id INTEGER` and include it in the constraint; must be the very first schema change; downstream features (reconciliation, history) depend on uniquely identifying a prediction per game
2. **UTC/ET date boundary mismatch** — `CURRENT_DATE` in Postgres and `date.today()` in Python return UTC; after ~8pm ET, "today" rolls to tomorrow, breaking late West Coast game display; fix by computing ET date via `datetime.now(ZoneInfo("US/Eastern"))` server-side and using MLB `officialDate` for storage
3. **Pipeline UPSERT overwrites reconciliation writes** — the confirmation run at 5pm ET can overwrite `actual_winner` written by the live poller if reconciliation columns are included in `_PREDICTION_UPDATE_COLS`; explicitly exclude all three reconciliation columns from UPSERT updates; use a separate `reconcile_prediction()` function with `WHERE actual_winner IS NULL` guard
4. **MLB Stats API has 127 game statuses** — string-matching on `"Final"` misses rain-shortened, forfeited, and completed-early games; use `abstractGameState == "Final"` (three abstract states only: Preview/Live/Final); never write `actual_winner` for suspended or postponed games
5. **APScheduler max_instances collision** — APScheduler counts running instances per callable; live poller and pipeline jobs must use completely distinct callables or the poller is silently skipped during pipeline windows; set `misfire_grace_time=90` on the poller

## Implications for Roadmap

Based on research, the feature dependency graph mandates this ordering. Each phase builds the foundation the next requires.

### Phase 1: Schema Migration + Game Visibility Fix
**Rationale:** Every downstream feature writes to or reads from the three new columns, and requires `game_id` in the unique constraint. The game visibility fix is the simplest user-facing change and validates the schedule enrichment pattern. Must come first.
**Delivers:** Three new Postgres columns (`actual_winner`, `prediction_correct`, `reconciled_at`) with idempotent migration; `game_id` added to predictions table and unique constraint; `game_status` field added to `PredictionResponse`; status badges (Pre-Game / Live / FINAL) render on existing game cards.
**Addresses:** All-day game visibility (table stakes), game status indicator (table stakes)
**Avoids:** Doubleheader collision (Pitfall 1), Frontend doubleheader grouping (Pitfall 10)
**Research flag:** Standard patterns — schema migration is well-documented; idempotent `ALTER TABLE` approach verified in ARCHITECTURE.md

### Phase 2: Date Navigation
**Rationale:** Establishes the `selectedDate` state and date-parameterized data flow that live polling, reconciliation display, and history all depend on. Pure frontend change (backend `/predictions/{date}` endpoint already exists). Resolves the UTC/ET boundary issue before it can affect any polling feature.
**Delivers:** `DateNavigator` component (arrows + date display + Today button); `usePredictions` hook parameterized by date; schedule-only display for future dates with "Predictions available on game day" placeholder; correct ET date computation replacing `CURRENT_DATE`
**Addresses:** Date navigation (table stakes), Tomorrow schedule-only mode (should-have), Future-date schedule-only (should-have)
**Avoids:** UTC/ET boundary mismatch (Pitfall 3), Tomorrow stale SP predictions (Pitfall 7)
**Research flag:** Standard patterns — date state management, TanStack Query key parameterization, native date input

### Phase 3: Live Score Polling
**Rationale:** Most complex new feature. Requires schema (Phase 1) to have a target for outcome writes, and date parameterization (Phase 2) for UI integration. The live poller is the primary mechanism for outcome recording; reconciliation (Phase 4) is its safety net.
**Delivers:** `GET /api/v1/games/live?date=YYYY-MM-DD` backend endpoint with 30s server-side cache; `useLiveGames` hook polling at 90s only when date is today and games are Live; `LiveScoreOverlay` component on in-progress cards; auto-write of Final outcomes to Postgres; `BasesDiamond` SVG component; expanded live card section (pitcher/batter/count)
**Addresses:** Live score on in-progress cards (table stakes), Final score on completed cards (table stakes), Bases diamond (differentiator), Expanded live card (differentiator)
**Avoids:** Live poller/pipeline race condition (Pitfall 4), APScheduler collision (Pitfall 5), Status zoo problem (Pitfall 6), API amplification (Pitfall 11), Worker memory pressure (Pitfall 9)
**Research flag:** Needs attention — five pitfalls converge here; APScheduler callable isolation and `abstractGameState` usage must be explicitly called out in the implementation plan

### Phase 4: Nightly Reconciliation
**Rationale:** Safety net for games the live poller missed. Backend-only change. Requires schema (Phase 1) and the outcome-writing pattern from Phase 3.
**Delivers:** `reconcile_outcomes()` function in `db.py`; `run_reconciliation()` as fourth CronTrigger job at 2am ET (plus 4am ET for West Coast coverage); partial index on unreconciled rows; prediction outcome marker (checkmark/X) displayed on final cards
**Addresses:** Prediction outcome marker (table stakes), Nightly reconciliation (differentiator)
**Avoids:** Late West Coast game missing reconciliation (Pitfall 8), Status filter cascade hiding reconciliation outcomes (Pitfall 2)
**Research flag:** Standard patterns — APScheduler job addition is additive; idempotency pattern well-documented

### Phase 5: History Route
**Rationale:** Terminal feature requiring all other phases to be in place and data to have accumulated (~50+ games, roughly 4 full days of MLB schedule). Build the infrastructure first, let data accumulate, then build the UI.
**Delivers:** `GET /api/v1/history?start_date=X&end_date=Y` backend endpoint with per-game records, accuracy %, and Brier score; `HistoryPage` React component with date range picker, `AccuracySummaryCard`, and sortable `HistoryTable`; `NavBar` for page navigation; `react-router` installed with `createBrowserRouter` in `main.tsx`; rolling accuracy chart (Recharts) deferred to v2.3+
**Addresses:** History page with accuracy tracking (highest trust-building differentiator per FEATURES.md)
**Avoids:** Accuracy denominator including postponed/suspended games, infinite scroll anti-pattern, full-season unindexed SELECT
**Research flag:** Standard patterns for most of it; confirm Brier score SQL computation against actual prediction column layout before implementing

### Phase Ordering Rationale

- Schema first because the unique constraint fix (Pitfall 1) must precede any reconciliation writes; retrofitting it after Phase 3 would require data repair on existing rows
- Date navigation before live polling because `selectedDate` state is the foundation the live polling UI integration builds on; also resolves UTC/ET before it causes live polling bugs
- Live polling before reconciliation because the poller is the primary outcome recording mechanism; the reconciler fills gaps but should not be the primary path
- History last because it has no value until Phases 1-4 have generated reconciled data

### Research Flags

Phases needing attention during planning:

- **Phase 3 (Live Score Polling):** Five pitfalls converge here (race condition, APScheduler collision, 127-status zoo, API amplification, memory pressure). The implementation plan should explicitly document how each is addressed: separate callable from `run_pipeline`; `abstractGameState` not `detailedState`; 30s server-side cache; no `LiveFeatureBuilder` import in poller.
- **Phase 4 (Nightly Reconciliation):** The reconciliation write must target ALL prediction rows for a `game_id`, not just `is_latest = TRUE` rows (Pitfall 2). Plan must call this out explicitly to prevent `mark_not_latest()` calls from hiding reconciled outcomes.

Phases with standard patterns (research-phase can be skipped):

- **Phase 1 (Schema Migration):** Idempotent `ALTER TABLE` via `DO $$ BEGIN...EXCEPTION` blocks is a well-established Postgres pattern. Game visibility fix is enriching an existing API response.
- **Phase 2 (Date Navigation):** TanStack Query key parameterization, React state lifting, native date input — all established patterns with no novel integrations.
- **Phase 5 (History Route):** React Router declarative setup, TanStack Query fetching, HTML table with date range filter — standard patterns. SQL aggregation queries are specified in full in ARCHITECTURE.md.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | React Router 7.13.2 verified on reactrouter.com; MLB Stats API response verified via live call 2026-03-30; all other decisions use existing validated dependencies |
| Features | HIGH | Feature set derived from direct competitor analysis (ESPN, MLB.com, FanGraphs) plus live API verification of data availability; bases data confirmed in live game 2026-03-30 |
| Architecture | HIGH | Research performed against actual source files; all integration points traced to real code; SQL queries written against verified schema |
| Pitfalls | HIGH | 11 of 11 pitfalls derived from direct codebase analysis or verified API behavior; doubleheader constraint verified in schema.sql; UTC issue verified in docker-compose.yml |

**Overall confidence:** HIGH

### Gaps to Address

- **MLB Stats API rate limit behavior:** The rate limit is undocumented. The 30s server-side cache and 90s polling interval are conservative. Monitor for 429 responses after Phase 3 ships; add 200ms inter-request delay as a precaution.
- **Recharts timing decision:** The history endpoint design returns per-game records in the shape Recharts needs. Roadmap should flag Phase 5 as "table only at launch; chart added when game count exceeds 50."
- **Reconciliation run time for Phase 4:** PITFALLS.md recommends single run at 3am ET or double run at 1am + 4am ET. The roadmap plan should make an explicit choice and document it rather than leaving it to the implementer.
- **`statsapi.get()` vs `statsapi.schedule()` distinction:** Must be explicitly called out in the Phase 3 implementation plan. Using `statsapi.schedule()` for the live score proxy silently returns empty linescore data.

## Sources

### Primary (HIGH confidence)
- [MLB Stats API schedule endpoint](https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=03/30/2026&hydrate=linescore,team) — live response verified 2026-03-30; linescore structure confirmed including `offense.first/second/third` for bases
- [MLB Stats API game status endpoint](https://statsapi.mlb.com/api/v1/gameStatus) — 127 status codes verified; `abstractGameState` three-value taxonomy confirmed
- [React Router v7 home](https://reactrouter.com/home) — v7.13.2 current stable, React 19 support confirmed
- [React Router declarative installation](https://reactrouter.com/start/declarative/installation) — setup guide confirmed
- [MLB-StatsAPI wiki: schedule function](https://github.com/toddrob99/MLB-StatsAPI/wiki/Function:-schedule) — `statsapi.schedule()` vs `statsapi.get()` distinction documented
- [APScheduler 3.x User Guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html) — BlockingScheduler, CronTrigger, max_instances behavior
- Direct codebase analysis: `src/pipeline/schema.sql`, `src/pipeline/db.py`, `src/pipeline/scheduler.py`, `api/routes/predictions.py`, `frontend/src/hooks/usePredictions.ts`, `docker-compose.yml`, `Dockerfile`

### Secondary (MEDIUM confidence)
- [ESPN MLB Scoreboard](https://www.espn.com/mlb/scoreboard) — date navigation, live card layout reference
- [FanGraphs Live Scoreboard](https://library.fangraphs.com/features/live-scoreboard/) — expanded card tabs, game odds display patterns
- [MLB.com Scores](https://www.mlb.com/scores) — standard scoreboard layout reference
- [GUMBO Documentation](https://bdata-research-blog-prod.s3.amazonaws.com/uploads/2019/03/GUMBOPDF3-29.pdf) — MLB live data feed spec (2019 doc; structure verified via live API calls instead)
- [APScheduler Issue #423](https://github.com/agronholm/apscheduler/issues/423) — function-level max_instances counting behavior confirmed
- [react-day-picker v9 changelog](https://daypicker.dev/changelog) — date-fns bundled dependency confirmed; used to justify native input decision

### Tertiary (LOW confidence)
- [Native date input styling](https://dev.to/codeclown/styling-a-native-date-input-into-a-custom-no-library-datepicker-2in) — cross-browser styling approach; acceptable inconsistency for a single-user dashboard

---
*Research completed: 2026-03-30*
*Ready for roadmap: yes*
