# Phase 8: API and Dashboard - Research

**Researched:** 2026-03-29
**Domain:** FastAPI REST API + React 19 SPA dashboard
**Confidence:** HIGH

## Summary

Phase 8 builds two interconnected deliverables: a FastAPI read-only API layer over the existing Postgres database (populated by Phase 7), and a React 19 + Vite 8 single-page dashboard that consumes it. The API is thin -- it queries the `predictions` and `pipeline_runs` tables and serves JSON. The frontend is a static SPA with no routing (today-only view), using TanStack React Query for data fetching and visibility-aware polling.

The existing `src/pipeline/db.py` uses **synchronous** psycopg3 (`ConnectionPool`, not `AsyncConnectionPool`). This is the correct choice: FastAPI runs sync `def` endpoints in a thread pool automatically, so the API can import and reuse the existing db module directly without any async conversion. Model artifacts are already loaded by `src/pipeline/inference.py::load_all_artifacts()` with a fail-hard pattern -- the API lifespan wraps this with a DB pool open/close.

**Primary recommendation:** Build a FastAPI app (`api/main.py`) that reuses the sync psycopg3 pool from `src/pipeline/db.py` with `def` (not `async def`) route handlers, loads model artifacts via the existing `load_all_artifacts()` at startup, and serves the Vite-built React SPA from `frontend/dist/` using a custom `SPAStaticFiles` mount. The React frontend uses TanStack React Query v5 with `refetchInterval: 60000` and `refetchIntervalInBackground: false` for DASH-06 polling.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Ensemble average** is the primary/hero probability displayed on each game card (LR + RF + XGBoost averaged)
- Individual model breakdown (LR / RF / XGB) is **always visible below the hero number** -- no expand/toggle, no tooltip
- **Post-lineup is primary**: when both versions exist, post-lineup takes the left/main slot; pre-lineup shown smaller as reference
- When no post-lineup prediction exists yet: show team-only ensemble at full opacity with **amber "SP: TBD" badge** -- cards NOT grayed out
- **Kalshi price always shown**; edge badge (BUY_YES / BUY_NO) shown only when edge exists; NO_EDGE suppressed
- Edge badge format: color-coded badge + edge magnitude (e.g., green "BUY YES +8.3pts")
- `sp_may_have_changed` surfaced as **amber warning banner across card top**
- **Today-only dashboard** -- no date picker, no prev/next navigation in UI
- `GET /api/v1/predictions/{date}` available for direct API access but not exposed in frontend
- **Static accuracy summary strip** showing Brier scores, pre-rendered from `model_metadata.json` -- NOT a live API-04 call
- **`frontend/` directory in this repo** -- React app alongside `src/`, single git history
- `.gitignore` updated: `frontend/node_modules/`, `frontend/dist/`, `frontend/.env.local`
- **Local dev**: Vite dev server proxied to localhost:8000; run FastAPI and Vite separately
- **Production**: FastAPI mounts `frontend/dist/` as StaticFiles at root route
- **Greenfield FastAPI app**: `api/main.py` entry point importing from `src/pipeline/`

