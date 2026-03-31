---
gsd_state_version: 1.0
milestone: v2.2
milestone_name: Game Lifecycle, Live Scores & Historical Accuracy
status: executing
stopped_at: Completed 15-01-PLAN.md
last_updated: "2026-03-31T22:17:17Z"
last_activity: 2026-03-31 -- Completed Plan 15-01 (LiveScoreData model, linescore cache, parse function, test scaffolds)
progress:
  total_phases: 6
  completed_phases: 2
  total_plans: 14
  completed_plans: 8
---

---
gsd_state_version: 1.0
milestone: v2.2
milestone_name: Game Lifecycle, Live Scores & Historical Accuracy
status: executing
stopped_at: Completed 14-03-PLAN.md
last_updated: "2026-03-31T18:45:00Z"
last_activity: 2026-03-31 -- Completed Phase 14 date navigation (FutureDateBanner, EmptyState, GameCard future modes, visual verification on VPS)
progress:
  total_phases: 5
  completed_phases: 2
  total_plans: 7
  completed_plans: 7
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-30)

**Core value:** Produce well-calibrated win probability estimates that can be rigorously compared against Kalshi market prices, surfacing where models agree, disagree, and where edges may exist.
**Current focus:** Phase 15 - Live Score Polling

## Current Position

Phase: 15 of 17 (Live Score Polling) — IN PROGRESS
Plan: 1 of 4 in phase 15 — complete
Status: Plan 15-01 complete, ready for 15-02
Last activity: 2026-03-31 -- Completed Plan 15-01 (LiveScoreData model, linescore cache, parse function, test scaffolds)

Progress: [██████░░░░] 57% (milestone v2.2: 8 of 14 plans)

## Performance Metrics

**Velocity:**
- Total plans completed: 8 (v2.2)
- Average duration: 4min
- Total execution time: 37min

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

**Recent Trend:**
- Last 5 plans: 3min, 5min, 3min, 10min, 4min
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

Last session: 2026-03-31T22:17:17Z
Stopped at: Completed 15-01-PLAN.md
Resume file: .planning/phases/15-live-score-polling/15-02-PLAN.md
