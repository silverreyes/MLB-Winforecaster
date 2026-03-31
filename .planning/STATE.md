---
gsd_state_version: 1.0
milestone: v2.2
milestone_name: Game Lifecycle, Live Scores & Historical Accuracy
status: completed
stopped_at: Completed 13-03-PLAN.md
last_updated: "2026-03-31T13:02:33.061Z"
last_activity: 2026-03-31 -- Completed 13-03 frontend game visibility plan
progress:
  total_phases: 5
  completed_phases: 1
  total_plans: 3
  completed_plans: 3
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-30)

**Core value:** Produce well-calibrated win probability estimates that can be rigorously compared against Kalshi market prices, surfacing where models agree, disagree, and where edges may exist.
**Current focus:** Phase 13 - Schema Migration & Game Visibility

## Current Position

Phase: 13 of 17 (Schema Migration & Game Visibility)
Plan: 3 of 3 in current phase
Status: Phase Complete
Last activity: 2026-03-31 -- Completed 13-03 frontend game visibility plan

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 3 (v2.2)
- Average duration: 4min
- Total execution time: 12min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| Phase 13 P01 | 3min | 2 tasks | 5 files |
| Phase 13 P02 | 5min | 2 tasks | 5 files |
| Phase 13 P03 | 4min | 2 tasks | 8 files |

**Recent Trend:**
- Last 5 plans: 3min, 5min, 4min
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

- Phase 15 has 5 converging pitfalls (race condition, APScheduler collision, status zoo, API amplification, memory pressure) -- needs careful planning
- Phase 16 reconciliation must target ALL prediction rows for a game_id, not just is_latest = TRUE rows

## Session Continuity

Last session: 2026-03-31T12:56:39.846Z
Stopped at: Completed 13-03-PLAN.md
Resume file: None