### Claude's Discretion
- Exact placement and sizing of accuracy metrics strip within dark/amber design
- React component file structure within `frontend/src/`
- Data fetching library: React Query preferred (visibility-aware polling aligns with `refetchIntervalInBackground: false`)
- Error boundary vs manual error state component for DASH-07
- Postgres connection pool library: psycopg3 sync pool (already in use) vs asyncpg -- **recommendation: keep sync psycopg3**

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| API-01 | `GET /api/v1/predictions/today` -- all games for current date with both versions, model probs, Kalshi, edge, SP names, staleness | DB query pattern against `predictions` table with `is_latest=TRUE` filter; sync psycopg3 pool; Pydantic response model |
| API-02 | `GET /api/v1/predictions/{date}` -- same shape, historical date | Same query pattern with date parameter; not exposed in frontend |
| API-03 | `GET /api/v1/predictions/latest-timestamp` -- lightweight timestamp endpoint for polling | Single `SELECT MAX(created_at)` query; minimal response model |
| API-04 | `GET /api/v1/results/accuracy` -- Brier scores by date range | Query aggregation from predictions + games tables; not used by frontend (static strip instead) |
| API-05 | `GET /api/v1/health` -- pipeline status per version | Existing `get_health_data(pool)` from `src/pipeline/health.py` maps directly |
| API-06 | Model artifacts loaded at startup via lifespan; API fails to start if missing | Existing `load_all_artifacts()` from `src/pipeline/inference.py` already implements fail-hard pattern |
| DASH-01 | React 19 + Vite 8 dashboard with dark cinematic + amber aesthetic | UI-SPEC.md provides complete design contract; CSS Modules with custom properties |
| DASH-02 | Pre/post lineup side-by-side with LR/RF/XGB per version | GameCard component with PredictionColumn sub-component; layout per UI-SPEC |
| DASH-03 | Kalshi price + edge signal per game | KalshiSection + EdgeBadge components; NO_EDGE suppressed per user decision |
| DASH-04 | SP confirmation status, TBD flag, sp_may_have_changed warning | SpBadge component + amber warning strip; full spec in UI-SPEC |
| DASH-05 | "Last updated" timestamp + 3-hour staleness with grayed-out cards | `opacity: 0.45` overlay; compare `Date.now()` vs displayed timestamp on every render |
| DASH-06 | Visibility-aware 60s polling with "New predictions" banner | TanStack React Query `refetchInterval` + `refetchIntervalInBackground: false` |
| DASH-07 | Explicit error state when API unreachable; last-known data with offline indicator | ErrorState component; React Query error handling; cached data display |
</phase_requirements>

## Standard Stack

### Core -- Backend (Python)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | >=0.115.0,<1.0 | REST API framework | Standard Python API framework; lifespan context manager for startup/shutdown; StaticFiles for SPA serving |
| uvicorn | >=0.30.0 | ASGI server | Standard FastAPI deployment server; production and development |
| pydantic | >=2.0 (bundled with FastAPI) | Response models, validation | FastAPI's native serialization layer; auto-generates OpenAPI docs |
| psycopg[binary,pool] | >=3.3.0,<4.0 | Postgres driver + connection pool | **Already in requirements.txt**; existing `db.py` uses sync `ConnectionPool` |

### Core -- Frontend (TypeScript/React)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| react | 19.2.x | UI framework | User-specified; latest stable |
| react-dom | 19.2.x | DOM rendering | Paired with React 19 |
| vite | 8.0.x | Build tool + dev server | User-specified; proxy support for local dev |
| typescript | 5.x or 6.x | Type safety | Standard for React projects; catches API contract mismatches at build time |
| @tanstack/react-query | 5.x | Data fetching + polling | `refetchIntervalInBackground: false` natively implements DASH-06 visibility-aware polling |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @types/react | 19.x | React TypeScript definitions | Always (TypeScript project) |
| @types/react-dom | 19.x | ReactDOM TypeScript definitions | Always (TypeScript project) |
| @vitejs/plugin-react | latest | Vite React integration | Always (Vite + React) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| TanStack React Query | SWR | SWR lacks `refetchIntervalInBackground` natively -- would require manual `visibilitychange` listener; React Query recommended by user |
| TanStack React Query | plain useEffect + fetch | Would need to hand-roll polling, visibility detection, caching, error retry -- exactly the complexity React Query solves |
| psycopg3 sync pool | asyncpg | Would require rewriting all of `db.py` to async; existing sync pool works fine with FastAPI thread pool; zero benefit for this read-heavy, low-concurrency dashboard |
| CSS Modules | Tailwind CSS | UI-SPEC specifies CSS Modules with custom properties; Tailwind not in design contract |

### Installation

**Backend (add to requirements.txt):**
```bash
pip install "fastapi[standard]>=0.115.0,<1.0"
```
Note: `fastapi[standard]` includes uvicorn. Alternatively add `uvicorn[standard]>=0.30.0` separately.

