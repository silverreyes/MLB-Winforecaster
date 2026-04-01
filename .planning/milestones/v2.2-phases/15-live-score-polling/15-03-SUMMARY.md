---
phase: 15-live-score-polling
plan: 03
subsystem: ui
tags: [react, typescript, css-modules, svg, live-scores, polling]

# Dependency graph
requires:
  - phase: 15-01
    provides: LiveScoreData Pydantic model and live_score field in API GameResponse
provides:
  - LiveScoreData TypeScript interface and live_score field on frontend GameResponse
  - 90s dual-gate polling (viewMode=live AND hasLiveGames) in useGames hook
  - ScoreRow with expand/collapse on LIVE cards only
  - BasesDiamond inline SVG component with amber fill for occupied bases
  - LiveDetail expanded section with bases diamond, count, batter info, on-deck batter
affects: [15-04, 16-live-score-polling]

# Tech tracking
tech-stack:
  added: []
  patterns: [inline-svg-component, useState-expand-collapse, dual-gate-polling, conditional-render-for-status-gating]

key-files:
  created:
    - frontend/src/components/BasesDiamond.tsx
    - frontend/src/components/LiveDetail.tsx
    - frontend/src/components/LiveDetail.module.css
  modified:
    - frontend/src/api/types.ts
    - frontend/src/hooks/useGames.ts
    - frontend/src/components/GameCard.tsx
    - frontend/src/components/GameCard.module.css

key-decisions:
  - "Always singular 'out' (not 'outs') per UI-SPEC copywriting contract"
  - "useState for expand/collapse per UI-SPEC lock (not details/summary)"
  - "ScoreRow conditional render on game_status === LIVE gates expand affordance to LIVE cards only"

patterns-established:
  - "Inline SVG component pattern: BasesDiamond takes boolean props, renders SVG with conditional fill"
  - "Dual-gate polling: refetchInterval checks viewMode AND game status before enabling"
  - "Expand/collapse via conditional render: useState + game_status guard implicitly clears on status transition"

requirements-completed: [LIVE-01, LIVE-02, LIVE-03, LIVE-04, LIVE-05, LIVE-06, LIVE-07]

# Metrics
duration: 3min
completed: 2026-03-31
---

# Phase 15 Plan 03: Frontend Live Score Display Summary

**Live score ScoreRow with expand/collapse, BasesDiamond SVG, LiveDetail batter info, and 90s dual-gate polling on LIVE cards only**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-31T22:27:58Z
- **Completed:** 2026-03-31T22:30:50Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- LiveScoreData TypeScript interface with 14 fields matching Python model, added to GameResponse
- useGames polling upgraded from 60s-always-live to 90s dual-gate (today selected AND live games exist)
- ScoreRow renders between headerRow and predictionBody for LIVE games only with amber-tinted background
- BasesDiamond inline SVG with amber fill for occupied bases and accessible aria-label
- LiveDetail expanded section with bases diamond, pitch count, current batter with AVG/OPS, on-deck batter
- Full keyboard accessibility (role="button", tabIndex, Enter/Space handlers, aria-expanded)
- Production build succeeds with zero TypeScript errors

## Task Commits

Each task was committed atomically:

1. **Task 1: TypeScript types + useGames polling gate update** - `6b59381` (feat)
2. **Task 2: ScoreRow, LiveDetail, BasesDiamond components + GameCard integration** - `c537aac` (feat)

## Files Created/Modified
- `frontend/src/api/types.ts` - Added LiveScoreData interface and live_score field to GameResponse
- `frontend/src/hooks/useGames.ts` - Updated refetchInterval to 90s dual-gate polling
- `frontend/src/components/BasesDiamond.tsx` - NEW: Inline SVG bases diamond with boolean runner props
- `frontend/src/components/LiveDetail.tsx` - NEW: Expanded detail with diamond, count, batter info
- `frontend/src/components/LiveDetail.module.css` - NEW: Expanded detail section styles
- `frontend/src/components/GameCard.tsx` - Added ScoreRow, expand state, LiveDetail integration
- `frontend/src/components/GameCard.module.css` - Added scoreRow, scoreText, expandChevron styles

## Decisions Made
- Used always-singular "out" (not "outs") per UI-SPEC copywriting contract -- plan code had conditional plural but spec explicitly says "0 out", "1 out", "2 out"
- Used useState for expand/collapse per UI-SPEC lock -- not details/summary -- because LIVE-to-FINAL transition must implicitly clear expand state via conditional render

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed outs pluralization to match UI-SPEC**
- **Found during:** Task 2 (ScoreRow implementation)
- **Issue:** Plan code used `outs === 1 ? 'out' : 'outs'` but UI-SPEC line 241 explicitly says "always singular 'out' (not 'outs')"
- **Fix:** Changed to always use singular "out" as specified in UI-SPEC
- **Files modified:** frontend/src/components/GameCard.tsx
- **Verification:** Visual inspection of code confirms singular "out"
- **Committed in:** c537aac (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor copywriting correction to match authoritative UI-SPEC. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Frontend live score display complete and ready for end-to-end testing with Plan 15-04 (integration verification)
- All LIVE-01 through LIVE-07 frontend requirements implemented
- Backend live score data (Plan 15-01 and 15-02) already provides the data this frontend consumes

## Self-Check: PASSED

All 7 files verified present. Both task commits (6b59381, c537aac) verified in git log.

---
*Phase: 15-live-score-polling*
*Completed: 2026-03-31*
