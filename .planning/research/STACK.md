# Technology Stack -- v2.2 Additions

**Project:** MLB Win Forecaster -- Game Lifecycle, Live Scores & Historical Accuracy
**Researched:** 2026-03-30
**Scope:** NEW dependencies only. Existing stack (React 19, Vite 8, TanStack Query 5, FastAPI, psycopg3, APScheduler, MLB-StatsAPI 1.9.0) is validated and unchanged.

---

## Recommended Stack Additions

### Frontend -- Routing

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| react-router | ^7.13.2 | Client-side routing for `/` (dashboard) and `/history` (accuracy page) | React Router 7 supports React 19 natively. Declarative mode is the right fit -- no SSR/framework features needed. Single `npm i react-router` install, no separate `react-router-dom` package (they merged in v7). Estimated ~14kB gzipped. The existing `SPAStaticFiles` middleware in `api/spa.py` already falls back unknown paths to `index.html`, so server-side SPA routing works with zero backend changes. |

**Confidence:** HIGH -- React Router 7.13.2 is current stable, React 19 support confirmed on reactrouter.com, declarative mode documented at reactrouter.com/start/declarative/installation.

**Integration with existing app:**
- Wrap `<App />` in `<BrowserRouter>` inside `main.tsx` (alongside existing `<QueryClientProvider>`)
- Use `<Routes>` / `<Route>` inside `App.tsx` for `/` and `/history`
- Shared layout components (`Header`, `AboutModels`) remain outside `<Routes>`

### Frontend -- Date Picker

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Native `<input type="date">` | N/A | Calendar picker for date navigation | **Do not add react-day-picker.** The project philosophy favors zero-dep solutions (CSS-only tooltips, native `<details>` for collapsibles). A native date input is accessible, mobile-friendly, adds no bundle weight, and meets the use case perfectly: picking a single date from a calendar. Style with CSS custom properties to match dark/amber theme. The only limitation is cross-browser styling inconsistency, which is acceptable for a single-user dashboard. |

**Confidence:** HIGH -- native HTML5 input, no dependency to verify.

**Why NOT react-day-picker v9:**
- Pulls in date-fns as a bundled dependency (~22kB gzipped total for react-day-picker + date-fns)
- Overkill for single-date selection with no range picking or multi-select
- Requires CSS override work to match custom dark/amber theme
- Adds maintenance burden for a feature that native HTML handles

**Date navigation UX approach:**
- Left/right arrow buttons for day-by-day navigation (custom `<button>` components)
- A "Today" chip/button for quick return to current date
- Native `<input type="date">` for calendar jump-to-date
- All three controls compose into a `<DateNav>` component that manages a `selectedDate` state
- The `selectedDate` drives the TanStack Query key: `['predictions', selectedDate]` fetching `/api/v1/predictions/{date}`

### Frontend -- Bases Diamond SVG

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Inline SVG component | N/A | Visual bases-occupied indicator on in-progress game cards | Hand-craft a `<BasesDiamond>` React component (~30 lines JSX) using inline SVG. Four shapes: home plate (pentagon), 1B/2B/3B (rotated squares). Fill occupied bases with `var(--color-amber)`, empty with `var(--color-surface-dim)`. No library needed -- the geometry is 4 simple shapes with conditional fill. This is the standard approach in MLB scorecard UIs. Props: `{ first: boolean; second: boolean; third: boolean }`. |

**Confidence:** HIGH -- trivial SVG geometry, no external dependency.

**SVG approach details:**
```
<svg viewBox="0 0 60 60" width="40" height="40">
  <!-- 2B: top diamond -->  <rect x="22" y="5"  w="16" h="16" transform="rotate(45 30 13)" />
  <!-- 3B: left diamond --> <rect x="5"  y="22" w="16" h="16" transform="rotate(45 13 30)" />
  <!-- 1B: right diamond --><rect x="39" y="22" w="16" h="16" transform="rotate(45 47 30)" />
  <!-- Home: bottom -->     <polygon points="30,55 22,47 26,40 34,40 38,47" />
</svg>
```
Each base gets `fill={occupied ? 'var(--color-amber)' : 'var(--color-surface-dim)'}`.

