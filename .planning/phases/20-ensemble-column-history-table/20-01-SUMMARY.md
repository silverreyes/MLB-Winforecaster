---
phase: 20-ensemble-column-history-table
plan: 01
subsystem: api, ui
tags: [ensemble, history, pydantic, sql, react, typescript]

# Dependency graph
requires:
  - phase: 18-history-route
    provides: History API endpoint, HistoryRow model, HistoryPage component
provides:
  - ensemble_prob column in get_history SQL query
  - ensemble_prob field in HistoryRow Pydantic model and TypeScript interface
  - Ens% column in history table UI
  - ENS accuracy in accuracy strip
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SQL CASE/ROUND for derived ensemble column in CTE"
    - "Ensemble accuracy derived from prediction_correct (already ensemble-based)"

key-files:
  created: []
  modified:
    - src/pipeline/db.py
    - api/models.py
    - api/routes/history.py
    - tests/test_api/test_history.py
    - frontend/src/api/types.ts
    - frontend/src/components/HistoryPage.tsx

key-decisions:
  - "Ensemble computed in SQL CTE rather than Python to keep DB as single source of truth"
  - "Ensemble accuracy uses prediction_correct directly since prediction_correct IS the ensemble outcome"

patterns-established:
  - "Derived ensemble columns computed via CASE/ROUND in SQL, not application layer"

requirements-completed: [HIST-03]

# Metrics
duration: 4min
completed: 2026-04-01
---

# Phase 20 Plan 01: Ensemble Column in History Table Summary

**End-to-end ensemble_prob in history: SQL CASE/ROUND computation, Pydantic model, route pass-through, TypeScript type, Ens% table column, ENS accuracy strip**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-01T13:54:13Z
- **Completed:** 2026-04-01T13:58:28Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Added ensemble_prob as SQL-computed column (ROUND of 3-model average) in get_history CTE
- Extended HistoryRow Pydantic model and TypeScript interface with ensemble_prob field
- Rendered Ens% column between XGB% and outcome marker in history table
- Added ENS accuracy to accuracy strip using prediction_correct as ensemble truth

## Task Commits

Each task was committed atomically:

1. **Task 1: Add ensemble_prob to get_history SQL, HistoryRow model, route handler, and tests** - `8da9a24` (feat)
2. **Task 2: Add ensemble_prob to frontend HistoryRow type and render Ensemble% column** - `10fa489` (feat)

**Plan metadata:** [pending] (docs: complete plan)

## Files Created/Modified
- `src/pipeline/db.py` - Added CASE/ROUND ensemble_prob computation in ranked CTE and outer SELECT
- `api/models.py` - Added ensemble_prob field to HistoryRow Pydantic model
- `api/routes/history.py` - Pass ensemble_prob to HistoryRow constructor; added ensemble accuracy tracking in _compute_accuracy
- `tests/test_api/test_history.py` - Added test_sql_computes_ensemble_prob; updated test data with ensemble_prob=0.5767; updated empty assertions for ensemble key
- `frontend/src/api/types.ts` - Added ensemble_prob to TypeScript HistoryRow interface
- `frontend/src/components/HistoryPage.tsx` - Added Ens% column header/cell; updated accuracy strip to include ENS

## Decisions Made
- Ensemble computed in SQL CTE via CASE/ROUND rather than Python application layer -- keeps DB as single source of truth and avoids redundant computation in route handler
- Ensemble accuracy uses prediction_correct directly since prediction_correct is already defined by ensemble logic -- no need for separate ensemble vs actual comparison

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Updated empty-state test assertions for ensemble key**
- **Found during:** Task 2
- **Issue:** test_route_empty_history and test_empty_rows_returns_zero_totals only checked lr/rf/xgb keys but _compute_accuracy now returns ensemble key too
- **Fix:** Added "ensemble" to the model_key iteration in both tests
- **Files modified:** tests/test_api/test_history.py
- **Verification:** All 16 tests pass
- **Committed in:** 10fa489 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Test assertion completeness fix. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- HIST-03 gap fully closed
- History page now displays ensemble probability alongside per-model columns
- Accuracy strip shows ENS accuracy metric

---
## Self-Check: PASSED

All 6 modified files verified on disk. Both task commits (8da9a24, 10fa489) verified in git log.

---
*Phase: 20-ensemble-column-history-table*
*Completed: 2026-04-01*
