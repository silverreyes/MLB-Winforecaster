---
phase: 14-date-navigation
plan: 01
subsystem: api
tags: [fastapi, pydantic, mlb-statsapi, timezone, ET, view-mode, probable-pitchers]

# Dependency graph
requires:
  - phase: 13-schema-migration-and-game-visibility
    provides: /games/{date} endpoint, schedule caching, GameResponse/GamesDateResponse models
provides:
  - view_mode field on GamesDateResponse (live/historical/tomorrow/future)
  - prediction_label and pitcher fields on GameResponse
  - compute_view_mode() server-side date classification using ET timezone
  - Probable pitcher hydration via probablePitcher(note) API parameter
  - PRELIMINARY label logic for tomorrow games with both SPs confirmed
affects: [14-02-PLAN, 14-03-PLAN, frontend-date-navigation, live-poller]

# Tech tracking
tech-stack:
  added: [zoneinfo]
  patterns: [server-side date classification, composite cache keys, pitcher hydration]

key-files:
  created: [tests/test_api/test_games.py (new test classes)]
  modified: [api/models.py, api/routes/games.py, src/data/mlb_schedule.py]

key-decisions:
  - "Server-side view_mode via ET timezone avoids client-side date math pitfalls"
  - "Composite cache key (date:pitchers) prevents returning non-pitcher data for tomorrow requests"
  - "Pitcher fields always present in schedule dicts (None when not hydrated) for consistent dict shape"

patterns-established:
  - "ET timezone constant at module level for date classification"
  - "Composite cache keys when same endpoint has variant data shapes"
  - "_apply_tomorrow_labels mutates GameResponse in-place after build_games_response"

requirements-completed: [DATE-04, DATE-05, DATE-06, DATE-07, DATE-08]

# Metrics
duration: 5min
completed: 2026-03-31
---

# Phase 14 Plan 01: API View Mode and Tomorrow Labels Summary

**Server-side view_mode computation with ET timezone, probable pitcher hydration for tomorrow games, and PRELIMINARY label logic when both SPs confirmed**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-31T17:27:48Z
- **Completed:** 2026-03-31T17:32:33Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 4

## Accomplishments
- Added view_mode field to every /games/{date} response (live/historical/tomorrow/future) computed server-side using America/New_York timezone
- Extended GameResponse with prediction_label, home_probable_pitcher, and away_probable_pitcher fields
- Added probable pitcher hydration via probablePitcher(note) MLB API parameter for tomorrow's schedule
- Implemented PRELIMINARY label logic: tomorrow games with both SPs confirmed get labeled, others remain null
- Comprehensive TDD test coverage: 15 new tests across TestDateNavigation and TestTomorrowPreliminary classes

## Task Commits

Each task was committed atomically (TDD flow):

1. **Task 1 RED: Failing tests** - `40667dc` (test)
2. **Task 1 GREEN: Implementation** - `43e4513` (feat)

_Note: TDD task with RED (failing tests) and GREEN (implementation) commits._

## Files Created/Modified
- `api/models.py` - Added prediction_label, home/away_probable_pitcher to GameResponse; view_mode to GamesDateResponse
- `api/routes/games.py` - Added compute_view_mode(), _is_pitcher_confirmed(), _apply_tomorrow_labels(); updated endpoint
- `src/data/mlb_schedule.py` - Added include_pitchers param to fetch_schedule_for_date and get_schedule_cached with composite cache key
- `tests/test_api/test_games.py` - Added TestDateNavigation (7 tests) and TestTomorrowPreliminary (8 tests)

## Decisions Made
- Server-side view_mode computed via ET timezone to avoid client-side date math timezone pitfalls
- Composite cache key (`date:pitchers` vs `date`) prevents returning non-pitcher data for tomorrow requests
- Pitcher fields (home_probable_pitcher, away_probable_pitcher) always present in schedule dicts as None when not hydrated, for consistent dict shape

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Pre-existing test failures in test_feature_builder.py and test_leakage.py (unrelated to this plan's changes) -- documented as out-of-scope

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- API now returns view_mode in every /games/{date} response -- frontend can use this for rendering decisions
- Tomorrow games include pitcher data and PRELIMINARY labels -- ready for Plan 02 (frontend date picker) and Plan 03 (frontend rendering)
- No blockers for Plan 02

## Self-Check: PASSED

All files exist, all commits verified.

---
*Phase: 14-date-navigation*
*Completed: 2026-03-31*