### Frontend -- No Other Additions

| Considered | Decision | Why |
|------------|----------|-----|
| TanStack Router | Skip | Already using TanStack Query; but TanStack Router is ~50kB gzipped and designed for file-based routing patterns. React Router declarative mode is lighter and better suited for 2 routes. |
| chart.js / recharts | Skip | History page accuracy display can use a simple HTML table with CSS-styled bar widths for rolling accuracy. If charts are needed later, revisit in a future milestone. |
| date-fns | Skip | Not needed independently. Native `Date` + `Intl.DateTimeFormat` (already used for game time display) handles all date formatting. |
| wouter | Skip | Ultra-lightweight router (~1.5kB) but lacks community size and React 19 testing. React Router 7 is the safe choice for a production app. |

---

### Backend -- Python Dependencies

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| No new Python packages | -- | -- | Everything needed is already installed. MLB-StatsAPI 1.9.0 provides `statsapi.schedule()` with `hydrate='linescore'` for live score data. APScheduler 3.x handles the nightly reconciliation job. psycopg3 handles the DB writes for `actual_winner`/`prediction_correct`. httpx is already in requirements.txt for any direct HTTP calls. |

**Confidence:** HIGH -- all capabilities verified against existing `requirements.txt` and MLB-StatsAPI library.

**Backend work is code changes, not new deps:**

1. **Live score proxy endpoint** -- New FastAPI route `GET /api/v1/scores/{date}` that calls `statsapi.schedule()` with `hydrate='linescore,team'` and returns a slim JSON response. The frontend polls this at 90s intervals via a new TanStack Query hook. Proxy through FastAPI because MLB Stats API CORS policy is unknown/unreliable for browser-direct calls, and proxying lets us shape the response to only the fields the frontend needs.

2. **Outcome reconciliation** -- New function in `src/pipeline/db.py` that writes `actual_winner` and `prediction_correct` columns. Called from two places:
   - The live score poller detects `abstractGameState == "Final"` and writes immediately
   - A nightly APScheduler job at 1:00 AM ET catches any games the poller missed

3. **Schema migration** -- Three new columns on `predictions` table:
   ```sql
   ALTER TABLE predictions ADD COLUMN actual_winner VARCHAR(3);
   ALTER TABLE predictions ADD COLUMN prediction_correct BOOLEAN;
   ALTER TABLE predictions ADD COLUMN reconciled_at TIMESTAMPTZ;
   ```

---

## MLB Stats API Live Feed -- Endpoint Shape

**Endpoint:** `GET https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={MM/DD/YYYY}&hydrate=linescore,team`

**Confidence:** HIGH -- verified by fetching live data from the endpoint on 2026-03-30.

### Response structure (relevant fields only):

```json
{
  "dates": [{
    "games": [{
      "gamePk": 778277,
      "status": {
        "abstractGameState": "Final" | "Live" | "Preview",
        "detailedState": "Final" | "In Progress" | "Pre-Game" | "Scheduled" | "Warmup",
        "statusCode": "F" | "I" | "P" | "S" | "PW"
      },
      "linescore": {
        "currentInning": 7,
        "currentInningOrdinal": "7th",
        "inningState": "Top" | "Bottom",
        "isTopInning": true,
        "teams": {
          "home": { "runs": 3, "hits": 8, "errors": 0 },
          "away": { "runs": 1, "hits": 5, "errors": 1 }
        },
        "offense": {
          "first": { "id": 123456, "fullName": "Player Name" },
          "second": null,
          "third": { "id": 654321, "fullName": "Player Name" }
        },
        "balls": 2,
        "strikes": 1,
        "outs": 1
      },
      "teams": {
        "home": { "team": { "name": "...", "abbreviation": "NYY" } },
        "away": { "team": { "name": "...", "abbreviation": "BOS" } }
      }
    }]
  }]
}
```

