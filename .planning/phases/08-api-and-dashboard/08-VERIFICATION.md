---
phase: 08-api-and-dashboard
verified: 2026-03-29T00:00:00Z
status: passed
score: 21/21 must-haves verified
re_verification: false
---

# Phase 08: API and Dashboard Verification Report

**Phase Goal:** Users visit mlbforecaster.silverreyes.net and see today's MLB game predictions with model probabilities, Kalshi edge signals, and SP confirmation status -- updated automatically via client-side polling
**Verified:** 2026-03-29
**Status:** PASSED
**Re-verification:** No -- initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | GET /api/v1/predictions/today returns all games with both versions, model probs, Kalshi, edge, SP, ensemble_prob, timestamps | VERIFIED | `api/routes/predictions.py` L92-96: sync def handler, CURRENT_DATE query, `_build_prediction()` computes ensemble_prob and edge_magnitude |
| 2 | GET /api/v1/predictions/{date} returns same shape for historical date | VERIFIED | L118-128: identical logic via shared `_fetch_predictions()` with date param, format validation |
| 3 | GET /api/v1/predictions/latest-timestamp returns most recent created_at for polling | VERIFIED | L100-115: `SELECT MAX(created_at)` query, `/latest-timestamp` route registered BEFORE `/{date}` route (ordering comment present) |
| 4 | GET /api/v1/results/accuracy returns Brier scores from model_metadata.json | VERIFIED | `api/routes/accuracy.py`: reads file via `json.load()`, returns `AccuracyResponse` with models dict and training_date |
| 5 | GET /api/v1/health returns pipeline status per version with last run timestamps | VERIFIED | `api/routes/health.py`: calls `get_health_data(pool)` from `src.pipeline.health`, returns `HealthResponse(**health_data)` |
| 6 | API fails to start if any of the 6 model artifacts is missing | VERIFIED | `api/main.py` L25: `load_all_artifacts()` called in lifespan before yield; test_lifespan.py `test_missing_artifact_fails` asserts FileNotFoundError |
| 7 | Frontend builds successfully producing frontend/dist/ | VERIFIED | `npm run build` exits 0, dist/index.html + dist/assets/ produced (91 modules, 233KB JS) |
| 8 | Game cards display ensemble average as hero probability in DM Mono 32px amber | VERIFIED | `PredictionColumn.tsx` renders `formatProb(ensemble_prob)`; `PredictionColumn.module.css`: `font-size: 32px`, `font-family: var(--font-data)`, `color: var(--color-accent)` |
| 9 | Individual model breakdown (LR / RF / XGB) always visible below hero number | VERIFIED | `PredictionColumn.tsx` L24-37: unconditional `modelRows` div with LR/RF/XGB model rows |
| 10 | Post-lineup takes primary (left) position when both versions exist; pre-lineup shown muted on right | VERIFIED | `GameCard.tsx` L62-75: `hasBothVersions` path renders post_lineup with `isPrimary=true` left, pre_lineup with `isPrimary=false` right; `PredictionColumn.module.css` `.muted { opacity: 0.55 }` |
| 11 | When only pre-lineup exists, it occupies full card width with TEAM ONLY label | VERIFIED | `GameCard.tsx` L77-82: `pre_lineup` single-version path passes `label="TEAM ONLY"` and `isPrimary={true}` |
| 12 | Kalshi price always shown on every card; edge badge shown only when edge exists; NO_EDGE suppressed | VERIFIED | `KalshiSection.tsx`: price always formatted as `{Math.round(price * 100)}c` or `--`; `showEdge` only true when `edgeSignal === 'BUY_YES' \|\| edgeSignal === 'BUY_NO'` |
| 13 | SP TBD shown as amber badge; sp_may_have_changed shown as amber warning strip across card top | VERIFIED | `SpBadge.tsx`: `SP: TBD` with `color-accent-muted` + `rgba(217, 119, 6, 0.15)` background; `GameCard.tsx` L27-30: warning strip with same amber bg and "SP assignment may have changed" text |
| 14 | Skeleton cards display during loading state with pulse animation | VERIFIED | `SkeletonCard.module.css`: `@keyframes pulse` oscillating opacity 0.3 to 0.6 over 1.5s; `App.tsx` renders 6 SkeletonCards when `isLoading && !data` |
| 15 | Client-side polling fires every 60 seconds when document is visible | VERIFIED | `useLatestTimestamp.ts`: `refetchInterval: 60_000`, `refetchIntervalInBackground: false` (TanStack Query natively pauses when tab is hidden) |
| 16 | Polling suspends when tab is hidden and resumes when visible | VERIFIED | `useLatestTimestamp.ts` L10: `refetchIntervalInBackground: false` -- TanStack Query v5 halts refetchInterval when document.visibilityState is hidden |
| 17 | New predictions available banner appears when polled timestamp is newer than displayed data | VERIFIED | `App.tsx` L29-33: `hasNewPredictions` compares `timestampData.timestamp > displayedTimestamp`; `NewPredictionsBanner.tsx` renders when `visible={hasNewPredictions}` |
| 18 | Clicking the banner triggers a data refetch, not a browser reload | VERIFIED | `NewPredictionsBanner.tsx` L14: `onClick={onRefresh}`; `App.tsx` L47-49: `handleRefresh = () => refetch()` (React Query refetch, not `window.location.reload()`) |
| 19 | Prediction cards are grayed out (opacity 0.45) when data is older than 3 hours | VERIFIED | `App.tsx` L13: `STALE_THRESHOLD_MS = 3 * 60 * 60 * 1000`; `GameCardGrid.module.css` `.stale { opacity: 0.45 }`; `isStale` passed through to grid |
| 20 | Staleness indicator text replaces normal Last updated text | VERIFIED | `Header.tsx` L31-34: when `isStale`, renders `staleTimestamp` span ("Data may be stale -- last updated ..."); `Header.module.css`: `.staleTimestamp { color: var(--color-stale) }` (6B7280) vs `.timestamp { color: var(--color-accent) }` |
| 21 | When API is unreachable, explicit error state shown -- not a blank page | VERIFIED | `App.tsx` L70-71: `isError && !data` renders `<ErrorState>`; `ErrorState.tsx` "Dashboard offline" heading + "Unable to reach the predictions API" body; cached data path shows offline badge in Header |

