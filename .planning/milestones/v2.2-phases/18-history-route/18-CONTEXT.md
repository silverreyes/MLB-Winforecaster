# Phase 18: History Route - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning

<domain>
## Phase Boundary

A `/history` page accessible from the main dashboard where users can review past predictions vs actual outcomes over a selected date range, with rolling model accuracy percentages per model. Implements HIST-01 through HIST-04.

No Recharts charts — those are deferred to v2.3+ (HIST-05/06). Accuracy display is a summary row and table column, not a trend chart.

</domain>

<decisions>
## Implementation Decisions

### Routing
- **Hash-based routing** (`#/history`) — no React Router dependency added. Parse `window.location.hash` in `App.tsx` to determine which page to render.
- The existing `App.tsx` content becomes the `#/` (main) view; the history page renders when hash is `#/history`.
- The Header component stays visible on both pages (shared across views).
- Header title/logo becomes a home link: clicking it sets `window.location.hash = '#/'` from any page.
- History page has a `← Back to Today` link in its page header row that sets hash back to `#/`.

### Table structure
- **One row per game** — each completed game is one row.
- **Columns (left to right):** Date | Matchup (Away @ Home) | Score | LR% | RF% | XGB% | ✓/✕
- Probabilities shown are **post-lineup** predictions when available; fallback to pre-lineup when no post-lineup exists. The `%` shown is the model's probability for the home team winning.
- **Only games with recorded outcomes** are shown — `prediction_correct IS NOT NULL`. Games without outcomes (unresolved, no reconciliation yet) are excluded.
- **✓/✕ correctness column**: check mark in amber for correct, ✕ in muted color for incorrect. Consistent with Phase 17 GameCard outcome markers.

### Model accuracy summary
- A **summary row pinned above the table** showing accuracy per model: `LR: 57.3% correct | RF: 59.1% correct | XGB: 61.2% correct` (computed from games in current date range).
- Updates dynamically as date range changes.
- These are **live pipeline accuracy percentages** (games correctly predicted / total completed games), NOT backtest Brier scores.

### Default date range & date controls
- Default range on open: **last 14 days** (today − 14 days through yesterday, inclusive).
- Controls: **two native `<input type="date">` fields** — Start Date and End Date. Consistent with DateNavigator's native input pattern (Phase 14). No library needed.
- Range is clamped so end date cannot be in the future (history is for completed games).

### Empty state
- When the selected range has no completed games with recorded outcomes: show a simple empty state message — "No completed games in this range" — consistent with the main page's EmptyState component pattern.

### History page layout (top to bottom)
1. `<Header>` component (shared, unchanged — clock, title, badges)
2. Page header row: "Prediction History" title + "← Back to Today" link on the right
3. Accuracy summary strip: `LR: X% | RF: X% | XGB: X%` for the current date range
4. Date range picker row: Start date input — End date input
5. Predictions vs actuals table (or empty state if no results)

### Navigation entry point
- A **"View History →" link** added to the right side of the existing `AccuracyStrip` component. Contextually appropriate — users viewing accuracy stats are the natural audience for the history page.
- The history page **replaces** the DateNavigator and AccuracyStrip from the main layout — they do not appear on the history page (clean page swap).

### Backend API
- New `GET /api/v1/history?start=YYYY-MM-DD&end=YYYY-MM-DD` endpoint.
- Returns: list of completed prediction rows with outcome data + per-model accuracy summary.
- Only returns rows where `prediction_correct IS NOT NULL`.
- Uses post-lineup prediction (falling back to pre-lineup) as the canonical row per game.

### Claude's Discretion
- Exact CSS layout and spacing for the history page within the dark/amber design system
- How the hash change listener is implemented (hashchange event vs useEffect on window)
- SQL query design for the history endpoint (join strategy, ordering)
- TanStack Query key and caching strategy for history data
- Mobile/responsive behavior of the table (horizontal scroll vs column truncation)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §HIST-01 through HIST-04 — the four requirements this phase implements
- `.planning/REQUIREMENTS.md` §Future Requirements — HIST-05/06 deferred to v2.3+ (Recharts charts); do NOT implement in Phase 18

### Carry-forward decisions (locked)
- `.planning/STATE.md` §Carry-Forward Decisions — includes: "prediction_correct IS NOT NULL" targeting pattern, game_id::INTEGER cast for game_logs joins, sync def handlers in FastAPI, psycopg3 connection pool patterns

