---
phase: 13-schema-migration-and-game-visibility
plan: 04
subsystem: database, api, pipeline
tags: [postgres, migration, fastapi, pipeline-runner, packaging]

# Dependency graph
requires:
  - phase: 13-schema-migration-and-game-visibility (plans 01-03)
    provides: migration_001.sql, apply_schema(), insert_prediction schema with game_id
provides:
  - apply_schema() warning log when migration file missing
  - API container auto-applies schema migrations on startup
  - Pre-lineup predictions include probable pitcher names
affects: [15-live-poller, 16-reconciliation]

# Tech tracking
tech-stack:
  added: []
  patterns: [migration-on-startup, display-only-pitcher-names]

key-files:
  created: []
  modified:
    - src/pipeline/db.py
    - src/pipeline/runner.py
    - tests/test_pipeline/test_runner.py

key-decisions:
  - "Pre-lineup pitcher names are display-only; sp_uncertainty stays True because TEAM_ONLY models are still used"
  - "pyproject.toml and api/main.py already had correct changes from prior plans; only db.py warning log was missing"

patterns-established:
  - "Migration file missing: log warning with path and packaging hint, not silent skip"

requirements-completed: [SCHM-01, VIBL-02]

# Metrics
duration: 3min
completed: 2026-03-31
---

# Phase 13 Plan 04: UAT Gap Closure Summary

**Migration warning logging in apply_schema() and pre-lineup pitcher name passthrough for display**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-31T16:04:17Z
- **Completed:** 2026-03-31T16:06:57Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- apply_schema() now logs a warning with the expected path when migration_001.sql is missing, aiding Docker debugging
- Pre-lineup predictions pass confirmed probable pitcher names (home_sp/away_sp) instead of hardcoded None
- New test covers the missing-pitcher edge case (None values) with sp_uncertainty=True

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix migration packaging and API startup migration call** - `62fd8f6` (feat)
2. **Task 2 RED: Failing tests for pre-lineup pitcher names** - `c84bb60` (test)
3. **Task 2 GREEN: Pass probable pitcher names in pre-lineup** - `7044d9f` (feat)

**Plan metadata:** (pending) (docs: complete plan)

_Note: Task 2 used TDD with separate RED and GREEN commits._

## Files Created/Modified
- `src/pipeline/db.py` - Added logger.info on successful migration and logger.warning when migration file missing
- `src/pipeline/runner.py` - Changed _process_pre_lineup() to pass game.get("home_probable_pitcher") / game.get("away_probable_pitcher")
- `tests/test_pipeline/test_runner.py` - Updated pre_lineup assertions to expect pitcher names; added test_pre_lineup_no_pitcher_available

## Decisions Made
- Pre-lineup pitcher names are display-only: sp_uncertainty remains True because TEAM_ONLY models are still used for the 10am prediction
- pyproject.toml migration glob and api/main.py apply_schema call were already in place from plans 01-03; only the db.py warning log was a net-new change in Task 1

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Task 1 mostly already done from prior plans**
- **Found during:** Task 1 (Fix migration packaging and API startup)
- **Issue:** pyproject.toml already had migration_*.sql glob and api/main.py already called apply_schema -- only the db.py warning log was missing
- **Fix:** Applied only the missing db.py warning log change; did not re-apply already-present changes
- **Files modified:** src/pipeline/db.py
- **Verification:** All three verification checks passed
- **Committed in:** 62fd8f6

---

**Total deviations:** 1 (partial overlap with prior plans, no scope creep)
**Impact on plan:** Minimal -- 2 of 3 Task 1 changes were already present; only net-new work was the warning log.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 13 UAT gaps fully closed
- Schema migration runs automatically on API container startup with proper logging
- Pre-lineup predictions display pitcher names when available
- Ready for Phase 14+ (live poller, reconciliation)

## Self-Check: PASSED

All files exist, all commits verified (62fd8f6, c84bb60, 7044d9f).

---
*Phase: 13-schema-migration-and-game-visibility*
*Completed: 2026-03-31*
