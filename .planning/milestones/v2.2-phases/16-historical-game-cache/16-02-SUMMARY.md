---
phase: 16-historical-game-cache
plan: 02
subsystem: database
tags: [postgres, statsapi, seed-script, incremental-sync, cli]

# Dependency graph
requires:
  - phase: 16-historical-game-cache
    plan: 01
    provides: game_logs table DDL, batch_insert_game_logs(), sync_game_logs(), apply_schema migration_002
provides:
  - seed_game_logs.py standalone CLI for one-time 2025+2026 game_logs backfill
  - run_pipeline.py sync_game_logs integration at worker startup (both modes)
affects: [16-03-feature-builder-modification]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Seed script calls apply_schema() before insert to ensure migration has run"
    - "sync_game_logs wrapped in try/except for non-fatal failure at pipeline startup"
    - "Seed script uses _normalize_game helper with _SKIP_NORMALIZE guard for Tie values"

key-files:
  created:
    - scripts/seed_game_logs.py
  modified:
    - scripts/run_pipeline.py

key-decisions:
  - "Seed script extracted _normalize_game as a helper function for clarity and reusability"
  - "sync_game_logs failure is non-fatal: pipeline continues with stale data if MLB API is down"
  - "Seed script defaults to seasons 2025+2026 per product owner decision; CLI --seasons allows override"

patterns-established:
  - "Seed scripts call apply_schema() before data operations to self-ensure schema readiness"
  - "Non-critical sync operations wrapped in try/except with warning log at pipeline startup"

requirements-completed: [CACHE-02, CACHE-03]

# Metrics
duration: 2min
completed: 2026-03-31
---

# Phase 16 Plan 02: Seed Script and Pipeline Sync Integration Summary

**One-time seed CLI for game_logs backfill with incremental sync wired into worker startup for both scheduler and single-run modes**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-01T00:17:45Z
- **Completed:** 2026-04-01T00:20:25Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Created scripts/seed_game_logs.py with --seasons CLI arg (default 2025 2026), statsapi.schedule fetch, Final+R filter, normalize_team with _SKIP_NORMALIZE guard, and batch_insert_game_logs for idempotent insert
- Wired sync_game_logs(pool) into run_pipeline.py _run_scheduler and _run_once, wrapped in try/except for non-fatal failure

## Task Commits

Each task was committed atomically:

1. **Task 1: Create seed_game_logs.py CLI script** - `d369bce` (feat)
2. **Task 2: Wire sync_game_logs into run_pipeline.py startup** - `31525de` (feat)

## Files Created/Modified
- `scripts/seed_game_logs.py` - Standalone CLI: backfills game_logs from MLB Stats API for specified seasons (143 lines)
- `scripts/run_pipeline.py` - Added sync_game_logs import and calls in both _run_scheduler and _run_once

## Decisions Made
- Extracted _normalize_game() as a named helper in seed_game_logs.py for clarity (plan showed inline normalization; function extraction is cleaner)
- sync_game_logs failure is deliberately non-fatal -- the pipeline can run with stale game_logs data if MLB API is temporarily down

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Seed script ready for manual invocation: `python scripts/seed_game_logs.py` or `docker compose exec worker python scripts/seed_game_logs.py`
- Pipeline worker now syncs game_logs on every startup before scheduled jobs
- Plan 03 (FeatureBuilder modification) can now proceed: game_logs table is seeded and kept current

## Self-Check: PASSED

All 3 files found. All 2 commits verified.

---
*Phase: 16-historical-game-cache*
*Completed: 2026-03-31*
