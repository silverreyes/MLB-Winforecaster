---
phase: 07-live-pipeline-and-database
plan: 01
subsystem: database
tags: [postgres, psycopg3, schema, connection-pool, pipeline]

# Dependency graph
requires:
  - phase: 06-model-retrain-and-calibration
    provides: Trained model artifacts with calibrators and feature_cols for pipeline consumption
provides:
  - Postgres schema DDL (games, predictions, pipeline_runs tables)
  - Python DB access layer with connection pool and CRUD helpers
  - Test infrastructure with pg_pool fixture and 8 schema tests
affects: [07-02, 07-03, 08-api-and-dashboard]

# Tech tracking
tech-stack:
  added: [psycopg3, psycopg-pool, APScheduler]
  patterns: [ConnectionPool context manager, parameterized queries, UPSERT with ON CONFLICT, idempotent schema application]

key-files:
  created:
    - src/pipeline/__init__.py
    - src/pipeline/schema.sql
    - src/pipeline/db.py
    - tests/test_pipeline/__init__.py
    - tests/test_pipeline/conftest.py
    - tests/test_pipeline/test_schema.py
  modified:
    - requirements.txt

key-decisions:
  - "psycopg3 (not psycopg2) for async-ready connection pool and modern Python type support"
  - "ENUM types for prediction_version and prediction_status enforce domain values at DB level"
  - "UPSERT pattern (ON CONFLICT DO UPDATE) for re-run safety instead of failing on duplicates"
  - "apply_schema handles DuplicateObject for ENUMs to allow idempotent re-runs"

patterns-established:
  - "Pool-based DB access: all helpers accept ConnectionPool, use pool.connection() context manager"
  - "Parameterized queries: all SQL uses %(name)s placeholders, never string formatting"
  - "Test isolation: clean_tables fixture drops and recreates schema per test (not autouse)"
  - "Graceful skip: pg_pool fixture skips tests when Postgres is unavailable"

requirements-completed: [PIPE-01, PIPE-07]

# Metrics
duration: 4min
completed: 2026-03-30
---

# Phase 7 Plan 01: Database Schema and Access Layer Summary

**Postgres schema with 3 tables, 2 ENUMs, CHECK/UNIQUE constraints, and psycopg3 connection pool access layer**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-30T03:11:34Z
- **Completed:** 2026-03-30T03:15:25Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Postgres schema DDL with games, predictions, and pipeline_runs tables enforcing business invariants at the DB level
- Python DB access layer with 8 exported functions: pool management, prediction CRUD, pipeline run lifecycle
- Test infrastructure with 8 tests covering schema creation, CHECK constraint (post_lineup requires confirmed), UNIQUE constraint/UPSERT, ENUM validation, and CRUD helpers

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Postgres schema, DB access layer, and install dependencies** - `3def550` (feat)
2. **Task 2: Create test infrastructure and schema/constraint tests** - `2e770ea` (test)

## Files Created/Modified
- `src/pipeline/__init__.py` - Package marker for pipeline module
- `src/pipeline/schema.sql` - Complete DDL with 3 tables, 2 ENUMs, 2 constraints, 4 indexes
- `src/pipeline/db.py` - Connection pool management and CRUD helpers (8 exported functions)
- `tests/test_pipeline/__init__.py` - Package marker for pipeline tests
- `tests/test_pipeline/conftest.py` - pg_pool, clean_tables, sample_prediction_data fixtures
- `tests/test_pipeline/test_schema.py` - 8 tests for schema, constraints, and CRUD helpers
- `requirements.txt` - Added psycopg[binary,pool] and APScheduler dependencies

## Decisions Made
- psycopg3 (not psycopg2) chosen for modern async-ready connection pool and native Python type support
- ENUM types enforce prediction_version and prediction_status at the database level
- UPSERT pattern (ON CONFLICT DO UPDATE) for re-run safety instead of raising on duplicates
- apply_schema catches DuplicateObject for ENUMs to allow idempotent re-runs
- clean_tables fixture is explicitly requested (not autouse) to prevent Postgres connection attempts in unit tests

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] psycopg-pool package not installed by extras syntax**
- **Found during:** Task 1 (dependency installation)
- **Issue:** `pip install -r requirements.txt` installed psycopg but not psycopg_pool; the `[pool]` extras syntax did not resolve the dependency
- **Fix:** Explicitly installed `psycopg-pool` via `python -m pip install psycopg-pool`
- **Files modified:** None (runtime install only; requirements.txt already correct)
- **Verification:** `from psycopg_pool import ConnectionPool` imports successfully
- **Committed in:** 3def550 (part of Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minor pip resolution issue, no code or scope changes needed.

## Issues Encountered
None beyond the psycopg-pool installation issue documented above.

## User Setup Required
None - no external service configuration required. Test Postgres can be started via Docker when running integration tests.

## Next Phase Readiness
- Schema and DB access layer ready for 07-02 (LiveFeatureBuilder) and 07-03 (Scheduler and Orchestrator)
- All 8 helper functions exported and importable
- Test infrastructure ready for additional pipeline tests in subsequent plans

## Self-Check: PASSED

All 6 created files verified present. Both task commits (3def550, 2e770ea) verified in git log.

---
*Phase: 07-live-pipeline-and-database*
*Completed: 2026-03-30*