**Score:** 21/21 truths verified

---

## Required Artifacts

### Plan 01 (API Backend)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `api/main.py` | FastAPI app with lifespan, CORS, router includes, SPA mount | VERIFIED | 51 lines; lifespan loads artifacts + pool; 3 routers included at `/api/v1`; SPAStaticFiles conditionally mounted |
| `api/models.py` | Pydantic response models for all endpoints | VERIFIED | 62 lines; PredictionResponse (18 fields), TodayResponse, LatestTimestampResponse, AccuracyResponse, HealthResponse all present |
| `api/routes/predictions.py` | API-01, API-02, API-03 route handlers | VERIFIED | 129 lines; all 3 routes implemented; ensemble_prob and edge_magnitude computed via `_build_prediction()`; route ordering enforced with comment |
| `api/routes/accuracy.py` | API-04 route handler | VERIFIED | 32 lines; reads model_metadata.json, returns AccuracyResponse, returns 404 on FileNotFoundError |
| `api/routes/health.py` | API-05 route handler | VERIFIED | 21 lines; delegates to `get_health_data(pool)` |
| `api/spa.py` | SPAStaticFiles subclass | VERIFIED | 21 lines; extends StaticFiles; `get_response` falls back to index.html |
| `tests/test_api/conftest.py` | TestClient fixture with mocked DB pool and artifacts | VERIFIED | 47 lines; patches `api.main.load_all_artifacts` and `api.main.get_pool` |

### Plan 02 (React Frontend)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `frontend/package.json` | React 19 + Vite 8 + TanStack React Query project | VERIFIED | `"react": "^19.2.4"`, `"@tanstack/react-query": "^5.95.2"`, `"vite": "^8.0.1"` |
| `frontend/src/index.css` | CSS custom properties matching UI-SPEC tokens | VERIFIED | All 10 color tokens, 6 spacing tokens, 2 font stacks, 3 @font-face declarations |
| `frontend/src/api/types.ts` | TypeScript interfaces matching API response models | VERIFIED | PredictionResponse (18 fields), TodayResponse, LatestTimestampResponse, GameGroup all exported |
| `frontend/src/components/GameCard.tsx` | Primary game card component | VERIFIED | 106 lines; renders PredictionColumn and KalshiSection; two-column and single-column layout; SP warning strip |
| `frontend/vite.config.ts` | Vite config with /api proxy to localhost:8000 | VERIFIED | Proxy `/api` -> `http://localhost:8000` with `changeOrigin: true` |

