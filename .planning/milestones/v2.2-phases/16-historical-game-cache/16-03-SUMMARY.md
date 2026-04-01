---
phase: 16-historical-game-cache
plan: 03
subsystem: features
tags: [postgres, psycopg, feature-builder, game-logs, connection-pool, backward-compat]

# Dependency graph
requires:
  - phase: 16-historical-game-cache
    provides: game_logs table DDL (migration_002), batch_insert_game_logs(), sync_game_logs()
provides:
  - FeatureBuilder with optional pool parameter for DB-backed schedule loading
  - _load_from_game_logs method querying game_logs Postgres table
  - LiveFeatureBuilder pool passthrough to FeatureBuilder
  - runner.py pool wiring to LiveFeatureBuilder
  - Test proving DB path used and API not called when pool provided
affects: [17-final-outcomes-reconciliation, 18-rolling-model-accuracy]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "FeatureBuilder pool=None default preserves backward compat for notebooks/backtest"
    - "psycopg.rows.dict_row for DataFrame construction from game_logs query"
    - "Computed columns (status, is_shortened_season, season_games) added post-query to match fetch_schedule output"
    - "Pool passed through runner -> LiveFeatureBuilder -> FeatureBuilder constructor chain"

key-files:
  created: []
  modified:
    - src/features/feature_builder.py
    - src/pipeline/live_features.py
    - src/pipeline/runner.py
    - tests/test_pipeline/test_game_log_sync.py
    - tests/test_pipeline/test_live_features.py

key-decisions:
  - "pool=None default ensures FeatureBuilder([2025]) still works for notebooks without any pool dependency"
  - "_load_from_game_logs uses psycopg dict_row cursor for clean DataFrame construction"
  - "Computed columns (status='Final', is_shortened_season, season_games) added to DB-sourced DataFrame to match fetch_schedule output exactly"

patterns-established:
  - "Optional pool parameter pattern: pool=None means legacy Parquet/API path, pool!=None means DB path"
  - "Pool wiring chain: runner.py -> LiveFeatureBuilder(pool=pool) -> FeatureBuilder(pool=pool)"

requirements-completed: [CACHE-04]

# Metrics
duration: 6min
completed: 2026-03-31
---

# Phase 16 Plan 03: FeatureBuilder Modification Summary

**FeatureBuilder reads from game_logs Postgres table when pool provided, eliminating fetch_schedule() API call during live pipeline runs**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-01T01:00:52Z
- **Completed:** 2026-04-01T01:07:16Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- FeatureBuilder.__init__ accepts optional pool parameter (default None for backward compat)
- _load_schedule dispatches to new _load_from_game_logs when pool provided, preserving fetch_schedule() path when pool is None
- LiveFeatureBuilder and runner.py wire pool through constructor chain
- Test verifies DB path is used and fetch_schedule API is NOT called when pool provided
- All 67 pipeline tests pass with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Add pool parameter to FeatureBuilder and implement _load_from_game_logs** - `440d5be` (feat)
2. **Task 2: Wire pool through LiveFeatureBuilder and runner + implement test** - `9bbcc44` (feat)

## Files Created/Modified
- `src/features/feature_builder.py` - Added pool parameter to __init__, _load_from_game_logs method with game_logs SQL query and computed columns
- `src/pipeline/live_features.py` - LiveFeatureBuilder accepts pool parameter, passes to FeatureBuilder constructor
- `src/pipeline/runner.py` - run_pipeline passes pool to LiveFeatureBuilder(pool=pool)
- `tests/test_pipeline/test_game_log_sync.py` - Implemented test_feature_builder_reads_game_logs (removed skip decorator)
- `tests/test_pipeline/test_live_features.py` - Fixed pre-existing assertion (seasons list, pool kwarg)

## Decisions Made
- pool=None default ensures FeatureBuilder([2025]) still works for notebooks without any pool dependency
- _load_from_game_logs uses psycopg dict_row cursor for clean DataFrame construction from query results
- Computed columns (status='Final', is_shortened_season, season_games) added post-query so downstream methods receive identical DataFrame shape

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed pre-existing test assertion in test_live_features.py**
- **Found during:** Task 2 (wiring pool through LiveFeatureBuilder)
- **Issue:** test_live_feature_builder_season_and_date expected `seasons=[2025]` but LiveFeatureBuilder passes `[self.season - 1, self.season]` = `[2024, 2025]`; also missing pool=None kwarg
- **Fix:** Updated assertion to expect `seasons=[2024, 2025]` and `pool=None`
- **Files modified:** tests/test_pipeline/test_live_features.py
- **Verification:** Full pipeline test suite (67 tests) passes
- **Committed in:** 9bbcc44 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Pre-existing test assertion was already wrong (seasons list mismatch); our pool kwarg addition surfaced it. Fixed inline. No scope creep.

## Issues Encountered
- Test Postgres container (mlb-test-pg) needed restart with correct credentials (postgres:test vs mlb:mlb). Not a code issue.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 16 (Historical Game Cache) is now complete: game_logs table, seed script, sync function, and FeatureBuilder modification all in place
- Live pipeline will now read historical schedule data from game_logs DB instead of calling fetch_schedule(season) API
- Ready for Phase 17 (Final Outcomes Reconciliation)

## Self-Check: PASSED

All files verified, all commits confirmed.

---
*Phase: 16-historical-game-cache*
*Completed: 2026-03-31*