**Frontend (create new project):**
```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install @tanstack/react-query
```

**Version verification:** React 19.2.4, Vite 8.0.3, @tanstack/react-query 5.95.2, TypeScript 6.0.2 confirmed as latest via npm registry on 2026-03-29.

## Architecture Patterns

### Recommended Project Structure

```
api/
  __init__.py
  main.py              # FastAPI app + lifespan + route includes
  routes/
    __init__.py
    predictions.py     # API-01, API-02, API-03 endpoints
    accuracy.py        # API-04 endpoint
    health.py          # API-05 endpoint
  models.py            # Pydantic response models
  spa.py               # SPAStaticFiles subclass for SPA serving

frontend/
  index.html
  package.json
  tsconfig.json
  vite.config.ts
  src/
    main.tsx           # Entry point, React Query provider
    App.tsx            # Root: data fetching, layout, state management
    index.css          # CSS custom properties, font-face, reset
    api/
      client.ts        # fetch wrapper, API base URL
      types.ts         # TypeScript interfaces matching API response models
    hooks/
      usePredictions.ts    # React Query hook for predictions data
      useLatestTimestamp.ts # React Query hook for polling timestamp
    components/
      Header.module.css / Header.tsx
      AccuracyStrip.module.css / AccuracyStrip.tsx
      NewPredictionsBanner.module.css / NewPredictionsBanner.tsx
      GameCardGrid.module.css / GameCardGrid.tsx
      GameCard.module.css / GameCard.tsx
      PredictionColumn.module.css / PredictionColumn.tsx
      KalshiSection.module.css / KalshiSection.tsx
      EdgeBadge.module.css / EdgeBadge.tsx
      SpBadge.module.css / SpBadge.tsx
      EmptyState.module.css / EmptyState.tsx
      ErrorState.module.css / ErrorState.tsx
      SkeletonCard.module.css / SkeletonCard.tsx
    fonts/
      DMMono-Regular.woff2
      DMSans-Regular.woff2
      DMSans-SemiBold.woff2

src/pipeline/        # Existing -- API imports from here
  db.py              # Reused directly for DB pool
  health.py          # Reused directly for GET /health
  inference.py       # Reused for model artifact loading at startup
```

### Pattern 1: FastAPI Lifespan with Sync Pool and Model Loading

**What:** Single lifespan context manager that opens the DB pool and loads model artifacts at startup, closes pool at shutdown. Fail-hard if any artifact is missing.
**When to use:** Always -- this is the only correct startup pattern for this API.

```python
# api/main.py
from contextlib import contextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.pipeline.db import get_pool
from src.pipeline.inference import load_all_artifacts

@contextmanager
def lifespan(app: FastAPI):
    # Startup: load artifacts (fail hard if missing) then open pool
    artifacts = load_all_artifacts()  # Raises FileNotFoundError if missing
    pool = get_pool(min_size=2, max_size=5)
    app.state.artifacts = artifacts
    app.state.pool = pool
    yield
    # Shutdown: close pool
    pool.close()

app = FastAPI(title="MLB Win Forecaster API", lifespan=lifespan)

# Include API routers FIRST
# app.include_router(predictions_router, prefix="/api/v1")
# app.include_router(health_router, prefix="/api/v1")

# Mount SPA LAST (catch-all)
# app.mount("/", SPAStaticFiles(directory="frontend/dist", html=True), name="spa")
```

**Critical:** FastAPI's lifespan parameter actually expects an `asynccontextmanager`, not a sync `contextmanager`. Since the startup operations (file I/O for model loading, sync pool creation) are all synchronous, wrap them in an `asynccontextmanager`:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    artifacts = load_all_artifacts()
    pool = get_pool(min_size=2, max_size=5)
    app.state.artifacts = artifacts
    app.state.pool = pool
    yield
    pool.close()
```

### Pattern 2: Sync Route Handlers Reusing Existing DB Module

**What:** Route handlers defined as `def` (not `async def`) so they run in FastAPI's thread pool, allowing direct use of the sync psycopg3 `ConnectionPool`.
**When to use:** All API endpoints in this phase.

```python
# api/routes/predictions.py
from fastapi import APIRouter, Request
from psycopg.rows import dict_row

