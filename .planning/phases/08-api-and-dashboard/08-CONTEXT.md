# Phase 8: API and Dashboard — Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the FastAPI read layer over Postgres and the React 19/Vite 8 frontend that together deliver the live dashboard at mlbforecaster.silverreyes.net. Phase 8 produces: all API endpoints (API-01 through API-06), the React dashboard (DASH-01 through DASH-07), and the `frontend/` project scaffold with local dev setup. Infrastructure, deployment, and Nginx/SSL are Phase 9. The `frontend-design` skill must be invoked before planning begins (DASH-01 gate).

</domain>

<decisions>
## Implementation Decisions

### Game card — hero number
- **Ensemble average** is the primary/hero probability displayed on each game card (LR + RF + XGBoost averaged)
- Individual model breakdown (LR / RF / XGB) is **always visible below the hero number** — no expand/toggle, no tooltip; instant visibility for power users

### Game card — pre/post lineup layout
- **Post-lineup is primary**: when both versions exist, post-lineup takes the left/main slot with full prominence; pre-lineup shown smaller as reference context
- This reflects that pitcher-informed predictions are more accurate; the layout communicates the hierarchy

### Game card — TBD/pre-lineup-only state
- When no post-lineup prediction exists yet (starters TBD or unconfirmed): show team-only ensemble probability at full opacity with an **amber "SP: TBD" badge** in the starter name slot
- Cards are NOT grayed out for this state — team-only predictions are real predictions, just without SP info

