---
gsd_state_version: 1.0
milestone: v2.2
milestone_name: Game Lifecycle, Live Scores & Historical Accuracy
status: executing
stopped_at: Phase 17 approved � ready for Phase 18
last_updated: "2026-04-01T03:10:00.000Z"
last_activity: 2026-04-01 -- Phase 17 approved; all outcomes and nightly reconciliation complete
progress:
  total_phases: 7
  completed_phases: 5
  total_plans: 17
  completed_plans: 17
  percent: 97
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-30)

**Core value:** Produce well-calibrated win probability estimates that can be rigorously compared against Kalshi market prices, surfacing where models agree, disagree, and where edges may exist.
**Current focus:** Phase 17 - Final Outcomes and Nightly Reconciliation

## Current Position

Phase: 18 of 18 (History Route)
Plan: 0 of 2 in phase 18 -- not started
Status: Phase 17 approved; ready to begin Phase 18
Last activity: 2026-04-01 -- Phase 17 approved by user

Progress: [█████████░] 94% (milestone v2.2: 16 of 17 plans)

## Performance Metrics

**Velocity:**
- Total plans completed: 16 (v2.2)
- Average duration: 4min
- Total execution time: ~68min

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
| Phase 16 P02 | 2min | 2 tasks | 2 files |
| Phase 16 P03 | 6min | 2 tasks | 5 files |
| Phase 17 P01 | 5min | 2 tasks | 3 files |
| Phase 17 P02 | 4min | 2 tasks | 6 files |

**Recent Trend:**
- Last 5 plans: 5min, 2min, 6min, 5min, 4min
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
- FeatureBuilder pool=None default preserves backward compat for notebooks/backtest; pool!=None uses game_logs DB path (Phase 16)
- Pool wiring chain: runner.py -> LiveFeatureBuilder(pool=pool) -> FeatureBuilder(pool=pool) (Phase 16)
- _load_from_game_logs adds computed columns (status='Final', is_shortened_season, season_games) post-query to match fetch_schedule output exactly (Phase 16)
- reconcile_outcomes delegates to write_game_outcome per single-source-of-truth guarantee; nightly job at 6 AM ET with 1-hour misfire grace (Phase 17)
- Top-level actual_winner and prediction_correct on GameResponse sourced from primary prediction (post_lineup or pre_lineup) for frontend convenience (Phase 17)
- game_id::INTEGER cast in _fetch_final_scores SQL for VARCHAR game_logs to INTEGER predictions join (Phase 17)

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

Last session: 2026-04-01T02:50:00Z
Stopped at: Completed 17-02-PLAN.md
Resume file: None
