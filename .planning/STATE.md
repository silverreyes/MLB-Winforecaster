---
gsd_state_version: 1.0
milestone: v2.2
milestone_name: Game Lifecycle, Live Scores & Historical Accuracy
status: executing
stopped_at: Completed 16-01-PLAN.md
last_updated: "2026-04-01T00:05:52.614Z"
last_activity: 2026-03-31 -- Completed Plan 16-01 (game_logs DDL, batch insert, sync functions, test scaffold)
progress:
  total_phases: 7
  completed_phases: 3
  total_plans: 17
  completed_plans: 12
  percent: 71
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-30)

**Core value:** Produce well-calibrated win probability estimates that can be rigorously compared against Kalshi market prices, surfacing where models agree, disagree, and where edges may exist.
**Current focus:** Phase 16 - Historical Game Cache

## Current Position

Phase: 16 of 18 (Historical Game Cache)
Plan: 1 of 3 in phase 16 — complete
Status: Plan 16-01 complete, ready for Plan 16-02 (seed script)
Last activity: 2026-03-31 -- Completed Plan 16-01 (game_logs DDL, batch insert, sync functions, test scaffold)

Progress: [███████░░░] 71% (milestone v2.2: 12 of 17 plans)

## Performance Metrics

**Velocity:**
- Total plans completed: 12 (v2.2)
- Average duration: 4min
- Total execution time: ~51min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| Phase 13 P01 | 3min | 2 tasks | 5 files |
| Phase 13 P02 | 5min | 2 tasks | 5 files |
| Phase 13 P03 | 4min | 2 tasks | 8 files |
| Phase 13 P04 | 3min | 2 tasks | 3 files |
| Phase 14 P01 | 5min | 1 task | 4 files |
| Phase 14 P02 | 3min | 2 tasks | 5 files |
| Phase 14 P03 | 10min | 2 tasks | 7 files |
| Phase 15 P01 | 4min | 2 tasks | 4 files |
| Phase 15 P02 | 4min | 2 tasks | 4 files |
| Phase 15 P03 | 3min | 2 tasks | 7 files |
| Phase 15 P04 | ~2min | 2 tasks | 0 files |
| Phase 16 P01 | 5min | 2 tasks | 4 files |

**Recent Trend:**
- Last 5 plans: 4min, 4min, 3min, ~2min, 5min
- Trend: stable

*Updated after each plan completion*

## Accumulated Context

### Carry-Forward Decisions

- LiveFeatureBuilder calls FeatureBuilder private methods -- accepted coupling for now
- pandas must stay at 2.2.x (not 3.0) due to pybaseball incompatibility
- Kalshi historical data only available from 2025
- Postgres schema changes must be additive only (no drops, no renames)
- Docker Compose stack must remain deployable with docker compose up
- Migration SQL executed after main schema.sql in apply_schema(), not inline (Phase 13)
- game_id added to _PREDICTION_COLS but NOT _PREDICTION_UPDATE_COLS -- immutable per prediction (Phase 13)
- Raw statsapi.get() for schedule endpoint to preserve abstractGameState/codedGameState status fields (Phase 13)
- 75s TTL cache with max 7 entries for schedule data, thread-safe via Lock (Phase 13)
- game_id-first matching priority with team-pair fallback for prediction merge in /games/{date} (Phase 13)
- Preserved existing GameGroup/TodayResponse types for backward compat with usePredictions/useLatestTimestamp (Phase 13)
- StatusBadge placed between game time and SP row in card header per UI-SPEC layout contract (Phase 13)
- Server-side view_mode via ET timezone avoids client-side date math pitfalls (Phase 14)
- Composite cache key (date:pitchers) prevents returning non-pitcher data for tomorrow requests (Phase 14)
- Pitcher fields always present in schedule dicts (None when not hydrated) for consistent dict shape (Phase 14)
- Noon-anchored date arithmetic (T12:00:00) prevents timezone off-by-one in US timezones (Phase 14)
- refetchInterval callback reads view_mode from query.state.data for dynamic polling control (Phase 14)
- Linescore cache uses same dict+Lock+TTL pattern as schedule cache, bounded to 20 entries (Phase 15)
- statsapi.get('game') fields parameter reduces ~500KB response to ~5-10KB (Phase 15)
- inningHalf 'Middle'/'End' default to 'top' for display consistency (Phase 15)
- build_games_response view_mode param defaults to 'historical' for backward compat with existing call sites (Phase 15)
- live_poller_job uses direct statsapi.get() for linescore data, not the cached linescore function (Phase 15)
- Always singular "out" (not "outs") per UI-SPEC copywriting contract (Phase 15)
- useState for expand/collapse per UI-SPEC lock, not details/summary -- LIVE-to-FINAL transition clears state via conditional render (Phase 15)
- ScoreRow conditional render gated on game_status === 'LIVE' prevents expand affordance on non-LIVE cards (Phase 15)
- Phase 15 approved with no live games at VPS review time; MLB API rejection during pipeline is a pre-existing separate issue (Phase 15)
- Phase 16 (Historical Game Cache) inserted before Final Outcomes; old Phase 16→17, old Phase 17→18; milestone now Phases 13-18 (Phase 16 decision 2026-03-31)
- game_logs table is the source of truth for rolling team features; FeatureBuilder must read from DB, never call fetch_schedule(season) at prediction time (Phase 16 intent)
- game_logs.game_id is VARCHAR; predictions.game_id is INTEGER — Phase 17 joins across these tables must cast: game_logs.game_id::INTEGER or predictions.game_id::TEXT (Phase 16 carry-forward)
- seed_game_logs.py 2026 fetch returns a partial season (only completed games) — ON CONFLICT DO NOTHING and Final filter make this safe and idempotent (Phase 16 carry-forward)
- Module-level imports for date_cls, timedelta, statsapi in db.py enable clean test patching via patch("src.pipeline.db.date_cls") (Phase 16)
- sync_game_logs overlaps by 1 day from MAX(game_date) to catch late West Coast games that weren't Final at last sync (Phase 16)

### Roadmap Decisions

- Schema migration (game_id + outcome columns) must precede all reconciliation writes
- Live poller uses `statsapi.get()` not `statsapi.schedule()` to preserve linescore data
- `abstractGameState` (3 values) not `detailedState` (127 values) for status detection
- Reconciliation columns excluded from pipeline UPSERT to prevent overwrite race condition
- Reconciliation must target ALL prediction rows for a game_id, not just is_latest = TRUE
- HIST-04 "rolling model accuracy" = computed column in the table, NOT a Recharts chart; Recharts deferred to v2.3+

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 17 reconciliation must target ALL prediction rows for a game_id, not just is_latest = TRUE rows
- MLB Stats API 502/503 failures during pipeline runs (2026-03-31) — root cause: fetch_schedule(season) re-fetches entire March–Sept season on every run; Phase 16 eliminates this

## Session Continuity

Last session: 2026-04-01T00:05:52.610Z
Stopped at: Completed 16-01-PLAN.md
Resume file: None