### Game card — Kalshi edge signal
- **Kalshi price always shown** on every game card
- **Edge badge (BUY_YES / BUY_NO) shown only when an edge exists** — NO_EDGE is suppressed from the card entirely (it's noise)
- Edge badge format: color-coded badge + edge magnitude (e.g., green "BUY YES +8.3pts" or red "BUY NO −6.1pts")
- Fee-adjusted framing consistent with v1 (`KALSHI_FEE_RATE = 0.07` on profits)

### Game card — sp_may_have_changed warning
- Surface as an **amber warning banner across the top of the card**: "⚠ SP assignment may have changed — confirmation pending"
- Amber fits the aesthetic; signals attention without implying error

### Historical date navigation
- **Today-only dashboard** — no date picker, no prev/next navigation in the UI
- `GET /api/v1/predictions/{date}` (API-02) is available for direct API access but not exposed in the dashboard frontend
- Keeps the UI focused as a live predictions tool, not a historical results browser

### Accuracy metrics on dashboard
- A **static summary strip** showing Brier scores (e.g., "XGBoost SP: 0.231 | RF SP: 0.238 | LR SP: 0.244 | Kalshi 2025: 0.224")
- Pre-rendered from `models/artifacts/model_metadata.json` — NOT a live API-04 call on page load
- Placement and sizing at Claude's discretion within the dark/amber design

### Frontend project structure
- **`frontend/` directory in this repo** — React app alongside `src/`, `notebooks/`, etc.; single git history
- `.gitignore` must be updated as part of Phase 8 setup to exclude:
  - `frontend/node_modules/`
  - `frontend/dist/`
  - `frontend/.env.local`
- **Local dev**: Vite dev server with `/api/*` proxied to `localhost:8000` in `vite.config.ts`; run FastAPI and Vite separately, no Docker required for frontend dev
- **Production**: FastAPI mounts `frontend/dist/` as StaticFiles at the root route — single container serves both API and frontend
- **Greenfield FastAPI app**: new `api/main.py` (or `api/app.py`) entry point that imports from `src/pipeline/`; lifespan context manager handles DB pool and model artifact loading at startup

### Claude's Discretion
- Exact placement and sizing of the accuracy metrics strip within the dark/amber design
- React component file structure within `frontend/src/`
- Whether to use React Query, SWR, or plain `useEffect` + `fetch` for data fetching (prefer React Query — visibility-aware polling aligns with its `refetchIntervalInBackground: false` option)
- Error boundary vs manual error state component for DASH-07
- Postgres connection pool library (asyncpg vs psycopg3 — either fits; pick what integrates cleanest with FastAPI async)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### API and Dashboard Requirements
- `.planning/REQUIREMENTS.md` §API-01 through API-06 — exact endpoint shapes, startup behavior, model loading requirement
- `.planning/REQUIREMENTS.md` §DASH-01 through DASH-07 — all dashboard requirements including polling spec, staleness rules, error state, aesthetic spec
- `.planning/ROADMAP.md` §Phase 8 — goal, success criteria, DASH-01 frontend-design skill gate note

### Existing Backend Code (Phase 7 outputs — API builds on these)
- `src/pipeline/db.py` — DB connection pool; API imports this directly
- `src/pipeline/health.py` — `get_health_data()` for `GET /api/v1/health`
- `src/pipeline/inference.py` — prediction inference; model loading patterns to follow for API startup
- `src/pipeline/schema.sql` — Postgres schema; defines `predictions` table shape that API-01/02 query

### Model Artifacts
- `models/artifacts/model_metadata.json` — source for static accuracy strip (Brier scores, training metadata)
- `models/artifacts/` — 6 `.joblib` files loaded at FastAPI startup via lifespan

### No external design specs yet
- UI-SPEC.md to be generated by the `frontend-design` skill before planning begins (DASH-01 gate) — downstream agents must read it once created

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/pipeline/db.py` — asyncpg/psycopg DB pool; API lifespan context manager wraps this
- `src/pipeline/health.py` — `get_health_data(pool)` → structured dict; maps directly to `GET /api/v1/health` response
- `src/pipeline/inference.py` — model loading and prediction; understand artifact loading pattern before writing lifespan
- `src/models/edge.py` — edge signal computation (`BUY_YES`/`BUY_NO`/`NO_EDGE`); API serializes these values from DB, but the constant names/labels come from here
- `src/models/feature_sets.py` — `TEAM_ONLY_FEATURE_COLS`, `SP_ENHANCED_FEATURE_COLS`; relevant when API exposes which feature set was used for a prediction

### Established Patterns
- Thin-notebook pattern from v1: business logic in `src/`, notebooks/frontend just call it — apply same pattern to API (thin route handlers, logic in `src/pipeline/`)
- `KALSHI_FEE_RATE = 0.07` named constant from `src/models/edge.py` — fee-adjusted framing must be consistent with this value in frontend display copy
- Two-track evaluation: primary backtest (2015–2024) vs secondary Kalshi track (2025) — accuracy strip must label which benchmark each Brier score comes from

### Integration Points
- `api/main.py` → imports `src/pipeline/db`, `src/pipeline/health`, `src/pipeline/inference`
- `api/main.py` → lifespan creates DB pool + loads 6 model artifacts; both injected into request state
- FastAPI `app.mount("/", StaticFiles(directory="frontend/dist", html=True))` — must be mounted AFTER all API routes (route ordering matters in FastAPI)
- Vite proxy: `vite.config.ts` `server.proxy['/api'] = 'http://localhost:8000'`

</code_context>

<specifics>
## Specific Requirements

- `.gitignore` update is a Phase 8 task, not optional — `frontend/node_modules/`, `frontend/dist/`, `frontend/.env.local` must be excluded before the first commit of frontend code
- Polling implementation per DASH-06: `document.visibilityState === 'visible'` check on `visibilitychange` events; React Query's `refetchIntervalInBackground: false` flag implements this natively — verify this before choosing a polling approach
- "New predictions available — refresh" banner (DASH-06): appears when polled timestamp from `GET /api/v1/predictions/latest-timestamp` is newer than the timestamp of currently displayed data; clicking it triggers a full data refetch (not a browser reload)
- Model artifact loading per API-06: FastAPI must **fail to start** (not silently) if any of the 6 model artifacts is missing — raise on startup, not on first request

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 08-api-and-dashboard*
*Context gathered: 2026-03-29*
