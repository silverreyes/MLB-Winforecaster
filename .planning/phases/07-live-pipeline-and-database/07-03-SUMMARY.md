---
phase: 07-live-pipeline-and-database
plan: 03
subsystem: pipeline
tags: [apscheduler, cron, pipeline-runner, health-check, edge-signal, kalshi]

# Dependency graph
requires:
  - phase: 07-01
    provides: DB access layer (insert_prediction, mark_not_latest, pipeline_runs CRUD)
  - phase: 07-02
    provides: LiveFeatureBuilder, predict_game, fetch_kalshi_live_prices
provides:
  - Pipeline runner with three-version dispatch (pre_lineup/post_lineup/confirmation)
  - APScheduler cron configuration at 10am/1pm/5pm ET
  - Health data aggregation for API health endpoint
  - Entry point script with --once and scheduler modes
  - Edge signal computation (BUY_YES/BUY_NO/NO_EDGE)
affects: [08-api-and-dashboard, 09-infrastructure-and-portfolio]

# Tech tracking
tech-stack:
  added: [apscheduler-3.x, zoneinfo]
  patterns: [three-run-dispatch, edge-threshold-signal, sp-change-detection]

key-files:
  created:
    - src/pipeline/runner.py
    - src/pipeline/scheduler.py
    - src/pipeline/health.py
    - scripts/run_pipeline.py
    - tests/test_pipeline/test_runner.py
    - tests/test_pipeline/test_health.py

key-decisions:
  - "Edge threshold set at 0.05 (5pp) for BUY_YES/BUY_NO signals"
  - "TBD starters skip post_lineup entirely (PIPE-07); no fallback insertion"
  - "Confirmation run marks old post_lineup rows is_latest=FALSE on SP change"
  - "APScheduler BlockingScheduler with 5-minute misfire_grace_time per job"

patterns-established:
  - "Three-version dispatch: pre_lineup(team_only) -> post_lineup(sp_enhanced) -> confirmation(re-run + diff)"
  - "Edge signal computation: avg model prob vs Kalshi price with threshold guard"
  - "Pipeline run logging: insert_pipeline_run at start, update_pipeline_run at end"

requirements-completed: [PIPE-02, PIPE-03, PIPE-04, PIPE-05, PIPE-06, PIPE-07, PIPE-08]

# Metrics
duration: 4min
completed: 2026-03-30
---

# Phase 07 Plan 03: Pipeline Runner Summary

**Three-run pipeline orchestrator (10am/1pm/5pm ET) with SP change detection, Kalshi edge signals, and APScheduler cron scheduling**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-30T03:26:53Z
- **Completed:** 2026-03-30T03:31:05Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Pipeline runner dispatches pre_lineup/post_lineup/confirmation with correct feature set selection, SP change detection, and edge signal computation
- APScheduler configured with 3 CronTrigger jobs at 10am/1pm/5pm ET with 5-minute misfire grace
- Entry point script supports both --once (single run) and scheduler (blocking) modes
- 17 tests cover edge signal logic, all three run modes, SP change detection, TBD fallback, pipeline logging, and health data

## Task Commits

Each task was committed atomically:

1. **Task 1: Create pipeline runner with three-run dispatch logic** - `b9c13c4` (feat)
2. **Task 2: Create scheduler, entry point script, and pipeline tests** - `d5728df` (feat)

## Files Created/Modified
- `src/pipeline/runner.py` - Main orchestrator: run_pipeline dispatches pre_lineup/post_lineup/confirmation, edge signal computation
- `src/pipeline/scheduler.py` - APScheduler with CronTrigger at 10am/1pm/5pm ET
- `src/pipeline/health.py` - Health data aggregation (healthy/degraded/unhealthy status)
- `scripts/run_pipeline.py` - Entry point: load artifacts, init DB, --once or scheduler mode
- `tests/test_pipeline/test_runner.py` - 12 tests for edge signals, run modes, SP change detection, logging
- `tests/test_pipeline/test_health.py` - 5 tests for health status aggregation

## Decisions Made
- Edge threshold set at 0.05 (5pp minimum divergence for BUY_YES/BUY_NO signal)
- TBD starters skip post_lineup entirely per PIPE-07 -- no fallback insertion as post_lineup
- Confirmation run marks old post_lineup rows is_latest=FALSE when SP change detected
- APScheduler BlockingScheduler chosen (3.x) with 5-minute misfire_grace_time per job

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 07 (Live Pipeline and Database) is now complete: DB layer + data adapters + pipeline runner
- All pipeline components ready for Phase 08 (API and Dashboard) integration
- Entry point script ready for Phase 09 (Infrastructure) deployment configuration
- APScheduler can be replaced with system cron if needed during infrastructure phase

## Self-Check: PASSED

All 7 files verified present. Both task commits (b9c13c4, d5728df) confirmed in git history.

---
*Phase: 07-live-pipeline-and-database*
*Completed: 2026-03-30*
