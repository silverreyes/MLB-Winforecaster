---
phase: 15-live-score-polling
plan: 01
subsystem: api, data
tags: [pydantic, statsapi, caching, threading, pytest]

# Dependency graph
requires:
  - phase: 13-schema-migration-and-game-visibility
    provides: GameResponse model, get_schedule_cached pattern, map_game_status
provides:
  - LiveScoreData Pydantic model with 14 typed fields
  - GameResponse.live_score optional field
  - get_linescore_cached() with 90s TTL thread-safe cache
  - parse_linescore() extracting score, inning, runners, batter, on-deck from raw MLB API
  - Test scaffolds for LIVE-01, LIVE-04, LIVE-05, LIVE-06, LIVE-07, LIVE-08
affects: [15-02 route enrichment, 15-03 frontend live display, 15-04 live poller job]

# Tech tracking
tech-stack:
  added: []
  patterns: [per-game linescore cache (dict + Lock + TTL), MLB API fields parameter filtering]

key-files:
  created:
    - tests/test_api/test_games_live.py
    - tests/test_pipeline/test_live_poller.py
  modified:
    - api/models.py
    - src/data/mlb_schedule.py

key-decisions:
  - "Linescore cache uses same dict+Lock+TTL pattern as schedule cache, bounded to 20 entries"
  - "statsapi.get('game') fields parameter reduces ~500KB response to ~5-10KB"
  - "inningHalf 'Middle'/'End' default to 'top' for display consistency"

patterns-established:
  - "Per-game linescore cache: dict[int, tuple[float, dict]] with 90s TTL and 20-entry max"
  - "parse_linescore defensive .get() chaining with None return for pre-game state"
  - "Batter stats lookup via f'ID{batter_id}' key in both home and away boxscore players"

requirements-completed: [LIVE-01, LIVE-04, LIVE-05, LIVE-06, LIVE-07]

# Metrics
duration: 4min
completed: 2026-03-31
---

# Phase 15 Plan 01: Data Layer Summary

**LiveScoreData Pydantic model, 90s TTL linescore cache, and parse_linescore function extracting 14 live game fields from MLB Stats API with test scaffolds for all LIVE requirements**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-31T22:13:13Z
- **Completed:** 2026-03-31T22:17:17Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Created test scaffolds for all LIVE requirements (20 test items: 12 parse/cache + 8 poller stubs)
- Added LiveScoreData Pydantic model with 14 typed fields extending GameResponse
- Implemented get_linescore_cached() with 90s TTL, 20-entry max, thread-safe Lock
- Implemented parse_linescore() extracting score, inning, runners, batter stats, on-deck from raw API
- All 12 parse/cache tests pass, 8 poller stubs skip cleanly

## Task Commits

Each task was committed atomically:

1. **Task 1: Create test scaffolds for all LIVE requirements (Wave 0)** - `84b9127` (test)
2. **Task 2: LiveScoreData model + linescore cache + parse_linescore function** - `997f42f` (feat)

## Files Created/Modified
- `tests/test_api/test_games_live.py` - 12 tests for parse_linescore and get_linescore_cached (LIVE-01/04/05/06/07)
- `tests/test_pipeline/test_live_poller.py` - 8 stub tests for live poller and outcome write (LIVE-08)
- `api/models.py` - LiveScoreData nested model, GameResponse.live_score field
- `src/data/mlb_schedule.py` - get_linescore_cached(), parse_linescore(), linescore cache state

## Decisions Made
- Linescore cache follows identical dict+Lock+TTL pattern as existing schedule cache for consistency
- statsapi.get('game') fields parameter used to reduce response size from ~500KB-2MB to ~5-10KB
- inningHalf values "Middle" and "End" default to "top" for display (Pitfall 4 mitigation)
- Batter stats lookup checks both home and away boxscore players using f'ID{batter_id}' key format

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- LiveScoreData model and parse_linescore ready for Plan 02 route enrichment
- get_linescore_cached ready for Plan 02 games route handler to call per LIVE game
- Test stubs in test_live_poller.py ready for Plan 02 to fill in with live poller implementation
- All 12 parse/cache tests provide regression safety for refactoring

## Self-Check: PASSED

All files verified present, all commit hashes found in git log.

---
*Phase: 15-live-score-polling*
*Completed: 2026-03-31*
