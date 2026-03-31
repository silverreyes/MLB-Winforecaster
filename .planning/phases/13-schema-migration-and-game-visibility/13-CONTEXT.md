# Phase 13: Schema Migration & Game Visibility - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Two parallel tracks that must ship together:
1. **Schema migration** — Additive ALTER TABLE on `predictions`: add `game_id` integer column, update unique constraint to include `game_id` (prevents doubleheader collisions), add nullable `actual_winner` / `prediction_correct` / `reconciled_at` columns. Applied via idempotent migration.
2. **Game visibility** — All scheduled games visible on the dashboard all day regardless of game state (pre-game, in-progress, final, postponed). Each game card displays a PRE-GAME / LIVE / FINAL / POSTPONED status badge.

Date navigation, live score display, and outcome reconciliation are separate phases. This phase only adds the columns and makes all games visible with a status badge.

</domain>

<decisions>
## Implementation Decisions

### Schedule-only cards (VIBL-01 fix)
- When a game is scheduled but has no prediction row (before 10am pipeline, postponed, cancelled): show a **minimal stub card** — matchup names, game time, and status badge. No probability numbers, no edge signal.
- The stub card uses the same card shell as a prediction card; probability areas are simply absent/empty, not grayed out or distinctly styled.
- **Postponed games stay visible** with a POSTPONED badge — they do not disappear from the grid. No games are hidden.

### Status badge behavior
- Status badge (PRE-GAME / LIVE / FINAL / POSTPONED) appears on every card — both stub cards and prediction cards.
- Badge is **live** — it updates on the existing 60s prediction-poll interval. No extra polling needed.
- Status source: `abstractGameState` from MLB Stats API (3 values: Preview → PRE-GAME, Live → LIVE, Final → FINAL). POSTPONED detected via `codedGameState` or `detailedState` from the same schedule response.

### New /games/today endpoint (VIBL-01/02 architecture)
- Add `GET /api/v1/games/today` — fetches today's MLB schedule, merges with `predictions` rows, returns a unified list.
- **Existing `/predictions/today` remains unchanged** — no breaking change to current consumers.
- The frontend switches to `/games/today` as the primary data source for the dashboard.
- Schedule response cached in-memory with a **60–90s TTL** to avoid hitting the MLB Stats API on every poll cycle.

### GameResponse shape
- New `GameResponse` type: `{ game_id, home_team, away_team, game_time, game_status, prediction: PredictionGroup | null }`
- `PredictionGroup` wraps the existing pre/post-lineup pair (equivalent to the current `GameGroup` type in `frontend/src/api/types.ts`).
- `prediction` is `null` for stub cards (games with no prediction row).
- `game_status` is always a string: `'PRE_GAME' | 'LIVE' | 'FINAL' | 'POSTPONED'`.

### game_id in response
- `game_id` (MLB's `gamePk`) is **always present and non-nullable** in `GameResponse`.
- Source: schedule API for stub cards; `predictions.game_id` for prediction cards (after SCHM-01 migration).
- If a game_id cannot be determined, exclude the game from the response entirely rather than returning null.
- Rationale: Phase 15 (live scores) needs `game_id` to call `statsapi.get('game', gamePk=game_id)` — non-nullable avoids null-guards throughout downstream phases.

### Schema migration strategy
- Migrations are **idempotent ALTER TABLE IF NOT EXISTS / ADD COLUMN IF NOT EXISTS** statements.
- Applied in `apply_schema()` (called at container startup via `db.py`) — same pattern as existing schema.
- SCHM-01: Add `game_id INTEGER` to predictions, drop existing `uq_prediction` constraint, add new `uq_prediction` that includes `game_id`. Existing rows get `game_id = NULL` (acceptable — historical rows predate game_id tracking).
- SCHM-02: Add nullable `actual_winner TEXT`, `prediction_correct BOOLEAN`, `reconciled_at TIMESTAMPTZ` columns.
- Reconciliation columns excluded from the pipeline UPSERT column list to prevent overwrite race condition (already noted in STATE.md).

### Claude's Discretion
- Exact visual treatment of the stub card vs prediction card (e.g., whether to dim the probability area or simply omit it)
- In-memory cache implementation detail (module-level dict + timestamp vs. functools.lru_cache)
- Exact SQL for the constraint drop-and-recreate (handle concurrent-safe approach if applicable)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §SCHM-01, SCHM-02 — exact migration column specs and idempotency requirement
- `.planning/REQUIREMENTS.md` §VIBL-01, VIBL-02 — game visibility and status badge requirements

### Current schema and DB layer
- `src/pipeline/schema.sql` — existing table definitions, ENUMs, and constraint names (especially `uq_prediction` — must be dropped and recreated for SCHM-01)
- `src/pipeline/db.py` — `apply_schema()`, `upsert_prediction()`, UPSERT column lists (reconciliation columns must be excluded)

### Current API layer
- `api/models.py` — existing Pydantic models (`PredictionResponse`, `TodayResponse`) — new `GameResponse` sits alongside these
- `api/routes/predictions.py` — existing `/predictions/today` behavior; new `/games/today` must not break this route
- `frontend/src/api/types.ts` — existing `GameGroup` type that new `GameResponse` supersedes for the dashboard

### MLB Stats API
- `src/data/mlb_schedule.py` — `fetch_today_schedule()` already returns `game_datetime` and game info; check what status fields are available (need `abstractGameState` and `codedGameState`)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `GameCard.tsx` / `GameCard.module.css` — existing card shell is the base for stub cards; probability columns can simply be absent
- `frontend/src/api/types.ts` `GameGroup` — current grouping type; `GameResponse` replaces/extends this for the new endpoint
- `src/data/mlb_schedule.py` `fetch_today_schedule()` — already fetches schedule; needs extension to return status fields

### Established Patterns
- Sync `def` handlers in FastAPI (not async) — psycopg3 sync connections, runs in thread pool; new `/games/today` route follows same pattern
- `IS NOT EXISTS` / idempotent DDL pattern — already used in `schema.sql`; migration follows same convention
- 60s polling via TanStack Query — existing `refetchInterval` in frontend hooks; badge updates ride this naturally

### Integration Points
- `apply_schema()` in `src/pipeline/db.py` — called at container startup; migration SQL added here
- `api/routes/` — new `games.py` route file added alongside `predictions.py`
- `api/main.py` — new router registered in lifespan
- Frontend `App.tsx` or hooks layer — switches from `/predictions/today` to `/games/today` as data source

</code_context>

<specifics>
## Specific Ideas

- The `/games/today` endpoint is the authoritative source for the dashboard from Phase 13 onward. Phase 15 (live scores) will extend `GameResponse` with live score fields — keeping `/predictions/today` stable avoids churn on existing integrations.
- game_id flows `schedule API → db (predictions.game_id) → /games/today response → frontend → Phase 15 statsapi call`. The whole chain is established here so Phase 15 doesn't need to add it.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 13-schema-migration-and-game-visibility*
*Context gathered: 2026-03-30*