### Key fields for each feature:

| Feature | Fields Used |
|---------|-------------|
| Score display | `linescore.teams.{home,away}.runs` |
| Inning indicator | `linescore.currentInning` + `linescore.inningState` |
| Bases diamond | `linescore.offense.{first,second,third}` (null = empty, object = occupied) |
| Count display | `linescore.{balls,strikes,outs}` |
| Game status | `status.abstractGameState` ("Preview"/"Live"/"Final") |
| Final detection | `status.abstractGameState === "Final"` triggers reconciliation write |
| Winner detection | Compare `linescore.teams.home.runs` vs `linescore.teams.away.runs` when Final |

### Python access via MLB-StatsAPI:

The existing `MLB-StatsAPI==1.9.0` library wraps this endpoint. Two approaches:

1. **`statsapi.schedule()`** -- Returns parsed dicts but does NOT include linescore hydration in its parsed output. Only returns basic game info.
2. **`statsapi.get('schedule', params)`** -- Returns raw JSON from the API, preserving the full hydrated response including linescore.

**Use `statsapi.get()` for the live score proxy**, since `statsapi.schedule()` strips the linescore data during its internal parsing:

```python
import statsapi
data = statsapi.get(
    'schedule',
    {'sportId': 1, 'date': '03/30/2026', 'hydrate': 'linescore,team'}
)
# data is a dict with full API response including linescore
```

---

## Integration with Existing TanStack Query Polling

### Current polling architecture:
- `usePredictions()` hook: polls `/api/v1/predictions/today` with `staleTime: 55_000` (55s)
- `useLatestTimestamp()` hook: polls `/api/v1/predictions/latest-timestamp` for new-predictions detection

### New polling hooks for v2.2:

| Hook | Endpoint | Interval | When Active |
|------|----------|----------|-------------|
| `useLiveScores(date)` | `GET /api/v1/scores/{date}` | 90s (`staleTime: 85_000`) | Only when `date === today` AND at least one game has `status === "Live"` |
| `usePredictions(date)` | `GET /api/v1/predictions/{date}` | 55s (existing) | Always for selected date |

**Key design decisions:**
- `useLiveScores` should use `refetchInterval` conditionally: set to `90_000` when any game is live, `false` when all games are Final/Preview. This avoids unnecessary polling outside game hours.
- Query key includes the date: `['scores', selectedDate]` so date navigation invalidates the cache correctly.
- The existing `usePredictions` hook changes from hardcoded `'predictions-today'` key to `['predictions', selectedDate]` and fetches from `/api/v1/predictions/{date}` instead of `/predictions/today`.
- `document.visibilityState` gating should apply to live scores too (already implemented for predictions).

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Router | react-router 7 (declarative) | TanStack Router | TanStack Router is heavier (~50kB) and designed for data-loading patterns we already handle with TanStack Query. Two routes do not justify the complexity. |
| Router | react-router 7 (declarative) | wouter | Wouter is 1.5kB and elegant but has a smaller community and React 19 support is less battle-tested than React Router. |
| Date picker | Native `<input type="date">` | react-day-picker v9 | ~22kB gzipped total. Single-date selection does not need a full calendar library. Project precedent: CSS-only tooltips, native `<details>`. |
| Date picker | Native `<input type="date">` | react-datepicker | Even heavier than react-day-picker. Same reasoning applies. |
| Bases diamond | Inline SVG component | react-baseball-field-component | Unmaintained npm package (last updated 2019). The SVG is 4 shapes -- a dependency is absurd. |
| Live score source | Backend proxy endpoint | Direct browser fetch to statsapi.mlb.com | MLB Stats API CORS is unreliable for browser origins. Proxy through FastAPI gives response shaping, caching control, and CORS certainty. |
| Charts (history page) | HTML table + CSS bars | recharts / chart.js | Rolling accuracy is a single metric over time. A styled table with CSS width-based bars is sufficient. Avoids ~45kB+ chart library for one visual. Revisit if charting needs grow. |
| Nightly job | APScheduler CronTrigger (existing) | Celery / Celery Beat | Celery requires Redis/RabbitMQ broker. Massive overkill for one nightly job added to an existing APScheduler instance. Just add another `scheduler.add_job()` call. |
| Schema migration | Raw ALTER TABLE in schema.sql | Alembic | Three additive columns do not warrant a migration framework. `IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS` (Postgres 9.6+) makes it idempotent. Alembic is appropriate when schema changes become frequent (v3+). |

