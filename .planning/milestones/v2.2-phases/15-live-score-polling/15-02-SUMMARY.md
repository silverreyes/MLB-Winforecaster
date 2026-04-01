---
phase: 15-live-score-polling
plan: 02
subsystem: api, pipeline
tags: [fastapi, apscheduler, live-score, reconciliation, postgres]

# Dependency graph
requires:
  - phase: 15-01
    provides: "LiveScoreData model, get_linescore_cached, parse_linescore, test stubs"
provides:
  - "Linescore enrichment in /games/{date} for LIVE games"
  - "write_game_outcome for reconciliation writes to all prediction rows"
  - "live_poller_job with 90s IntervalTrigger and max_instances=1"
  - "8 fully implemented live poller tests"
affects: [16-final-card-rendering, 17-history-route]

# Tech tracking
tech-stack:
  added: [IntervalTrigger]
  patterns: [live-score-enrichment-in-route, outcome-reconciliation-via-poller]

key-files:
  created: []
  modified:
    - api/routes/games.py
    - src/pipeline/db.py
    - src/pipeline/scheduler.py
    - tests/test_pipeline/test_live_poller.py

key-decisions:
  - "build_games_response gets view_mode param with default='historical' for backward compat"
  - "live_poller_job uses statsapi.get() directly for linescore (not the cached function from mlb_schedule)"
  - "Scheduler shutdown() removed from test since scheduler was never started"

patterns-established:
  - "Route-level linescore enrichment: fetch + parse only for LIVE games in live view_mode"
  - "Reconciliation write targets ALL game_id rows (not just is_latest=TRUE)"

requirements-completed: [LIVE-01, LIVE-08]

# Metrics
duration: 4min
completed: 2026-03-31
---

# Phase 15 Plan 02: Live Score Polling Summary

**Wired live score data into /games/{date} route for LIVE games and built live_poller_job with 90s IntervalTrigger that writes game outcomes on Final transition**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-31T22:20:11Z
- **Completed:** 2026-03-31T22:24:40Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- /games/{date} enriches LIVE games with live_score data via get_linescore_cached + parse_linescore (graceful degradation on parse failure)
- write_game_outcome writes actual_winner and prediction_correct to ALL prediction rows for a game_id (not just is_latest=TRUE)
- live_poller_job registered with 90s IntervalTrigger, max_instances=1, exits early when no live/final games
- All 8 test stubs replaced with real implementations, all passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Games route enrichment + write_game_outcome + live_poller_job** - `fbb76c0` (feat)
2. **Task 2: Replace test stubs with full live poller tests** - `b32b6c0` (test)

## Files Created/Modified
- `api/routes/games.py` - Added LiveScoreData/linescore imports, view_mode param to build_games_response, LIVE game enrichment
- `src/pipeline/db.py` - Added write_game_outcome function for reconciliation writes
- `src/pipeline/scheduler.py` - Added live_poller_job function and registered with IntervalTrigger(seconds=90)
- `tests/test_pipeline/test_live_poller.py` - Replaced 8 stub tests with full implementations

## Decisions Made
- build_games_response view_mode parameter defaults to 'historical' to maintain backward compatibility with all 6 existing test call sites
- live_poller_job fetches linescore data via direct statsapi.get() call (not the cached linescore function) since the poller needs only runs data, not the full linescore fields
- Removed scheduler.shutdown() from test_poller_max_instances_config since APScheduler 3.x raises SchedulerNotRunningError on shutdown of a never-started scheduler

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed scheduler.shutdown() from test**
- **Found during:** Task 2 (test implementation)
- **Issue:** Plan's test code called scheduler.shutdown(wait=False) but the scheduler was never started, causing SchedulerNotRunningError
- **Fix:** Removed the shutdown call since the scheduler was only created (not started) for configuration inspection
- **Files modified:** tests/test_pipeline/test_live_poller.py
- **Verification:** All 8 tests pass
- **Committed in:** b32b6c0

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor test code fix. No scope creep.

## Issues Encountered
- Pre-existing test failure in tests/test_feature_builder.py::test_rolling_ops (unrelated to Phase 15). Logged to deferred-items.md.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Live score enrichment and outcome writes are complete
- Phase 15 Plans 03 (frontend live score display) and 04 (frontend expanded view) can proceed
- Phase 16 (final card rendering) can build on write_game_outcome for nightly reconciliation

---
*Phase: 15-live-score-polling*
*Completed: 2026-03-31*
