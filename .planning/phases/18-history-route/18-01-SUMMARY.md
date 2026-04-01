---
phase: 18-history-route
plan: 01
subsystem: api
tags: [fastapi, pydantic, postgres, history, accuracy]

# Dependency graph
requires:
  - phase: 17-final-outcomes-and-nightly-reconciliation
    provides: prediction_correct and actual_winner columns populated by reconciliation
  - phase: 16-historical-game-cache
    provides: game_logs table with final scores for game_id join
provides:
  - GET /api/v1/history endpoint returning past predictions with outcomes
  - get_history() DB function with post_lineup preference and game_logs join
  - HistoryRow, ModelAccuracy, HistoryResponse Pydantic models
  - _compute_accuracy() per-model accuracy from ensemble+prediction_correct
affects: [18-02 frontend history page]

# Tech tracking
tech-stack:
  added: []
  patterns: [ROW_NUMBER post_lineup preference, ensemble-derived per-model accuracy]

key-files:
  created:
    - api/routes/history.py
    - tests/test_api/test_history.py
  modified:
    - src/pipeline/db.py
    - api/models.py
    - api/main.py

key-decisions:
  - "Per-model accuracy derived from ensemble+prediction_correct to determine actual outcome, then each model evaluated individually"
  - "Route tests use conftest.py client fixture with mocked lifespan for proper TestClient setup"

patterns-established:
  - "ROW_NUMBER with CASE for prediction_version preference (post_lineup > confirmation > pre_lineup)"
  - "Ensemble-derived actual outcome: home_won = (ensemble >= 0.5 AND pc) OR (ensemble < 0.5 AND NOT pc)"

requirements-completed: [HIST-01, HIST-02, HIST-03, HIST-04]

# Metrics
duration: 6min
completed: 2026-04-01
---

# Phase 18 Plan 01: History Route Summary

**GET /api/v1/history endpoint with post_lineup preference, game_logs score join, and per-model accuracy computation**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-01T06:06:48Z
- **Completed:** 2026-04-01T06:13:14Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- get_history() DB function: ROW_NUMBER for post_lineup preference, prediction_correct IS NOT NULL filter, LEFT JOIN game_logs with game_id::INTEGER cast
- HistoryRow, ModelAccuracy, HistoryResponse Pydantic models for typed response serialization
- GET /history route handler with date validation (400 on invalid format), _compute_accuracy per-model evaluation
- 15 unit tests covering DB query, Pydantic models, accuracy computation, and route-level behavior

## Task Commits

Each task was committed atomically:

1. **Task 1: Database query + Pydantic models + tests (TDD)** - `b9e689e` (test) -> `028f898` (feat)
2. **Task 2: History route handler + main.py registration** - `da9dbf7` (feat)

_Note: Task 1 used TDD with separate RED and GREEN commits_

## Files Created/Modified
- `src/pipeline/db.py` - Added get_history() function with ranked CTE query
- `api/models.py` - Added HistoryRow, ModelAccuracy, HistoryResponse models
- `api/routes/history.py` - Created route handler with _compute_accuracy helper
- `api/main.py` - Registered history_router under /api/v1 prefix
- `tests/test_api/test_history.py` - 15 tests for DB, models, accuracy, and routes

## Decisions Made
- Per-model accuracy uses ensemble probability + prediction_correct to derive actual outcome, then evaluates each model individually against that outcome
- Route tests use the shared conftest.py `client` fixture (mocked lifespan) rather than standalone TestClient creation
- _compute_accuracy skips rows where any probability or prediction_correct is None

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed route tests using standalone TestClient**
- **Found during:** Task 2 (route-level tests)
- **Issue:** Tests creating TestClient directly triggered lifespan which requires real DB pool and model artifacts, causing 500 errors
- **Fix:** Updated route tests to use conftest.py `client` fixture which mocks lifespan dependencies
- **Files modified:** tests/test_api/test_history.py
- **Verification:** All 15 tests pass
- **Committed in:** da9dbf7 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary fix for test correctness. No scope creep.

## Issues Encountered
None beyond the TestClient fixture issue documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- History API endpoint complete and tested, ready for frontend consumption in Plan 18-02
- Response shape (HistoryResponse) provides all data needed for history page: games list, per-model accuracy, date range

## Self-Check: PASSED

All 5 files found. All 3 commits verified (b9e689e, 028f898, da9dbf7).

---
*Phase: 18-history-route*
*Completed: 2026-04-01*
