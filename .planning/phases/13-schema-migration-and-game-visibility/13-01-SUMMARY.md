---
phase: 13-schema-migration-and-game-visibility
plan: 01
subsystem: database
tags: [postgres, migration, schema, idempotent-ddl, upsert]

# Dependency graph
requires: []
provides:
  - "game_id column on predictions table for doubleheader disambiguation"
  - "Rebuilt uq_prediction unique constraint including game_id"
  - "Reconciliation columns (actual_winner, prediction_correct, reconciled_at) for Phase 16"
  - "Idempotent migration_001.sql executed at apply_schema() startup"
  - "Pipeline UPSERT passes game_id from game dict through all 4 insert_prediction calls"
affects: [13-02, 13-03, 15-live-poller, 16-reconciliation]

# Tech tracking
tech-stack:
  added: []
  patterns: [idempotent-migration-sql, migration-dir-convention]

key-files:
  created:
    - src/pipeline/migration_001.sql
  modified:
    - src/pipeline/db.py
    - src/pipeline/runner.py
    - tests/test_pipeline/conftest.py
    - tests/test_pipeline/test_schema.py

key-decisions:
  - "Migration SQL executed after main schema.sql in apply_schema(), not inline"
  - "game_id added to _PREDICTION_COLS but NOT _PREDICTION_UPDATE_COLS (immutable per prediction)"
  - "Reconciliation columns excluded from both COLS lists to prevent pipeline UPSERT overwrite"

patterns-established:
  - "Migration file convention: src/pipeline/migration_NNN.sql, loaded by apply_schema()"
  - "Reconciliation columns are write-only by Phase 16 reconciliation process"

requirements-completed: [SCHM-01, SCHM-02]

# Metrics
duration: 3min
completed: 2026-03-31
---

# Phase 13 Plan 01: Schema Migration Summary

**Idempotent migration adding game_id column, rebuilt unique constraint with game_id for doubleheader support, and reconciliation columns for Phase 16 outcome tracking**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-31T12:35:41Z
- **Completed:** 2026-03-31T12:39:01Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Created idempotent migration_001.sql with game_id column, rebuilt unique constraint, 3 reconciliation columns, and partial index
- Updated apply_schema() to execute migration after main schema on every startup
- Added game_id to _PREDICTION_COLS and all 4 insert_prediction calls in runner.py
- Added TestMigration class with 6 tests covering column existence, constraint, UPSERT, doubleheader collision, reconciliation columns, and exclusion verification

## Task Commits

Each task was committed atomically:

1. **Task 1: Create migration SQL and update db.py** - `3424da8` (feat)
2. **Task 2: Update runner.py to pass game_id and add tests** - `94c1c35` (feat)

**Plan metadata:** [pending] (docs: complete plan)

## Files Created/Modified
- `src/pipeline/migration_001.sql` - Idempotent DDL for game_id, unique constraint rebuild, reconciliation columns, game_id index
- `src/pipeline/db.py` - _MIGRATION_DIR constant, apply_schema() migration execution, game_id in _PREDICTION_COLS, reconciliation exclusion comment
- `src/pipeline/runner.py` - game_id pass-through in all 4 insert_prediction calls
- `tests/test_pipeline/conftest.py` - game_id: 718520 added to sample_prediction_data fixture
- `tests/test_pipeline/test_schema.py` - TestMigration class (6 tests), updated expected_columns set

## Decisions Made
- Migration SQL executed after main schema.sql in apply_schema(), keeping migration separate from base DDL
- game_id added to _PREDICTION_COLS but not _PREDICTION_UPDATE_COLS since game_id is immutable per prediction row
- Reconciliation columns deliberately excluded from both COLS lists to prevent pipeline UPSERT from overwriting reconciliation data (Phase 16 writes only)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Schema migration is ready; predictions table will gain game_id and reconciliation columns on next apply_schema() call
- runner.py passes game_id through all insert paths, enabling doubleheader disambiguation
- Phase 13 Plan 02 (API date navigation and game-list endpoint) can proceed
- Phase 16 reconciliation can write to actual_winner, prediction_correct, reconciled_at columns

## Self-Check: PASSED

All 6 files verified present. Both task commits (3424da8, 94c1c35) verified in git log.

---
*Phase: 13-schema-migration-and-game-visibility*
*Completed: 2026-03-31*
