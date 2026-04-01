---
phase: 14-date-navigation
plan: 03
subsystem: ui
tags: [react, typescript, css-modules, date-context, preliminary-badge, empty-state, future-banner]

# Dependency graph
requires:
  - phase: 14-02
    provides: DateNavigator component, useGames hook with viewMode, TypeScript types with ViewMode/prediction_label
provides:
  - FutureDateBanner component for tomorrow and future date contexts
  - Date-context-aware EmptyState with viewMode-dependent copy
  - PRELIMINARY badge on GameCard for confirmed-SP tomorrow games
  - Future-mode GameCard rendering (header-only, no prediction body or Kalshi)
  - Schedule pitcher name display in SP row for tomorrow/future cards
affects: [15-live-score-polling, 16-final-outcomes]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - ViewMode-driven conditional rendering across FutureDateBanner, EmptyState, GameCard
    - Noon-anchored date formatting (T12:00:00) for timezone-safe display dates

key-files:
  created:
    - frontend/src/components/FutureDateBanner.tsx
    - frontend/src/components/FutureDateBanner.module.css
  modified:
    - frontend/src/components/EmptyState.tsx
    - frontend/src/components/GameCard.tsx
    - frontend/src/components/GameCard.module.css
    - frontend/src/components/GameCardGrid.tsx
    - frontend/src/App.tsx

key-decisions:
  - "Empty future/tomorrow dates show EmptyState (not FutureDateBanner) for consistency with zero-game states"
  - "Removed unused isStale prop from GameCard to eliminate TS6133 warning"

patterns-established:
  - "ViewMode prop threading: App -> GameCardGrid -> GameCard for context-dependent rendering"
  - "FutureDateBanner only renders when games.length > 0; EmptyState handles zero-game case for all modes"

requirements-completed: [DATE-01, DATE-02, DATE-03, DATE-05, DATE-07, DATE-08]

# Metrics
duration: 5min
completed: 2026-03-31
---

# Phase 14 Plan 03: Future/Tomorrow Rendering Summary

**FutureDateBanner, date-aware EmptyState, PRELIMINARY badge, and future-mode GameCard rendering across all view modes**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-31T17:55:00Z
- **Completed:** 2026-03-31T18:20:00Z
- **Tasks:** 2 (1 auto + 1 checkpoint)
- **Files modified:** 7

## Accomplishments
- FutureDateBanner renders contextual copy for tomorrow ("Tomorrow's Matchups" with PRELIMINARY explanation) and future ("Upcoming Schedule") dates
- EmptyState now shows four distinct messages based on viewMode: live, historical, tomorrow, and future
- GameCard displays amber PRELIMINARY badge when prediction_label is set, hides prediction body and Kalshi section in future mode, and shows schedule pitcher names from probable_pitcher fields
- Complete date navigation system visually verified and approved by user across all modes (past, today, tomorrow, future, empty)

## Task Commits

Each task was committed atomically:

1. **Task 1: FutureDateBanner, EmptyState update, GameCard PRELIMINARY badge and future rendering** - `e1b9021` (feat)
   - Post-task fix: `60b00ee` - Removed unused isStale prop from GameCard (TS6133 cleanup)
   - Post-checkpoint fix: `96d163b` - Empty future dates show EmptyState instead of FutureDateBanner

2. **Task 2: Visual verification of complete date navigation system** - Human checkpoint, approved

**Plan metadata:** (this commit)

## Files Created/Modified
- `frontend/src/components/FutureDateBanner.tsx` - Banner component with tomorrow/future copy variants
- `frontend/src/components/FutureDateBanner.module.css` - Banner styling (centered card, 20px heading, 16px body)
- `frontend/src/components/EmptyState.tsx` - Refactored with viewMode and selectedDate props for date-aware copy
- `frontend/src/components/GameCard.tsx` - Added viewMode prop, PRELIMINARY badge, future-mode header-only rendering, schedule pitcher names
- `frontend/src/components/GameCard.module.css` - Added .preliminaryBadge class (amber color scheme matching POSTPONED)
- `frontend/src/components/GameCardGrid.tsx` - Passes viewMode through to GameCard
- `frontend/src/App.tsx` - Integrates FutureDateBanner, passes viewMode to EmptyState and GameCardGrid

## Decisions Made
- **Empty future dates show EmptyState, not FutureDateBanner:** When games.length === 0 on a future/tomorrow date, the EmptyState component (with future-specific copy) renders instead of FutureDateBanner. This avoids showing a "schedule preview" banner when there is no schedule to preview. Discovered during post-checkpoint testing and fixed in `96d163b`.
- **Removed unused isStale prop from GameCard:** The GameCard component declared isStale in its props interface but never used it. Removed to fix TS6133 warning and keep the API clean. Fixed in `60b00ee`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unused isStale prop causing TS6133 warning**
- **Found during:** Task 1 verification (post-commit)
- **Issue:** GameCard declared `isStale: boolean` in props but never referenced it, causing TypeScript TS6133 unused variable warning
- **Fix:** Removed isStale from GameCardProps interface and from GameCardGrid's GameCard call site
- **Files modified:** frontend/src/components/GameCard.tsx, frontend/src/components/GameCardGrid.tsx
- **Verification:** `npx tsc --noEmit` exits 0
- **Committed in:** `60b00ee`

**2. [Rule 1 - Bug] Empty future dates showed FutureDateBanner instead of EmptyState**
- **Found during:** Post-checkpoint visual testing
- **Issue:** When navigating to a future date with no games, FutureDateBanner rendered (saying "Upcoming Schedule") even though there were no games to show. The correct behavior is EmptyState with future-specific copy.
- **Fix:** Changed conditional in App.tsx so that FutureDateBanner only renders when games.length > 0; empty future/tomorrow dates fall through to EmptyState
- **Files modified:** frontend/src/App.tsx
- **Verification:** Visual inspection confirmed; TypeScript compiles cleanly
- **Committed in:** `96d163b`

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both fixes improved correctness. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations above.

## User Setup Required
None - no external service configuration required.

## Pre-existing Test Failures (Out of Scope)
Three pre-existing test failures were observed during verification, all unrelated to Phase 14:
- `tests/test_feature_builder.py::test_rolling_ops` - Rolling OPS NaN assertion (feature builder, pre-Phase 14)
- `tests/test_leakage.py::test_shift1_prevents_current_game_leakage` - Same rolling OPS NaN imputation issue
- `tests/test_pipeline/test_live_features.py::test_live_feature_builder_season_and_date` - Season list assertion (live features, pre-Phase 14)

All API tests (43 tests) and TypeScript compilation pass cleanly.

## Next Phase Readiness
- Phase 14 is fully complete: all 3 plans delivered (backend API, DateNavigator, future/tomorrow rendering)
- Date navigation system approved visually by user
- Ready for Phase 15 (Live Score Polling) which depends on Phase 13 and Phase 14

## Self-Check: PASSED

- All 8 claimed files: FOUND
- All 3 claimed commits (e1b9021, 60b00ee, 96d163b): FOUND
- TypeScript compilation: exits 0
- API tests (43): all pass

---
*Phase: 14-date-navigation*
*Completed: 2026-03-31*
