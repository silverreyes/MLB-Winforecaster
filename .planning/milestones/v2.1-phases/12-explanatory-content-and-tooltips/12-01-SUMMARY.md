---
phase: 12-explanatory-content-and-tooltips
plan: 01
subsystem: ui
tags: [react, css-modules, details-summary, tooltip, accessibility]

# Dependency graph
requires:
  - phase: 09-kalshi-edge-signal
    provides: EdgeBadge component and KalshiSection rendering
provides:
  - Collapsible AboutModels explanatory section (model types, probability, calibration, PRE/POST-LINEUP, Kalshi)
  - Reusable Tooltip component with CSS hover/focus visibility
  - EdgeBadge (?) tooltip icons explaining contract mechanics
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Native <details>/<summary> for collapsible sections (zero JS state)"
    - "CSS-only tooltip with :hover/:focus-visible visibility toggle"

key-files:
  created:
    - frontend/src/components/AboutModels.tsx
    - frontend/src/components/AboutModels.module.css
    - frontend/src/components/Tooltip.tsx
    - frontend/src/components/Tooltip.module.css
  modified:
    - frontend/src/components/EdgeBadge.tsx
    - frontend/src/components/EdgeBadge.module.css
    - frontend/src/App.tsx

key-decisions:
  - "Used native <details>/<summary> over useState for collapse -- zero JS, built-in keyboard/screen reader support"
  - "CSS-only tooltip over library -- two static tooltips do not justify a dependency"

patterns-established:
  - "Collapsible sections: use <details>/<summary> with custom chevron, hide default marker via list-style:none + ::-webkit-details-marker"
  - "Tooltips: CSS visibility:hidden + opacity:0 with :hover/:focus-visible toggle; mobile breakpoint shifts anchor to right-aligned"

requirements-completed: [EXPLAIN-01, EXPLAIN-02, EXPLAIN-03, EXPLAIN-04, EXPLAIN-05, EXPLAIN-06, EXPLAIN-07, TLTP-01, TLTP-02]

# Metrics
duration: 2min
completed: 2026-03-30
---

# Phase 12 Plan 01: Explanatory Content and Tooltips Summary

**Collapsible "About the Models" section with model/probability/calibration/Kalshi explanations, plus (?) tooltip icons on EdgeBadge explaining contract mechanics**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-30T22:28:04Z
- **Completed:** 2026-03-30T22:30:11Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Collapsible "About the Models" section between AccuracyStrip and NewPredictionsBanner, defaults collapsed, explains LR/RF/XGBoost, probability interpretation, calibration, PRE/POST-LINEUP, and Kalshi mechanics with 7% fee disclosure
- Reusable Tooltip component with CSS hover/focus-visible visibility, keyboard accessible (tabIndex, aria-label), mobile-responsive positioning
- EdgeBadge (?) icons showing contract mechanics tooltips for Buy Yes and Buy No signals

## Task Commits

Each task was committed atomically:

1. **Task 1: Create AboutModels collapsible section and wire into App** - `1b8c41c` (feat)
2. **Task 2: Create Tooltip component and add (?) icons to EdgeBadge** - `2f1969b` (feat)

## Files Created/Modified
- `frontend/src/components/AboutModels.tsx` - Collapsible explanatory section using native details/summary
- `frontend/src/components/AboutModels.module.css` - Dark amber design system styles for collapsible section
- `frontend/src/components/Tooltip.tsx` - Reusable CSS tooltip wrapper with keyboard accessibility
- `frontend/src/components/Tooltip.module.css` - Tooltip positioning, visibility toggle, mobile breakpoint
- `frontend/src/components/EdgeBadge.tsx` - Added Tooltip import and (?) icons with contract mechanics text
- `frontend/src/components/EdgeBadge.module.css` - Added gap for tooltip icon spacing
- `frontend/src/App.tsx` - Imported and rendered AboutModels between AccuracyStrip and NewPredictionsBanner

## Decisions Made
- Used native `<details>`/`<summary>` over `useState` for collapse/expand -- zero JS overhead, built-in keyboard and screen reader support
- CSS-only tooltip over third-party library -- two static tooltips with short text do not justify adding a dependency

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 12 is the final phase of v2.1 milestone; this was the only plan in the phase
- All 9 requirements (EXPLAIN-01 through EXPLAIN-07, TLTP-01, TLTP-02) are addressed
- v2.1 Dashboard UX / Contextual Clarity milestone is complete

## Self-Check: PASSED

All 7 files verified present. Both task commits (1b8c41c, 2f1969b) verified in git log.

---
*Phase: 12-explanatory-content-and-tooltips*
*Completed: 2026-03-30*
