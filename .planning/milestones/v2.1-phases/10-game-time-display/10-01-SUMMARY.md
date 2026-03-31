---
phase: 10-game-time-display
plan: 01
subsystem: api, ui
tags: [fastapi, pydantic, react, intl, mlb-stats-api, timezone]

# Dependency graph
requires:
  - phase: none
    provides: existing API and frontend infrastructure
provides:
  - game_time field in PredictionResponse API model
  - Schedule lookup joining MLB Stats API game_datetime to predictions
  - Eastern Time game time display on game cards
  - "Time TBD" fallback for null game times
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Schedule lookup pattern: _build_schedule_lookup() joins MLB Stats API schedule to DB predictions by (home_team, away_team) tuple key"
    - "Graceful degradation: schedule fetch failures return empty lookup, game_time defaults to null"
    - "Timezone display: Intl.DateTimeFormat with America/New_York for consistent ET conversion"

key-files:
  created: []
  modified:
    - api/models.py
    - api/routes/predictions.py
    - tests/test_api/test_predictions.py
    - frontend/src/api/types.ts
    - frontend/src/hooks/usePredictions.ts
    - frontend/src/components/GameCard.tsx
    - frontend/src/components/GameCard.module.css

key-decisions:
  - "game_time field is datetime | None in Pydantic model (not str | None) for server-side validation"
  - "Schedule lookup only on /predictions/today endpoint; historical dates return game_time null"
  - "ET conversion done client-side via Intl.DateTimeFormat, not server-side"

patterns-established:
  - "Schedule-to-prediction join: normalize_team() bridges MLB Stats API full names to DB team codes"
  - "Graceful API degradation: wrap external API calls in try/except, log warning, return empty fallback"

requirements-completed: [GMTIME-01, GMTIME-02, GMTIME-03]

# Metrics
duration: 4min
completed: 2026-03-30
---

# Phase 10 Plan 01: Game Time Display Summary

**game_time field added to API response from MLB Stats API schedule, displayed as "7:05 PM ET" on game cards with "Time TBD" amber fallback**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-30T20:39:45Z
- **Completed:** 2026-03-30T20:43:48Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- API PredictionResponse now includes game_time (UTC ISO datetime) joined from MLB Stats API schedule data
- Game cards display start time in "7:05 PM ET" format using Intl.DateTimeFormat with America/New_York timezone
- Null game times display "Time TBD" in amber (--color-accent-muted) for visual distinction
- Schedule fetch failures degrade gracefully -- game_time is null, no 500 errors

## Task Commits

Each task was committed atomically:

1. **Task 1: Add game_time to API prediction response** (TDD)
   - `8ed00f2` (test: add failing tests for game_time)
   - `430c699` (feat: implement game_time in API response)
2. **Task 2: Display game time on game cards in Eastern Time** - `86b67b3` (feat)

**Plan metadata:** pending (docs: complete plan)

## Files Created/Modified
- `api/models.py` - Added game_time: datetime | None = None field to PredictionResponse
- `api/routes/predictions.py` - Added _build_schedule_lookup(), _parse_game_time(), extended _build_prediction and _fetch_predictions
- `tests/test_api/test_predictions.py` - Added 4 new tests for game_time behavior (populated, null, historical, fetch failure)
- `frontend/src/api/types.ts` - Added game_time to PredictionResponse and GameGroup interfaces
- `frontend/src/hooks/usePredictions.ts` - Propagated game_time to GameGroup in groupPredictions
- `frontend/src/components/GameCard.tsx` - Added formatGameTime() helper and game time display element
- `frontend/src/components/GameCard.module.css` - Added .gameTime and .gameTimeTbd style classes

## Decisions Made
- Used datetime | None (not str | None) for Pydantic game_time field to preserve server-side validation
- Schedule lookup only applied to /predictions/today endpoint; historical dates always return game_time as null since MLB Stats API only provides today's schedule
- ET conversion done client-side via Intl.DateTimeFormat for proper DST handling across user environments

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- game_time field is available in the API response for any future phases that need it
- Phase 11 and 12 (Explainability, Tooltip) have no dependency on this phase and can proceed independently
- Pre-existing test_feature_builder.py::test_rolling_ops failure noted (unrelated to this phase)

## Self-Check: PASSED

All 7 modified files verified present. All 3 task commits (8ed00f2, 430c699, 86b67b3) verified in git log.

---
*Phase: 10-game-time-display*
*Completed: 2026-03-30*