router = APIRouter()

@router.get("/predictions/today")
def get_today_predictions(request: Request):
    pool = request.app.state.pool
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT * FROM predictions
                WHERE game_date = CURRENT_DATE AND is_latest = TRUE
                ORDER BY home_team
            """)
            rows = cur.fetchall()
    # Transform rows into response model
    return {"predictions": rows, "timestamp": ...}
```

**Why sync `def` not `async def`:** FastAPI automatically runs sync `def` handlers in an external thread pool (via `anyio.to_thread`). This means they do NOT block the event loop. Using `async def` with sync DB calls WOULD block the event loop. The existing `db.py` module uses sync `psycopg` exclusively -- using `def` handlers is the correct, zero-refactor approach.

### Pattern 3: SPAStaticFiles for React SPA Serving

**What:** Custom `StaticFiles` subclass that returns `index.html` for any path not matching a real file, enabling client-side routing.
**When to use:** Production mode -- FastAPI serves both API and built React app.

```python
# api/spa.py
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
from pathlib import Path

class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except Exception:
            # Fall back to index.html for SPA routing
            return FileResponse(
                Path(self.directory) / "index.html"
            )
```

**Mount order matters:** API routes MUST be registered before the SPA mount. FastAPI/Starlette processes routes in registration order; a root-level StaticFiles mount would intercept API requests if mounted first.

### Pattern 4: React Query Visibility-Aware Polling (DASH-06)

**What:** TanStack React Query's `refetchInterval` combined with `refetchIntervalInBackground: false` implements the DASH-06 polling spec natively.
**When to use:** The timestamp polling query.

```typescript
// hooks/useLatestTimestamp.ts
import { useQuery } from '@tanstack/react-query';

export function useLatestTimestamp(currentTimestamp: string | null) {
  return useQuery({
    queryKey: ['latest-timestamp'],
    queryFn: () => fetch('/api/v1/predictions/latest-timestamp')
      .then(res => res.json())
      .then(data => data.timestamp),
    refetchInterval: 60_000,                  // 60 seconds
    refetchIntervalInBackground: false,       // Suspends when tab hidden
    staleTime: 55_000,                        // Avoid redundant fetches
  });
}
```

When `refetchIntervalInBackground` is `false` (default), React Query automatically pauses polling when `document.visibilityState !== 'visible'` and resumes when the tab becomes visible again. This matches DASH-06 exactly.

### Pattern 5: Ensemble Average Computation

**What:** The API returns raw model probabilities (LR, RF, XGB). The frontend computes the ensemble average for the hero number.
**When to use:** Every game card.

```typescript
function computeEnsemble(lr: number, rf: number, xgb: number): number {
  return (lr + rf + xgb) / 3;
}
```

**Decision note:** The ensemble average could be computed server-side or client-side. Server-side is cleaner (single source of truth), but CONTEXT.md specifies "LR + RF + XGBoost averaged" as the hero number, suggesting the API should return the individual values and let the frontend derive the average. This keeps the API response shape stable if the averaging logic changes.

**Recommendation:** Compute ensemble server-side in the API response (add an `ensemble_prob` field) AND return individual model probs. This ensures consistency and avoids floating-point discrepancies between server/client.

### Anti-Patterns to Avoid

- **`async def` with sync DB calls:** Using `async def` route handlers with the sync psycopg3 pool would block the event loop. Always use `def` handlers when calling sync I/O.
- **Model loading in request handlers:** Violates API-06. All 6 artifacts MUST be loaded in the lifespan, not on first request.
- **Mounting StaticFiles before API routes:** The SPA catch-all mount at `/` would intercept `/api/*` requests. API routes must be registered first.
- **Browser reload for "New predictions" banner:** DASH-06 specifies full data refetch via React Query, NOT `window.location.reload()`.
- **Async pool migration:** Do NOT convert `db.py` to use `AsyncConnectionPool` -- it would break the existing pipeline scheduler which also uses the sync pool.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Visibility-aware polling | Manual `visibilitychange` event listener + `setInterval` | React Query `refetchInterval` + `refetchIntervalInBackground: false` | React Query handles edge cases (tab focus, window blur, multiple queries, cleanup on unmount) |
| API data caching / stale management | Custom in-memory cache with timestamps | React Query `staleTime` + `gcTime` | Handles cache invalidation, background refetching, error retry automatically |
| API response serialization | Manual dict construction in route handlers | Pydantic response models with `model_config` | Type safety, automatic OpenAPI docs, consistent field naming (camelCase) |
| SPA fallback routing | Manual catch-all route with `FileResponse` | SPAStaticFiles subclass | Handles all static assets (JS, CSS, fonts) AND falls back to index.html for unknown paths |
| CORS configuration | Manual middleware | FastAPI `CORSMiddleware` | Only needed in development (Vite proxy handles it in dev); production serves same-origin |
| Skeleton loading states | Custom CSS from scratch | CSS keyframe animation with opacity pulse | UI-SPEC provides exact animation spec: `opacity 0.3-0.6, 1.5s ease-in-out infinite` |

**Key insight:** This phase is fundamentally a read-only data display pipeline. The complexity is in getting the visual states right (stale, offline, TBD, sp_changed), not in the data plumbing. React Query eliminates most of the data-layer complexity, letting implementation focus on the 7 visual states defined in UI-SPEC.

## Common Pitfalls

### Pitfall 1: Mounting SPA StaticFiles Before API Routes
**What goes wrong:** All requests including `/api/*` get intercepted by the StaticFiles mount at `/`, returning 404 or index.html instead of API responses.
**Why it happens:** FastAPI/Starlette processes routes in registration order. A root mount matches everything.
**How to avoid:** Always `include_router()` all API routes BEFORE calling `app.mount("/", SPAStaticFiles(...))`.
**Warning signs:** API endpoints return HTML instead of JSON; 404 errors on valid API paths.

### Pitfall 2: Using `async def` with Sync psycopg3 Pool
**What goes wrong:** The event loop blocks on every DB call, causing request timeouts and degraded throughput.
**Why it happens:** `async def` handlers run on the event loop; sync I/O blocks the entire loop. `def` handlers run in a thread pool, keeping the event loop free.
**How to avoid:** Use `def` (not `async def`) for all route handlers that call sync `db.py` functions.
**Warning signs:** High latency on concurrent requests; uvicorn logs showing event loop blocking.

### Pitfall 3: FastAPI Lifespan Must Be `asynccontextmanager`
**What goes wrong:** FastAPI silently ignores a sync `contextmanager` lifespan -- startup code never runs.
**Why it happens:** FastAPI expects an async context manager even if the body is synchronous.
**How to avoid:** Always use `@asynccontextmanager` and `async def lifespan(app)`, even when the body contains only sync operations.
**Warning signs:** `app.state.pool` is `None` at request time; model artifacts not loaded.

### Pitfall 4: Stale Timestamp Comparison Timezone Mismatch
**What goes wrong:** Staleness check (DASH-05: 3-hour threshold) gives wrong results because server sends UTC timestamps but client compares against local time.
**Why it happens:** Postgres `TIMESTAMPTZ` values are UTC; JavaScript `Date.now()` is UTC but displayed in local time.
**How to avoid:** Always compare UTC timestamps. API returns ISO8601 with `Z` suffix. Frontend converts to UTC for comparison, local time for display.
**Warning signs:** Staleness indicators appear immediately or never, depending on user timezone.

### Pitfall 5: React Query Default Stale Time
**What goes wrong:** React Query refetches on every window focus event (default `staleTime: 0`), causing unnecessary API calls.
**Why it happens:** Default behavior treats all data as immediately stale.
**How to avoid:** Set `staleTime` on the predictions query to something reasonable (e.g., 55 seconds, just under the poll interval). The timestamp query can use shorter staleTime since it's lightweight.
**Warning signs:** Excessive API calls on tab switches; network tab shows double fetches.

### Pitfall 6: Font Loading Flash (FOUT)
**What goes wrong:** Text appears in fallback system fonts for 200-500ms before DM Sans/DM Mono load, causing layout shift.
**Why it happens:** Self-hosted fonts not preloaded; browser renders text in fallback font while downloading.
**How to avoid:** Preload woff2 files via `<link rel="preload" as="font" type="font/woff2" crossorigin>` in `index.html`. Use `font-display: swap` in `@font-face` declarations.
**Warning signs:** Visible text reflow on initial page load; hero probability numbers shift width.

### Pitfall 7: Missing `created_at` in API Response for Staleness
**What goes wrong:** Frontend cannot compute staleness because the API doesn't include the prediction timestamp.
**Why it happens:** API returns model probs but forgets the `created_at` column needed for DASH-05.
**How to avoid:** API response model MUST include `latest_prediction_at` (the max `created_at` across all returned predictions) and individual `created_at` per prediction row.
**Warning signs:** "Last updated" always shows "unknown"; staleness indicator never triggers.

## Code Examples

### FastAPI Lifespan with Model Loading and DB Pool

```python
# api/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.pipeline.db import get_pool
from src.pipeline.inference import load_all_artifacts

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: fail hard if artifacts missing (API-06)
    artifacts = load_all_artifacts()
    pool = get_pool(min_size=2, max_size=5)
    app.state.artifacts = artifacts
    app.state.pool = pool
    yield
    # Shutdown
    pool.close()

app = FastAPI(
    title="MLB Win Forecaster API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS only needed for Vite dev server (localhost:5173 -> localhost:8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)
```

### Pydantic Response Model for Predictions

```python
# api/models.py
from pydantic import BaseModel, Field
from datetime import date, datetime

class PredictionResponse(BaseModel):
    game_date: date
    home_team: str
    away_team: str
    prediction_version: str
    prediction_status: str
    lr_prob: float | None
    rf_prob: float | None
    xgb_prob: float | None
    ensemble_prob: float | None  # Server-computed average
    feature_set: str
    home_sp: str | None
    away_sp: str | None
    sp_uncertainty: bool
    sp_may_have_changed: bool
    kalshi_yes_price: float | None
    edge_signal: str | None
    edge_magnitude: float | None  # Computed: ensemble_prob - kalshi_yes_price
    created_at: datetime

class TodayResponse(BaseModel):
    predictions: list[PredictionResponse]
    latest_prediction_at: datetime | None
    generated_at: datetime

class LatestTimestampResponse(BaseModel):
    timestamp: datetime | None
```

### Vite Proxy Configuration

```typescript
// frontend/vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
```

### React Query Provider and Polling Hook

```typescript
// frontend/src/hooks/useLatestTimestamp.ts
import { useQuery } from '@tanstack/react-query';

interface TimestampResponse {
  timestamp: string | null;
}

export function useLatestTimestamp() {
  return useQuery<TimestampResponse>({
    queryKey: ['latest-timestamp'],
    queryFn: async () => {
      const res = await fetch('/api/v1/predictions/latest-timestamp');
      if (!res.ok) throw new Error('Failed to fetch timestamp');
      return res.json();
    },
    refetchInterval: 60_000,
    refetchIntervalInBackground: false, // DASH-06: pause when tab hidden
  });
}
```

### CSS Custom Properties (from UI-SPEC)

```css
/* frontend/src/index.css */
:root {
  --color-bg: #0A0A0F;
  --color-surface: #12121A;
  --color-border: #1E1E2A;
  --color-text-primary: #E8E8ED;
  --color-text-secondary: #8A8A9A;
  --color-accent: #F59E0B;
  --color-accent-muted: #D97706;
  --color-edge-green: #22C55E;
  --color-edge-red: #EF4444;
  --color-stale: #6B7280;

  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;
  --space-2xl: 48px;

  --font-data: 'DM Mono', monospace;
  --font-ui: 'DM Sans', sans-serif;
}

*, *::before, *::after { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--color-bg);
  color: var(--color-text-primary);
  font-family: var(--font-ui);
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| FastAPI `on_event("startup")` | `lifespan` async context manager | FastAPI 0.95+ (2023) | Old events still work but deprecated; lifespan is the recommended pattern |
| React Query v4 `useQuery(key, fn, opts)` | React Query v5 `useQuery({ queryKey, queryFn, ...opts })` | TanStack Query v5 (2023) | Object syntax is the only API; positional args removed |
| Create React App | Vite | 2022-present | CRA deprecated; Vite is the standard React project scaffold |
| psycopg2 | psycopg3 (psycopg) | 2021-present | Native async support, better typing, connection pools; project already uses psycopg3 |

**Deprecated/outdated:**
- `@app.on_event("startup")` / `@app.on_event("shutdown")`: Deprecated in favor of lifespan. Still functional but generates deprecation warnings.
- `create-react-app`: Deprecated and unmaintained. Use Vite.
- React Query v3/v4 syntax: v5 uses object-only API for `useQuery`.

## Open Questions

1. **Font file sourcing for DM Mono and DM Sans**
   - What we know: UI-SPEC specifies self-hosted woff2 files with Latin subset preloading.
   - What's unclear: Whether to download from Google Fonts CDN during build or commit woff2 files to repo.
   - Recommendation: Download woff2 files from Google Fonts and commit to `frontend/src/fonts/`. They are small (10-30KB each) and eliminate external CDN dependency. Three files needed: DM Mono Regular, DM Sans Regular, DM Sans SemiBold (600).

2. **API-04 accuracy endpoint query complexity**
   - What we know: The endpoint aggregates Brier scores by date range from predictions joined with game outcomes.
   - What's unclear: Whether the `games` table has outcome data (the `home_win` column exists in schema but may not be populated by the pipeline).
   - Recommendation: Implement API-04 as a simple endpoint that reads from `model_metadata.json` (like the static accuracy strip) until game outcome data is reliably populated. Phase 8 scope is read-only -- backfilling results is not in scope.

3. **CORS in production**
   - What we know: In production, FastAPI serves both API and frontend from the same origin (via StaticFiles mount), so CORS is not needed.
   - What's unclear: Whether there are any cross-origin consumers of the API.
   - Recommendation: Enable CORS middleware only with `localhost:5173` origin for development. In production, the same-origin setup eliminates CORS entirely.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.1.1 (already installed) |
| Config file | None (runs from repo root with default discovery) |
| Quick run command | `pytest tests/test_pipeline/ -x -q` |
| Full suite command | `pytest tests/ -x -q` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| API-01 | GET /predictions/today returns correct shape | unit | `pytest tests/test_api/test_predictions.py::test_today_endpoint -x` | Wave 0 |
| API-02 | GET /predictions/{date} returns historical data | unit | `pytest tests/test_api/test_predictions.py::test_date_endpoint -x` | Wave 0 |
| API-03 | GET /predictions/latest-timestamp returns timestamp | unit | `pytest tests/test_api/test_predictions.py::test_latest_timestamp -x` | Wave 0 |
| API-04 | GET /results/accuracy returns Brier scores | unit | `pytest tests/test_api/test_accuracy.py -x` | Wave 0 |
| API-05 | GET /health returns pipeline status | unit | `pytest tests/test_api/test_health_endpoint.py -x` | Wave 0 |
| API-06 | App fails to start if artifacts missing | unit | `pytest tests/test_api/test_lifespan.py::test_missing_artifact_fails -x` | Wave 0 |
| DASH-01 | Frontend builds without errors | smoke | `cd frontend && npm run build` | Wave 0 (build script) |
| DASH-02 | GameCard renders both prediction versions | manual-only | Visual inspection of component rendering | N/A -- no component test framework in scope |
| DASH-03 | KalshiSection renders edge badge correctly | manual-only | Visual inspection | N/A |
| DASH-04 | SpBadge renders TBD and warning states | manual-only | Visual inspection | N/A |
| DASH-05 | Staleness overlay applied after 3 hours | manual-only | Visual inspection with mock data | N/A |
| DASH-06 | Polling fires every 60s when visible, suspends when hidden | manual-only | Manual tab switching test + network tab observation | N/A |
| DASH-07 | Error state shown when API unreachable | manual-only | Kill API server, observe dashboard behavior | N/A |

### Sampling Rate
- **Per task commit:** `pytest tests/test_api/ -x -q` (API tests only, fast)
- **Per wave merge:** `pytest tests/ -x -q && cd frontend && npm run build` (full suite + frontend build)
- **Phase gate:** Full suite green + successful frontend build before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_api/` directory -- new test directory for API endpoint tests
- [ ] `tests/test_api/__init__.py` -- package init
- [ ] `tests/test_api/conftest.py` -- FastAPI TestClient fixture with mocked pool/artifacts
- [ ] `tests/test_api/test_predictions.py` -- covers API-01, API-02, API-03
- [ ] `tests/test_api/test_accuracy.py` -- covers API-04
- [ ] `tests/test_api/test_health_endpoint.py` -- covers API-05
- [ ] `tests/test_api/test_lifespan.py` -- covers API-06
- [ ] `httpx` added to dev dependencies -- required for FastAPI TestClient
- [ ] Frontend DASH requirements tested manually (no React component test framework in scope for v2.0)

## Sources

### Primary (HIGH confidence)
- Existing codebase: `src/pipeline/db.py`, `src/pipeline/health.py`, `src/pipeline/inference.py`, `src/pipeline/schema.sql` -- direct inspection of Phase 7 outputs
- `models/artifacts/model_metadata.json` -- actual Brier scores for accuracy strip
- `.planning/phases/08-api-and-dashboard/08-UI-SPEC.md` -- complete visual/interaction contract
- `.planning/phases/08-api-and-dashboard/08-CONTEXT.md` -- user decisions and constraints
- npm registry (2026-03-29) -- verified versions: React 19.2.4, Vite 8.0.3, @tanstack/react-query 5.95.2, TypeScript 6.0.2

### Secondary (MEDIUM confidence)
- [FastAPI lifespan docs](https://fastapi.tiangolo.com/advanced/events/) -- lifespan async context manager pattern
- [FastAPI StaticFiles docs](https://fastapi.tiangolo.com/tutorial/static-files/) -- StaticFiles with html=True
- [TanStack Query useQuery docs](https://tanstack.com/query/v5/docs/framework/react/reference/useQuery) -- refetchInterval, refetchIntervalInBackground options
- [psycopg3 connection pool docs](https://www.psycopg.org/psycopg3/docs/advanced/pool.html) -- sync ConnectionPool usage
- [Vite server options](https://vite.dev/config/server-options) -- proxy configuration
- [FastAPI + React SPA pattern](https://davidmuraya.com/blog/serving-a-react-frontend-application-with-fastapi/) -- SPAStaticFiles subclass approach
- [FastAPI + psycopg3 integration](https://spwoodcock.dev/blog/2024-10-fastapi-pydantic-psycopg/) -- sync pool with FastAPI def handlers

### Tertiary (LOW confidence)
- FastAPI latest version 0.135.x (from PyPI search results) -- exact minor version may differ at install time; pin to >=0.115.0,<1.0 range

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- versions verified against npm/pip registries; existing codebase provides clear integration path
- Architecture: HIGH -- patterns verified against official docs; existing db.py sync pool confirmed compatible with FastAPI def handlers
- Pitfalls: HIGH -- common issues documented from multiple sources; timezone and mount-order pitfalls verified against official FastAPI docs
- UI-SPEC compliance: HIGH -- complete design contract exists with exact colors, spacing, typography, copywriting, and component inventory

**Research date:** 2026-03-29
**Valid until:** 2026-04-28 (stable stack -- React 19, FastAPI, psycopg3 all mature)