### Existing frontend
- `frontend/src/App.tsx` — current SPA entry point; hash routing added here
- `frontend/src/components/AccuracyStrip.tsx` — "View History →" link added here
- `frontend/src/components/Header.tsx` — home link added to title
- `frontend/src/api/types.ts` — add HistoryRow and HistoryResponse TypeScript types
- `frontend/src/index.css` — CSS custom properties (design tokens); history page must use these

### Existing backend
- `api/routes/games.py` — pattern for sync def route handlers; history route follows same structure
- `api/models.py` — add HistoryRow and HistoryResponse Pydantic models here
- `src/pipeline/db.py` — DB pool access pattern; history query added here
- `api/main.py` — history router registered here

### Phase 17 output (data source)
- `api/routes/games.py` — `actual_winner`, `prediction_correct`, `home_final_score`, `away_final_score` on GameResponse (source of truth for what's in the DB)
- Phase 17 produced the outcome columns; Phase 18 reads them for history display

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AccuracyStrip.tsx` — already rendered on main page; gets a "View History →" link added to its right side
- `EmptyState.tsx` + `EmptyState.module.css` — existing empty state component; reuse pattern for history empty state
- `useGames.ts` TanStack Query pattern — history uses same `useQuery` pattern with `fetchJson<HistoryResponse>('/history?start=...&end=...')`
- `frontend/src/api/client.ts` `fetchJson<T>()` — generic fetch wrapper; use for history API call

### Established Patterns
- Native `<input type="date">` for date controls — already in DateNavigator (Phase 14); consistent approach
- CSS custom properties (`--color-accent`, `--color-bg-card`, `--color-border`, `--color-text-muted`, etc.) — all table styling must use these tokens
- `window.location.hash` — no react-router-dom; App.tsx reads hash to switch views
- Sync `def` route handlers (not async) — FastAPI pattern established across all routes
- `actual_winner IS NOT NULL` / `prediction_correct IS NOT NULL` filter pattern — established in reconcile_outcomes (Phase 17)

### Integration Points
- `App.tsx` — hash listener + conditional render of `<HistoryPage>` vs main layout
- `AccuracyStrip.tsx` — right-side "View History →" anchor tag pointing to `#/history`
- `Header.tsx` — title becomes `<a href="#/">` for home navigation
- `api/main.py` — `app.include_router(history.router, prefix="/api/v1")`
- `src/pipeline/db.py` — new `get_history(pool, start_date, end_date)` function returning list of rows

</code_context>

<specifics>
## Specific Requirements

- History accuracy percentages are **live pipeline stats** (correct predictions / total completed games in range), not backtest Brier scores. The existing AccuracyStrip's hardcoded Brier scores remain on the main page; the history page shows live accuracy from actual pipeline predictions.
- The accuracy summary row appears even for small samples (1 game). No minimum sample size threshold.
- **Accuracy denominator is `prediction_correct IS NOT NULL` rows only.** If a 14-day range has 14 games but only 8 have outcomes recorded, accuracy is calculated over those 8 — never over the full 14 with NULLs dragging the percentage down. The backend query filters `WHERE prediction_correct IS NOT NULL` before computing counts, and this same filter defines both the table rows AND the accuracy numerator/denominator.
- LR%/RF%/XGB% columns show the model's probability the **home team wins** (consistent with existing PredictionResponse fields `lr_prob`, `rf_prob`, `xgb_prob`).
- `prediction_correct` for history uses the same logic established in Phase 17: true when ensemble_prob > 0.5 AND home team won, OR ensemble_prob < 0.5 AND away team won.

</specifics>

<deferred>
## Deferred Ideas

- **Header "Last updated" timestamp regression** — User noted the last-updated time/date in the header top-right disappeared during v2.2 development. Needs investigation and fix — separate bug fix task, not part of Phase 18.
- **HIST-05: Rolling accuracy trend chart** — Recharts line chart of accuracy over time. Deferred to v2.3+; needs 50+ games to be meaningful. Explicitly out of scope for Phase 18 (see REQUIREMENTS.md Future Requirements).
- **HIST-06: Per-model Brier score trend chart** — Also deferred to v2.3+.

</deferred>

---

*Phase: 18-history-route*
*Context gathered: 2026-03-31*
