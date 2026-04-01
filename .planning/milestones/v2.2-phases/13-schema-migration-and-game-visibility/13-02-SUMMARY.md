---
phase: 13-schema-migration-and-game-visibility
plan: 02
subsystem: api
tags: [fastapi, pydantic, statsapi, caching, schedule]

# Dependency graph
requires:
  - phase: 13-01
    provides: "game_id column in predictions table for join matching"
provides:
  - "GET /api/v1/games/{date} endpoint returning all scheduled games merged with predictions"
  - "map_game_status() for MLB status -> badge status mapping"
  - "fetch_schedule_for_date() using raw statsapi.get() with full status fields"
  - "get_schedule_cached() with 75s TTL thread-safe cache"
  - "PredictionGroup, GameResponse, GamesDateResponse Pydantic models"
affects: [13-03, 14-date-navigation, 15-live-poller]

# Tech tracking
tech-stack:
  added: []
  patterns: ["TTL cache with threading.Lock for schedule data", "game_id-first then team-pair fallback matching", "stub cards (prediction=null) for games without predictions"]

key-files:
  created:
    - api/routes/games.py
    - tests/test_api/test_games.py
  modified:
    - src/data/mlb_schedule.py
    - api/models.py
    - api/main.py

key-decisions:
  - "Used raw statsapi.get() instead of statsapi.schedule() wrapper to preserve abstractGameState/codedGameState fields"
  - "75s TTL cache with max 7 entries to bound memory before Phase 14 date nav"
  - "game_id matching takes priority over team-pair fallback for prediction merge"

patterns-established:
  - "Schedule cache pattern: thread-safe TTL cache with Lock, fetch outside lock"
  - "Merge pattern: schedule-driven loop with prediction lookup (game_id first, team-pair fallback)"
  - "Stub card pattern: games without predictions return prediction=null"

requirements-completed: [VIBL-01, VIBL-02]

# Metrics
duration: 5min
completed: 2026-03-31
---

# Phase 13 Plan 02: Games Date Endpoint Summary

**GET /games/{date} endpoint merging MLB schedule with predictions, enabling stub cards for games without predictions and accurate status badges (PRE_GAME/LIVE/FINAL/POSTPONED)**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-31T12:42:15Z
- **Completed:** 2026-03-31T12:47:17Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Created /games/{date} endpoint that returns all scheduled games for a date, including those without predictions (stub cards)
- Added status mapping logic: Preview->PRE_GAME, Live->LIVE, Final->FINAL, codedGameState D->POSTPONED
- Implemented TTL-cached schedule fetch using raw statsapi.get() for full status field access
- Added PredictionGroup model enabling pre/post-lineup prediction grouping per game
- 15 tests covering status mapping, merge logic, stub cards, doubleheaders, and endpoint integration

## Task Commits

Each task was committed atomically:

1. **Task 1: Add fetch_schedule_for_date with TTL cache and status mapping** - `2e849b3` (feat)
2. **Task 2: Create Pydantic models, /games/{date} route, register router, and add tests** - `43d2904` (feat)

## Files Created/Modified
- `src/data/mlb_schedule.py` - Added map_game_status(), fetch_schedule_for_date(), get_schedule_cached() with 75s TTL
- `api/models.py` - Added PredictionGroup, GameResponse, GamesDateResponse Pydantic models
- `api/routes/games.py` - New route handler with schedule+prediction merge logic
- `api/main.py` - Registered games router under /api/v1
- `tests/test_api/test_games.py` - 15 tests for status mapping, merge logic, and endpoint

## Decisions Made
- Used raw statsapi.get() instead of statsapi.schedule() wrapper to preserve abstractGameState/codedGameState fields needed for status badges
- 75s TTL cache with max 7 entries bounds memory before Phase 14 date navigation adds multi-date access
- game_id-first matching priority with team-pair fallback handles both new (game_id populated) and legacy (game_id NULL) prediction rows

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- /games/{date} endpoint ready for dashboard integration (Phase 13-03 verification)
- Schedule cache ready for Phase 14 date navigation (multi-date access patterns)
- Status mapping ready for Phase 15 live poller (LIVE status detection)
- Existing /predictions/today endpoint unchanged -- no regression

## Self-Check: PASSED

All 5 files verified present. Both task commits (2e849b3, 43d2904) found in git log.

---
*Phase: 13-schema-migration-and-game-visibility*
*Completed: 2026-03-31*
