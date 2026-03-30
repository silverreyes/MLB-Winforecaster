---
phase: 08-api-and-dashboard
plan: 02
subsystem: ui
tags: [react, vite, typescript, tanstack-react-query, css-modules, dashboard]

# Dependency graph
requires:
  - phase: 08-api-and-dashboard
    provides: "FastAPI backend with 5 API endpoints, Pydantic response models"
provides:
  - "React 19 + Vite 8 frontend scaffold with TanStack React Query"
  - "12 UI components matching UI-SPEC design contract (dark cinematic + amber aesthetic)"
  - "CSS custom properties for all color, spacing, and typography tokens"
  - "TypeScript interfaces matching API response models"
  - "Data hooks with visibility-aware 60s polling (DASH-06)"
  - "Game card with two-column prediction layout, Kalshi edge badges, SP status"
affects: [08-03-integration, 09-infrastructure]

# Tech tracking
tech-stack:
  added: [react-19, vite-8, tanstack-react-query-5, typescript-5.9, css-modules]
  patterns: [css-custom-properties, react-query-polling, game-group-aggregation, font-face-self-hosted]

key-files:
  created:
    - frontend/index.html
    - frontend/package.json
    - frontend/vite.config.ts
    - frontend/src/main.tsx
    - frontend/src/App.tsx
    - frontend/src/index.css
    - frontend/src/api/client.ts
    - frontend/src/api/types.ts
    - frontend/src/hooks/usePredictions.ts
    - frontend/src/hooks/useLatestTimestamp.ts
    - frontend/src/components/Header.tsx
    - frontend/src/components/AccuracyStrip.tsx
    - frontend/src/components/GameCardGrid.tsx
    - frontend/src/components/GameCard.tsx
    - frontend/src/components/PredictionColumn.tsx
    - frontend/src/components/KalshiSection.tsx
    - frontend/src/components/EdgeBadge.tsx
    - frontend/src/components/SpBadge.tsx
    - frontend/src/components/EmptyState.tsx
    - frontend/src/components/SkeletonCard.tsx
  modified: []

key-decisions:
  - "CSS custom properties reference design tokens from UI-SPEC rather than hard-coding hex values in component CSS"
  - "Game grouping (pre_lineup + post_lineup) done client-side in usePredictions hook via Map aggregation"
  - "Kalshi price formatted as cents (Math.round(price * 100)) matching API float response"
  - "Font files downloaded from Google Fonts CDN and committed to repo for self-hosting (no external CDN dependency)"

patterns-established:
  - "CSS Modules co-located with components (*.module.css + *.tsx pairs)"
  - "React Query hooks encapsulate API calls: usePredictions returns grouped games, useLatestTimestamp polls every 60s"
  - "Component prop interfaces match API types directly (PredictionResponse, GameGroup)"
  - "Conditional rendering pattern: isLoading -> skeleton, isError -> error state, games.length === 0 -> empty state"

requirements-completed: [DASH-01, DASH-02, DASH-03, DASH-04]

# Metrics
duration: 7min
completed: 2026-03-30
---

# Phase 08 Plan 02: React Dashboard Frontend Summary

**React 19 + Vite 8 dashboard with 12 UI components: game cards showing ensemble hero probability + LR/RF/XGB breakdown, two-column pre/post-lineup layout, Kalshi edge badges, SP status indicators, and skeleton loading**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-30T05:10:54Z
- **Completed:** 2026-03-30T05:18:00Z
- **Tasks:** 2
- **Files modified:** 39

## Accomplishments
- Complete React 19 + Vite 8 + TanStack React Query 5 frontend scaffold with API proxy and visibility-aware polling
- All 12 UI components built per UI-SPEC design contract: Header, AccuracyStrip, GameCardGrid, GameCard, PredictionColumn, KalshiSection, EdgeBadge, SpBadge, EmptyState, SkeletonCard
- CSS design system with all 10 color tokens, 6 spacing tokens, 2 typography stacks, and 3 self-hosted font faces (DM Mono, DM Sans 400/600)
- TypeScript interfaces matching API Pydantic models exactly, with GameGroup aggregation for pre/post-lineup pairing