### Plan 03 (Interactive Behaviors)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `frontend/src/components/NewPredictionsBanner.tsx` | Amber banner with Load latest predictions CTA | VERIFIED | 19 lines; `visible` guard; `onRefresh()` on click; not `window.location.reload()` |
| `frontend/src/components/ErrorState.tsx` | Dashboard offline error state | VERIFIED | 28 lines; "Dashboard offline" heading; conditional timestamp display; `lastSuccessfulTimestamp` prop used |

---

## Key Link Verification

### Plan 01 Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `api/main.py` | `src/pipeline/db.get_pool` | lifespan context manager | WIRED | L26: `get_pool(min_size=2, max_size=5)` inside lifespan, stored on `app.state.pool` |
| `api/main.py` | `src/pipeline/inference.load_all_artifacts` | lifespan loads artifacts | WIRED | L25: `load_all_artifacts()` called before `yield`, raises FileNotFoundError if missing |
| `api/routes/predictions.py` | `request.app.state.pool` | sync def handler accesses pool from app state | WIRED | L95: `pool = request.app.state.pool` in get_today_predictions |
| `api/routes/health.py` | `src/pipeline/health.get_health_data` | direct import and call with pool | WIRED | L10: `from src.pipeline.health import get_health_data`; L19: `get_health_data(pool)` |

### Plan 02 Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `frontend/src/hooks/usePredictions.ts` | `/api/v1/predictions/today` | React Query useQuery with fetch | WIRED | L34: `fetchJson<TodayResponse>('/predictions/today')` inside `queryFn` |
| `frontend/src/App.tsx` | `frontend/src/hooks/usePredictions.ts` | hook import and call | WIRED | L2 import + L17: `const { data, isLoading, isError, games, refetch } = usePredictions()` |
| `frontend/src/components/GameCard.tsx` | `frontend/src/components/PredictionColumn.tsx` | component composition | WIRED | L2 import + L63/66/78/85: `<PredictionColumn` rendered in all code paths |

### Plan 03 Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `frontend/src/App.tsx` | `frontend/src/hooks/useLatestTimestamp.ts` | hook call with timestamp comparison | WIRED | L3 import + L18: `const { data: timestampData } = useLatestTimestamp()` |
| `frontend/src/App.tsx` | `frontend/src/components/NewPredictionsBanner.tsx` | conditional render when hasNewPredictions | WIRED | L6 import + L59-62: `<NewPredictionsBanner visible={hasNewPredictions} onRefresh={handleRefresh} />` |
| `frontend/src/App.tsx` | `frontend/src/components/ErrorState.tsx` | conditional render when isError and no cached data | WIRED | L10 import + L71: `<ErrorState lastSuccessfulTimestamp={lastSuccessTimestamp} />` |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| API-01 | 08-01 | GET /api/v1/predictions/today | SATISFIED | `predictions.py` L92-96: route exists, queries CURRENT_DATE with is_latest=TRUE, computes ensemble_prob |
| API-02 | 08-01 | GET /api/v1/predictions/{date} | SATISFIED | `predictions.py` L118-128: same shape via shared `_fetch_predictions()`, date format validated |
| API-03 | 08-01 | GET /api/v1/predictions/latest-timestamp | SATISFIED | `predictions.py` L100-115: MAX(created_at) query; route registered BEFORE /{date} (ordering comment at L99) |
| API-04 | 08-01 | GET /api/v1/results/accuracy | SATISFIED | `accuracy.py`: reads model_metadata.json, returns 6-model Brier scores, 404 on missing file |
| API-05 | 08-01 | GET /api/v1/health | SATISFIED | `health.py`: delegates to `get_health_data(pool)` from src.pipeline.health |
| API-06 | 08-01 | API fails to start if any artifact missing | SATISFIED | `main.py` L25: `load_all_artifacts()` in lifespan raises FileNotFoundError; `test_lifespan.py` `test_missing_artifact_fails` asserts this behavior |
| DASH-01 | 08-02 | React 19 + Vite 8 dashboard with dark cinematic + amber aesthetic | SATISFIED | `package.json`: React 19.2.4, Vite 8.0.1; `index.css`: `--color-bg: #0A0A0F`, `--color-accent: #F59E0B`; build produces `frontend/dist/` |
| DASH-02 | 08-02 | Pre/post-lineup side-by-side; LR/RF/XGB per version; confirmed vs TBD visual distinction | SATISFIED | `GameCard.tsx`: two-column layout for both versions; `PredictionColumn.tsx`: always shows LR/RF/XGB breakdown; `SpBadge.tsx`: TBD amber vs confirmed normal |
| DASH-03 | 08-02 | Kalshi live price and edge signal (BUY_YES/BUY_NO/NO_EDGE) per game | SATISFIED | `KalshiSection.tsx`: price formatted as cents; EdgeBadge renders only for BUY_YES/BUY_NO; NO_EDGE suppressed |
| DASH-04 | 08-02 | SP confirmation status -- confirmed name shown, TBD flagged, sp_may_have_changed warning | SATISFIED | `SpBadge.tsx`: confirmed shows name, TBD shows amber badge; `GameCard.tsx` L17-30: sp_may_have_changed amber strip |
| DASH-05 | 08-03 | Last updated timestamp prominent; cards grayed when data > 3 hours old | SATISFIED | `App.tsx` L13+24-26: 3-hour threshold; `GameCardGrid.module.css` `.stale { opacity: 0.45 }`; `Header.tsx`: stale text in #6B7280 |
| DASH-06 | 08-03 | Client-side polling every 60s when visible, suspended when hidden, new predictions banner | SATISFIED | `useLatestTimestamp.ts`: `refetchInterval: 60_000`, `refetchIntervalInBackground: false`; `App.tsx`: hasNewPredictions detection + NewPredictionsBanner |
| DASH-07 | 08-03 | Explicit error state -- not blank page or infinite spinner; last-known data + Dashboard offline indicator | SATISFIED | `App.tsx` L70-71: ErrorState rendered when isError+!data; `ErrorState.tsx`: "Dashboard offline" heading + timestamp; offline badge in Header |

