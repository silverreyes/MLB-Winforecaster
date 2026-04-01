---
phase: 16-historical-game-cache
plan: 01
subsystem: database
tags: [postgres, psycopg, migration, game-logs, idempotent-insert]

# Dependency graph
requires:
  - phase: 13-schema-migration-and-game-visibility
    provides: migration pattern (migration_001.sql), apply_schema() migration execution
provides:
  - game_logs table DDL via migration_002.sql (11 columns, 4 indexes)
  - batch_insert_game_logs() CRUD function with ON CONFLICT DO NOTHING idempotency
  - sync_game_logs() incremental fetch from MAX(game_date) - 1 day forward
  - test scaffold covering CACHE-01 through CACHE-05
affects: [16-02-seed-script, 16-03-feature-builder-modification]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "migration_002.sql follows migration_001.sql pattern (idempotent, applied in apply_schema)"
    - "batch_insert uses per-row execute loop with rowcount aggregation for insert count"
    - "sync overlap by 1 day from MAX(game_date) catches late West Coast games"
    - "season derived from game_date[:4] not start.year to prevent cross-year bugs"

key-files:
  created:
    - src/pipeline/migration_002.sql
    - tests/test_pipeline/test_game_log_sync.py
  modified:
    - src/pipeline/db.py
    - tests/test_pipeline/conftest.py

key-decisions:
  - "game_id is VARCHAR PRIMARY KEY per locked decision (not INTEGER) -- predictions.game_id is INTEGER, cross-table joins must cast"
  - "Module-level imports for date_cls, timedelta, statsapi in db.py enable clean test patching"
  - "sync_game_logs overlap by 1 day prevents missing late West Coast games"

patterns-established:
  - "migration_002.sql pattern: CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS for idempotent DDL"
  - "batch_insert pattern: per-row execute with ON CONFLICT DO NOTHING, aggregate rowcount for insert count"

requirements-completed: [CACHE-01, CACHE-02, CACHE-03, CACHE-05]

# Metrics
duration: 5min
completed: 2026-03-31
---

# Phase 16 Plan 01: Game Logs Foundation Summary

**game_logs Postgres table with migration DDL, idempotent batch insert, and incremental sync from MAX(game_date) - 1 day forward**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-31T23:54:56Z
- **Completed:** 2026-04-01T00:00:38Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- migration_002.sql creates game_logs table with 11 columns and 4 performance indexes
- batch_insert_game_logs() inserts rows idempotently using INSERT ON CONFLICT DO NOTHING
- sync_game_logs() queries MAX(game_date), fetches from max-1 day to yesterday, filters Final regular-season games, normalizes team names, batch inserts
- Test scaffold with 6 test functions (5 passing, 1 stub for Plan 03)
- Existing schema tests (14) remain green -- zero regression

## Task Commits

Each task was committed atomically:

1. **Task 1: Wave 0 test stubs + migration DDL + conftest update** - `82d79d6` (test: RED), `f510dd6` (feat: GREEN)
2. **Task 2: db.py CRUD functions + apply_schema migration_002 + pass tests** - `d270dd8` (feat)

_Note: Task 1 was TDD -- RED commit (failing tests) followed by GREEN commit (apply_schema migration_002 wiring)._

## Files Created/Modified
- `src/pipeline/migration_002.sql` - game_logs table DDL with VARCHAR PRIMARY KEY on game_id, 4 indexes
- `src/pipeline/db.py` - Added apply_schema migration_002 execution, batch_insert_game_logs(), sync_game_logs()
- `tests/test_pipeline/test_game_log_sync.py` - 6 test functions covering schema, insert, immutability, sync
- `tests/test_pipeline/conftest.py` - Added DROP TABLE IF EXISTS game_logs CASCADE to clean_tables fixture

## Decisions Made
- game_id is VARCHAR PRIMARY KEY per locked decision -- not INTEGER like in the research document's schema example
- Module-level imports for date_cls, timedelta, statsapi in db.py for clean test patching (allows `patch("src.pipeline.db.date_cls")`)
- sync_game_logs overlaps by 1 day from MAX(game_date) to catch late West Coast games that weren't Final at last sync

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Test Postgres container (mlb-test-pg) was not running; started it during execution. Not a code issue.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- game_logs table foundation ready for Plan 02 (seed script) and Plan 03 (FeatureBuilder modification)
- batch_insert_game_logs and sync_game_logs are exported from db.py, ready for import by seed script
- Plan 03 stub test (test_feature_builder_reads_game_logs) is in place, marked @skip

## Self-Check: PASSED

All 5 files found. All 3 commits verified.

---
*Phase: 16-historical-game-cache*
*Completed: 2026-03-31*