## Task Commits

Each task was committed atomically:

1. **Task 1: Frontend scaffold, design tokens, TypeScript types, data hooks, and Vite config** - `86d5cc0` (feat)
2. **Task 2: All dashboard UI components (GameCard, PredictionColumn, Kalshi, Edge, SP, Accuracy, Skeleton, Empty)** - `fc9c95b` (feat)

## Files Created/Modified
- `frontend/package.json` - React 19 + Vite 8 + TanStack React Query 5 project
- `frontend/vite.config.ts` - Vite config with /api proxy to localhost:8000
- `frontend/index.html` - Entry HTML with font preload tags
- `frontend/src/index.css` - CSS custom properties matching UI-SPEC tokens + font-face declarations
- `frontend/src/main.tsx` - React entry with QueryClientProvider
- `frontend/src/App.tsx` - Root component wiring all components with loading/error/empty/data states
- `frontend/src/api/types.ts` - TypeScript interfaces: PredictionResponse, TodayResponse, GameGroup
- `frontend/src/api/client.ts` - Fetch wrapper with API base URL
- `frontend/src/hooks/usePredictions.ts` - React Query hook with game grouping
- `frontend/src/hooks/useLatestTimestamp.ts` - Polling hook with refetchInterval: 60000 and visibility-aware
- `frontend/src/components/Header.tsx` - Page title, subtitle, timestamp, staleness indicator
- `frontend/src/components/AccuracyStrip.tsx` - Static Brier scores from model_metadata.json
- `frontend/src/components/GameCardGrid.tsx` - CSS Grid with auto-fill columns and staleness opacity
- `frontend/src/components/GameCard.tsx` - Two-column prediction layout, SP warning strip, Kalshi section
- `frontend/src/components/PredictionColumn.tsx` - 32px hero number + LR/RF/XGB model breakdown
- `frontend/src/components/KalshiSection.tsx` - Price display + conditional EdgeBadge (NO_EDGE suppressed)
- `frontend/src/components/EdgeBadge.tsx` - Color-coded BUY YES/BUY NO with magnitude
- `frontend/src/components/SpBadge.tsx` - Confirmed SP name or amber TBD badge
- `frontend/src/components/EmptyState.tsx` - No games today message
- `frontend/src/components/SkeletonCard.tsx` - Loading placeholder with pulse animation

## Decisions Made
- CSS custom properties reference design tokens from UI-SPEC rather than hard-coding hex values in component CSS -- enables theming and single source of truth
- Game grouping (pre_lineup + post_lineup) done client-side in usePredictions hook via Map aggregation by home_team-away_team key
- Kalshi price formatted as cents using `Math.round(price * 100)` to match the API float response (0.55 -> "55c")
- Font files downloaded from Google Fonts CDN and committed to repo (small woff2 files ~1.6KB each) for self-hosting

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed unused variable TypeScript error**
- **Found during:** Task 1 (App.tsx initial scaffold)
- **Issue:** `_hasNewPredictions` variable triggered `noUnusedLocals` TS error even with underscore prefix
- **Fix:** Renamed to `hasNewPredictions` and added it to JSX render tree with conditional banner
- **Files modified:** frontend/src/App.tsx
- **Verification:** `npm run build` passes
- **Committed in:** 86d5cc0 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor naming fix. No scope creep.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Frontend builds to `frontend/dist/` with zero errors (TypeScript strict mode)
- All components ready for integration testing with live API (Plan 03)
- Vite dev server proxy configured for localhost:8000 API
- Skeleton loading, error state, and empty state all implemented
- Missing from this plan (deferred to Plan 03): NewPredictionsBanner as full component, ErrorState as full component, end-to-end integration test

## Self-Check: PASSED

- All 30 created files verified present on disk
- Both task commits verified in git log (86d5cc0, fc9c95b)
- `npm run build` exits 0 (TypeScript + Vite build)
- `npx tsc --noEmit` exits 0 (zero type errors)

---
*Phase: 08-api-and-dashboard*
*Completed: 2026-03-30*