All 13 requirements verified. No orphaned requirements found. REQUIREMENTS.md marks all 13 as Phase 8, Complete.

---

## Anti-Patterns Found

None. Full scan of `api/` and `frontend/src/` for TODO, FIXME, PLACEHOLDER, `return null` stubs in handlers, and `window.location.reload()` calls produced zero results.

---

## Human Verification Required

### 1. End-to-End Visual Inspection

**Test:** Start `uvicorn api.main:app --reload --port 8000` and `npm run dev` in `frontend/`, open http://localhost:5173
**Expected:** Dark near-black background, amber probabilities in DM Mono, game cards with team matchup header, LR/RF/XGB breakdown below hero number, Kalshi section at card bottom
**Why human:** Visual aesthetics, font rendering, card layout proportions, and dark/amber contrast cannot be verified programmatically

### 2. Polling Behavior in Browser

**Test:** Open browser Network tab, filter XHR. Wait 60+ seconds on http://localhost:5173
**Expected:** `/api/v1/predictions/latest-timestamp` fires approximately every 60 seconds; switching to another tab stops the requests; switching back resumes within 60 seconds
**Why human:** Browser event loop timing and `visibilityState` behavior require live browser observation

### 3. New Predictions Banner Flow

**Test:** With API running and predictions loaded, trigger a new prediction insertion in DB. Wait for next poll cycle.
**Expected:** Amber banner "New predictions available" appears. Clicking "Load latest predictions" refetches data without browser reload (Network tab shows a new `/predictions/today` request)
**Why human:** Requires live DB manipulation and observation of conditional banner render timing

---

## Gaps Summary

None. All 21 observable truths are verified. All 13 requirement IDs (API-01 through API-06, DASH-01 through DASH-07) are satisfied with direct evidence in code. All 6 commits documented in summaries exist in the git log (`fd9f9d5`, `426cf67`, `66b14de`, `86d5cc0`, `fc9c95b`, `d3165be`). API test suite passes (11/11). Frontend build succeeds (`vite v8.0.3`, 0 TypeScript errors, 91 modules). `frontend/dist/` exists and is ready for SPA serving by the FastAPI `SPAStaticFiles` mount.

The three human verification items are observational confirmations only -- all underlying logic is present and wired.

---

_Verified: 2026-03-29_
_Verifier: Claude (gsd-verifier)_