---

## What NOT to Add

| Technology | Why Avoid |
|------------|-----------|
| react-day-picker / react-datepicker | Bundle bloat for a single-date picker. Use native `<input type="date">`. |
| date-fns | Not needed. `Intl.DateTimeFormat` and native `Date` methods handle all formatting. Already used in v2.1 for game time display. |
| recharts / chart.js / victory | History page v1 is a table. Do not add a charting library preemptively. |
| Celery / Redis | No message broker needed. APScheduler handles the nightly reconciliation job. |
| Alembic | Three additive columns do not justify a migration framework. |
| WebSocket (socket.io, etc.) | Explicitly out of scope per PROJECT.md. Client-side polling at 90s is sufficient and avoids infrastructure complexity. |
| axios | `fetch()` + the existing `fetchJson()` wrapper in `api/client.ts` is sufficient. No reason to add axios. |

---

## Installation

### Frontend (one new package)

```bash
cd frontend
npm install react-router
```

Total bundle impact: ~14kB gzipped (react-router declarative mode, tree-shaken).

### Backend (zero new packages)

No changes to `requirements.txt`. All capabilities (MLB Stats API hydrated schedule, APScheduler cron jobs, psycopg3 column writes) are already available.

---

## Summary of Changes by Feature Area

| Feature | Frontend Deps | Backend Deps | New API Endpoints |
|---------|--------------|-------------|-------------------|
| Date navigation | react-router (routing), native `<input type="date">` | None | None (existing `/predictions/{date}` works) |
| Live scores | None (TanStack Query existing) | None (MLB-StatsAPI existing) | `GET /api/v1/scores/{date}` (new proxy) |
| Bases diamond | None (inline SVG) | None | Included in `/scores/{date}` response |
| Outcome reconciliation | None | None (APScheduler + psycopg3 existing) | None (backend-only writes) |
| History page | react-router (routing) | None | `GET /api/v1/history?start={date}&end={date}` (new) |

**Net new frontend dependency: 1 (react-router)**
**Net new backend dependency: 0**

---

## Sources

- [React Router 7 home](https://reactrouter.com/home) -- v7.13.2, React 19 support confirmed (HIGH confidence)
- [React Router declarative installation](https://reactrouter.com/start/declarative/installation) -- setup guide (HIGH confidence)
- [react-day-picker v9 changelog](https://daypicker.dev/changelog) -- v9.14.0, Feb 2026, date-fns bundled (HIGH confidence)
- [react-day-picker upgrade guide](https://daypicker.dev/upgrading) -- date-fns moved to deps in v9 (HIGH confidence)
- [MLB Stats API schedule endpoint](https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=03/30/2026&hydrate=linescore,team) -- live response verified (HIGH confidence)
- [MLB-StatsAPI wiki: linescore](https://github.com/toddrob99/MLB-StatsAPI/wiki/Function:-linescore) -- Python wrapper docs (HIGH confidence)
- [MLB-StatsAPI endpoints.py](https://github.com/toddrob99/MLB-StatsAPI/blob/master/statsapi/endpoints.py) -- source code for endpoint configs (HIGH confidence)
- [GUMBO documentation](https://bdata-research-blog-prod.s3.amazonaws.com/uploads/2019/03/GUMBOPDF3-29.pdf) -- MLB live data feed spec (MEDIUM confidence, 2019 doc but format stable)
- [Native date input styling](https://dev.to/codeclown/styling-a-native-date-input-into-a-custom-no-library-datepicker-2in) -- approach reference (MEDIUM confidence)
