---
phase: 08-api-and-dashboard
plan: 03
subsystem: ui
tags: [react, typescript, polling, staleness, error-handling, css-modules, visibility-api]

# Dependency graph
requires:
  - phase: 08-api-and-dashboard
    plan: 01
    provides: "FastAPI backend with 5 API endpoints including /latest-timestamp"
  - phase: 08-api-and-dashboard
    plan: 02
    provides: "React 19 frontend scaffold with hooks (useLatestTimestamp, usePredictions), 12 UI components"
provides:
  - "NewPredictionsBanner component with amber CTA triggering React Query refetch (not page reload)"
  - "ErrorState component showing 'Dashboard offline' with last-known timestamp"
  - "Visibility-aware 60s polling via TanStack React Query refetchIntervalInBackground: false"
  - "3-hour staleness detection with opacity overlay and stale gray timestamp text"
  - "Header offline badge (red indicator) when API is unreachable"
  - "App.tsx interactive wiring: polling, staleness, new-predictions detection, error state cascade"
affects: [09-infrastructure]

# Tech tracking
tech-stack:
  added: []
  patterns: [visibility-aware-polling, staleness-threshold-check, error-state-cascade, cached-data-fallback]

key-files:
  created:
    - frontend/src/components/NewPredictionsBanner.tsx
    - frontend/src/components/NewPredictionsBanner.module.css
    - frontend/src/components/ErrorState.tsx
    - frontend/src/components/ErrorState.module.css
    - frontend/src/App.module.css
  modified:
    - frontend/src/App.tsx

key-decisions:
  - "No additional visibilitychange listener needed -- TanStack React Query refetchIntervalInBackground: false already handles pause/resume"
  - "Error state with cached data shows grayed cards + offline badge rather than replacing with full ErrorState component"
  - "No retry button in ErrorState -- React Query auto-recovers when API responds again"

patterns-established:
  - "Staleness pattern: compare Date.now() to displayed timestamp with 3-hour threshold constant"
  - "New predictions detection: poll timestamp vs displayed timestamp comparison, banner CTA triggers refetch()"
  - "Error cascade: isError + no data = ErrorState; isError + cached data = offline badge + stale overlay"

requirements-completed: [DASH-05, DASH-06, DASH-07]

# Metrics
duration: 8min
completed: 2026-03-30
---

# Phase 8 Plan 3: Interactive Behaviors Summary

**Visibility-aware polling with new-predictions banner, 3-hour staleness overlay, and Dashboard offline error state completing the live dashboard UX**

## Performance

- **Duration:** 8 min
- **Tasks:** 2 (1 auto + 1 checkpoint)
- **Files created:** 5
- **Files modified:** 1

## Accomplishments
- Wired all three interactive behaviors that transform the static dashboard into a live, resilient application
- NewPredictionsBanner component with amber CTA triggers React Query refetch (DASH-06) -- never window.location.reload
- 3-hour staleness threshold grays out prediction cards at opacity 0.45 with stale timestamp text in #6B7280 (DASH-05)
- ErrorState component shows "Dashboard offline" with last-known timestamp; cached data persists with offline badge (DASH-07)
- Skeleton loading grid mirrors GameCardGrid layout so loading cards occupy correct positions
- Visual verification checkpoint approved by human reviewer

## Task Commits

Each task was committed atomically:

1. **Task 1: NewPredictionsBanner, ErrorState components, and App.tsx interactive wiring** - `d3165be` (feat)
2. **Task 2: Visual verification of complete dashboard** - checkpoint:human-verify (approved)

## Files Created/Modified
- `frontend/src/components/NewPredictionsBanner.tsx` - Amber banner with "Load latest predictions" CTA button
- `frontend/src/components/NewPredictionsBanner.module.css` - Banner styles with rgba(217,119,6,0.15) background, 44px min-height touch target
- `frontend/src/components/ErrorState.tsx` - "Dashboard offline" error state with last-known timestamp display
- `frontend/src/components/ErrorState.module.css` - Centered 480px card with #12121A background
- `frontend/src/App.module.css` - Skeleton grid matching GameCardGrid layout
- `frontend/src/App.tsx` - Full interactive wiring: staleness check, new-predictions detection, error cascade, handleRefresh via refetch()

## Decisions Made
- No additional visibilitychange listener needed -- TanStack React Query's `refetchIntervalInBackground: false` already handles visibility-aware polling pause/resume
- Error state with cached data shows grayed cards with offline badge rather than replacing the entire view with ErrorState component
- No retry button in ErrorState component -- React Query continues polling automatically and recovers when API responds

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 8 (API and Dashboard) is now complete: FastAPI backend (08-01), React frontend (08-02), and interactive behaviors (08-03) are all built and verified
- Ready for Phase 9: Infrastructure and Go-Live (Docker Compose, Nginx SSL, Postgres backups, portfolio page)
- All components validated locally; deployment to Hostinger KVM 2 VPS can proceed

## Self-Check: PASSED

- All 6 files verified on disk (5 created, 1 modified)
- Commit d3165be verified in git log

---
*Phase: 08-api-and-dashboard*
*Plan: 03*
*Completed: 2026-03-30*
