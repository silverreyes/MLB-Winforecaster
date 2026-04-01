---
phase: 13-schema-migration-and-game-visibility
plan: 03
subsystem: ui
tags: [react, typescript, css-modules, status-badge, game-visibility]

# Dependency graph
requires:
  - phase: 13-02
    provides: "/games/{date} API endpoint returning GameResponse with game_status and prediction groups"
provides:
  - "GameStatus, PredictionGroup, GameResponse, GamesDateResponse TypeScript types"
  - "useGames() hook fetching /games/{date} with 60s polling"
  - "StatusBadge component rendering PRE-GAME/LIVE/FINAL/POSTPONED badges"
  - "Updated GameCard supporting stub cards (no prediction body) and StatusBadge"
  - "GameCardGrid using game_id as React key (fixes doubleheader collision)"
  - "App.tsx wired to useGames() instead of usePredictions()"
affects: [live-poller-ui, historical-accuracy-display, date-navigation]

# Tech tracking
tech-stack:
  added: []
  patterns: ["stub card pattern -- GameCard conditionally omits predictionBody and KalshiSection when prediction is null"]

key-files:
  created:
    - frontend/src/hooks/useGames.ts
    - frontend/src/components/StatusBadge.tsx
    - frontend/src/components/StatusBadge.module.css
  modified:
    - frontend/src/api/types.ts
    - frontend/src/components/GameCard.tsx
    - frontend/src/components/GameCard.module.css
    - frontend/src/components/GameCardGrid.tsx
    - frontend/src/App.tsx

key-decisions:
  - "Preserved existing GameGroup/TodayResponse types for backward compatibility with usePredictions and useLatestTimestamp hooks"
  - "StatusBadge placed between game time and SP row in card header per UI-SPEC layout contract"

patterns-established:
  - "Stub card pattern: when prediction is null, card renders header only (matchup + time + badge + SP TBD), no prediction body or Kalshi section"
  - "game_id as React key instead of team-pair string to handle doubleheaders"

requirements-completed: [VIBL-01, VIBL-02]

# Metrics
duration: 4min
completed: 2026-03-31
---

# Phase 13 Plan 03: Frontend Game Visibility Summary

**Dashboard fetches /games/{date} showing all scheduled games with status badges and stub cards for games without predictions**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-31T12:51:07Z
- **Completed:** 2026-03-31T12:55:18Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Added TypeScript types (GameStatus, PredictionGroup, GameResponse, GamesDateResponse) and useGames() hook fetching /games/{date} with 60-second polling
- Created StatusBadge component with 4 color variants (PRE-GAME gray, LIVE green, FINAL gray, POSTPONED amber) per UI-SPEC
- Updated GameCard to accept GameResponse, render StatusBadge in header, and conditionally omit prediction body for stub cards
- Switched App.tsx from usePredictions() to useGames(), and GameCardGrid from team-pair key to game_id key

## Task Commits

Each task was committed atomically:

1. **Task 1: Add TypeScript types and useGames hook** - `04dd272` (feat)
2. **Task 2: Create StatusBadge component and update GameCard/GameCardGrid/App** - `b797a0b` (feat)

**Plan metadata:** pending (docs: complete plan)

## Files Created/Modified
- `frontend/src/api/types.ts` - Added GameStatus, PredictionGroup, GameResponse, GamesDateResponse types
- `frontend/src/hooks/useGames.ts` - New hook fetching /games/{date} with 60s polling and today default
- `frontend/src/components/StatusBadge.tsx` - New component rendering 4 status badge variants
- `frontend/src/components/StatusBadge.module.css` - Badge styles: preGame, live, final, postponed
- `frontend/src/components/GameCard.tsx` - Rewritten to accept GameResponse, render StatusBadge, support stub cards
- `frontend/src/components/GameCard.module.css` - Added .statusBadge margin class
- `frontend/src/components/GameCardGrid.tsx` - Updated to use GameResponse[] and game_id as React key
- `frontend/src/App.tsx` - Switched from usePredictions() to useGames(), updated displayedTimestamp source

## Decisions Made
- Preserved existing GameGroup/TodayResponse/LatestTimestampResponse types -- still used by usePredictions (backward compat) and useLatestTimestamp hooks
- StatusBadge placed on its own line between game time and SP row, with 4px top margin matching header spacing rhythm

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 13 is now fully complete (all 3 plans executed)
- Frontend displays all scheduled games from /games/{date} endpoint
- Ready for Phase 14 (live poller) or Phase 15 (reconciliation) work

## Self-Check: PASSED

All 8 files verified present. Both task commits (04dd272, b797a0b) verified in git log.

---
*Phase: 13-schema-migration-and-game-visibility*
*Completed: 2026-03-31*
