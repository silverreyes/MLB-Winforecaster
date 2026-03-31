# Architecture: v2.2 Game Lifecycle, Live Scores & Historical Accuracy

**Domain:** MLB pre-game win probability dashboard -- game lifecycle completion
**Researched:** 2026-03-30
**Confidence:** HIGH (existing codebase thoroughly analyzed; all integration points verified against source; MLB Stats API capabilities confirmed via library docs)

---

## Current System Architecture (Baseline)

Understanding what exists before adding anything.

### Backend (FastAPI + Postgres + APScheduler)

| Component | File(s) | Role |
|-----------|---------|------|
| FastAPI app | `api/main.py` | Lifespan (pool + artifacts), CORS, router mounting, SPA static files |
| Prediction routes | `api/routes/predictions.py` | `/predictions/today`, `/predictions/{date}`, `/predictions/latest-timestamp` |
| Accuracy route | `api/routes/accuracy.py` | `/results/accuracy` (reads static JSON metadata) |
| Health route | `api/routes/health.py` | `/health` (pipeline_runs status) |
| Pydantic models | `api/models.py` | `PredictionResponse`, `TodayResponse`, `LatestTimestampResponse`, etc. |
| SPA fallback | `api/spa.py` | `SPAStaticFiles` -- serves `index.html` for unknown paths (enables client routing) |
| DB layer | `src/pipeline/db.py` | `get_pool`, `apply_schema`, `insert_prediction`, `mark_not_latest`, pipeline_run CRUD |
| Schema | `src/pipeline/schema.sql` | `games`, `predictions`, `pipeline_runs` tables; ENUMs; indexes |
| Scheduler | `src/pipeline/scheduler.py` | `BlockingScheduler` with 3 CronTrigger jobs (10am/1pm/5pm ET) |
| Runner | `src/pipeline/runner.py` | `run_pipeline()` -- fetch/features/predict/store orchestration |
| Entry point | `scripts/run_pipeline.py` | `--once` or scheduler mode; retry logic; schema application |
| MLB data | `src/data/mlb_schedule.py` | `fetch_schedule()` (historical), `fetch_today_schedule()` (live day) |

### Frontend (React 19 + TanStack Query)

| Component | File(s) | Role |
|-----------|---------|------|
| Entry | `main.tsx` | `QueryClient` + `QueryClientProvider`; no router |
| App | `App.tsx` | Single-page: Header, AccuracyStrip, AboutModels, NewPredictionsBanner, GameCardGrid |
| API client | `api/client.ts` | `fetchJson<T>` helper; base path `/api/v1` |
| Types | `api/types.ts` | `PredictionResponse`, `TodayResponse`, `GameGroup`, etc. |
| Predictions hook | `hooks/usePredictions.ts` | Fetches `/predictions/today`; groups by matchup into `GameGroup[]` |
| Timestamp hook | `hooks/useLatestTimestamp.ts` | 60s polling of `/predictions/latest-timestamp` |
| Clock hook | `hooks/useEasternClock.ts` | Drift-corrected ET clock for header |
| GameCard | `components/GameCard.tsx` | Renders pre/post-lineup columns, SP badges, Kalshi section |

### Docker Topology

```
[Nginx :443] --> [api :8082 (512M)] --> [db :5432 (512M)]
                                              ^
               [worker (1536M)] ---------------+
               (APScheduler BlockingScheduler)
```

### Key Architectural Constraints

1. **API handlers are sync `def`** (not `async def`) because psycopg3 sync connections block the event loop if called from async context. FastAPI runs them in a thread pool.
2. **Worker uses BlockingScheduler** -- the scheduler IS the process; adding jobs is additive, not architectural change.
3. **SPA fallback already exists** -- `SPAStaticFiles` serves `index.html` for unknown paths, so client-side routing will work without backend changes.
4. **Memory ceiling** -- api container at 512M, worker at 1536M. New features must not increase baseline memory.
5. **No WebSocket infrastructure** -- all real-time updates use client-side polling. v2.2 continues this pattern.

---

## Feature 1: Game Visibility Fix

### Problem

The `/predictions/today` query filters `WHERE is_latest = TRUE`, which correctly shows the most recent prediction per game. However, games that have gone to "In Progress" or "Final" status in the MLB schedule are not explicitly filtered out -- the issue is that the schedule lookup `_build_schedule_lookup()` calls `fetch_today_schedule()` which returns all game statuses. The predictions table itself has no game status column, so games remain visible as long as predictions exist.

**Actual diagnosis from code review:** The query `WHERE game_date = CURRENT_DATE AND is_latest = TRUE` will return all predictions for today regardless of game status. The real visibility issue is likely that `fetch_today_schedule()` in the route handler only fetches game times for today's date -- if the schedule call fails, game_time becomes null but predictions still display. Games "disappearing" is more likely a frontend grouping or rendering issue, or a timezone boundary issue where `CURRENT_DATE` in Postgres (UTC) mismatches the ET calendar date.

### Architecture Decision

**What:** Add `game_status` to the API response (sourced from live schedule data, not stored in predictions table).

**Why not store status in predictions table:** Game status changes minute-by-minute during a game. The predictions table is a snapshot at prediction time. Mixing mutable game state with immutable predictions creates update pressure on a table designed for write-once semantics.

### Integration Points

| Layer | Change Type | Details |
|-------|-------------|---------|
| `api/routes/predictions.py` | MODIFY | Enhance `_build_schedule_lookup()` to include `status`, `home_score`, `away_score`, `current_inning`, `inning_state` from `statsapi.schedule()` return |
| `api/models.py` | MODIFY | Add `game_status: str \| None` field to `PredictionResponse` |
| `api/types.ts` | MODIFY | Add `game_status` to `PredictionResponse` TS type |
| `GameCard.tsx` | MODIFY | Conditionally render status badge (Scheduled/In Progress/Final) |

### Data Flow

```
Client request --> GET /predictions/today
  1. Query predictions WHERE game_date AND is_latest (unchanged)
  2. Call fetch_today_schedule() (already happens for game_time)
  3. Enrich: schedule_lookup now carries status + scores
  4. Build PredictionResponse with game_status field
  5. Return enriched response
```

**No new endpoints. No schema changes. No new tables.**

---

## Feature 2: Date Navigation

### Architecture Decision

**What:** Parameterize the existing predictions fetch by date. The backend endpoint `GET /predictions/{date}` already exists. The change is primarily frontend.

### New Backend Work: Tomorrow's Predictions

The existing pipeline runs at 10am/1pm/5pm ET for **today** only. To show tomorrow's predictions, the system needs a trigger mechanism.

**Recommended approach: On-demand prediction via API endpoint (not scheduled).**

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| Scheduled job for tomorrow | Automatic | Runs every day even if no one navigates to tomorrow; stale quickly; SP data unreliable for tomorrow | REJECT |
| API endpoint triggers prediction | Only runs when needed; can return cached result | Adds write-path to API container; needs model artifacts in API | REJECT (memory) |
| Worker-side on-demand trigger | Keeps heavy work in worker (1536M) | Needs IPC between API and worker | OVERENGINEERED |
| **Fetch schedule only for tomorrow** | Zero prediction cost; shows matchups with "Predictions available on game day" | No probabilities for tomorrow | **USE THIS** |

**Rationale:** Tomorrow's starting pitchers are frequently unknown or change overnight. Pre-game prediction with no SP confirmation has low value and may mislead. The existing `fetch_today_schedule()` pattern can be adapted to `fetch_schedule_for_date(date)` to show tomorrow's scheduled games without predictions. This is honest (no fake predictions) and zero-cost.

### Integration Points

| Layer | Change Type | Details |
|-------|-------------|---------|
| `src/data/mlb_schedule.py` | MODIFY | Add `fetch_schedule_for_date(date_str)` -- same as `fetch_today_schedule()` but parameterized |
| `api/routes/predictions.py` | MODIFY | `get_date_predictions()` now calls `fetch_schedule_for_date(date)` for schedule enrichment (game_time, status) instead of `fetch_today_schedule()` |
| `api/routes/predictions.py` | NEW LOGIC | For dates with no predictions but scheduled games, return schedule-only entries with null probabilities |
| `api/models.py` | MODIFY | Add `schedule_only: bool = False` flag to `PredictionResponse` |
| `api/types.ts` | MODIFY | Add `schedule_only` field |
| Frontend | NEW | `DateNavigator` component (left arrow, date display, right arrow, optional calendar picker) |
| `hooks/usePredictions.ts` | MODIFY | Accept `date` parameter; change queryKey to `['predictions', date]`; fetch `/predictions/{date}` instead of `/predictions/today` |
| `App.tsx` | MODIFY | Add `selectedDate` state; pass to `usePredictions` and `DateNavigator` |
| `GameCard.tsx` | MODIFY | Render "schedule only" variant when `schedule_only === true` (no probabilities, just matchup + time) |

### Date Boundaries

| Navigation Target | What to Show | Source |
|-------------------|-------------|--------|
| Past dates | Predictions + outcomes (when available) | `predictions` table via existing `/{date}` endpoint |
| Today | Full predictions + live status | Current behavior + Feature 1 enrichment |
| Tomorrow | Schedule only (matchups, times, probable pitchers) | `fetch_schedule_for_date()` via MLB Stats API |
| 2+ days out | Schedule only (less reliable) | Same as tomorrow |

### Frontend Date State

```
App.tsx
  selectedDate: string (YYYY-MM-DD, default: today)
  |
  +-- DateNavigator (arrows, display, calendar)
  |     onDateChange(newDate) --> setSelectedDate
  |
  +-- usePredictions(selectedDate)
        queryKey: ['predictions', selectedDate]
        queryFn: fetchJson(`/predictions/${selectedDate}`)
```

**No React Router needed for date navigation.** Date is state, not a route. The URL does not need to reflect the selected date for this use case (bookmarkable date URLs would be a v2.3+ enhancement using `useSearchParams`).

---

## Feature 3: Live Score Polling

### Architecture Decision: Backend Proxy, Not Client-Direct

**Decision: The FastAPI API proxies live score data. The React client does NOT call MLB Stats API directly.**

| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| Client-direct to MLB API | No backend changes | CORS issues (MLB API has no CORS headers); exposes API rate limits to N clients; no server-side caching; cannot write to Postgres on Final | REJECT |
| **Backend proxy endpoint** | CORS solved; server-side 30s cache; single upstream request per game; can write Final result to Postgres | Adds endpoint to API container | **USE THIS** |
| Worker polling loop | Can write to DB | Adds continuous load to memory-constrained worker; complex state management | REJECT |

### New Endpoint: `GET /api/v1/games/live?date=YYYY-MM-DD`

This endpoint serves a different purpose than `/predictions/{date}`. Predictions are immutable snapshots; live game data changes every pitch. Separate endpoint, separate concerns.

**Implementation:**

```python
# api/routes/live.py (NEW FILE)

@router.get("/games/live", response_model=LiveGamesResponse)
def get_live_games(request: Request, date: str = None):
    """Return live game scores for a date. Cached for 30s server-side."""
    # 1. Parse date (default: today)
    # 2. Check in-memory cache (dict keyed by date, 30s TTL)
    # 3. If cache miss: call statsapi.schedule(date=...) for all games
    # 4. For games with status "In Progress": call statsapi.get("game_linescore", {"gamePk": id})
    # 5. For games with status "Final": write outcome to Postgres (idempotent)
    # 6. Cache result, return
```

### New Pydantic Model

```python
class LiveGameData(BaseModel):
    game_id: int
    home_team: str
    away_team: str
    status: str                    # "Scheduled", "Pre-Game", "Warmup", "In Progress", "Final", etc.
    home_score: int | None
    away_score: int | None
    current_inning: int | None
    inning_state: str | None       # "Top", "Middle", "Bottom", "End"
    # Expanded view data (bases, pitcher, batter) -- optional
    on_first: bool | None
    on_second: bool | None
    on_third: bool | None
    current_pitcher: str | None
    current_batter: str | None
    balls: int | None
    strikes: int | None
    outs: int | None

class LiveGamesResponse(BaseModel):
    games: list[LiveGameData]
    cached_at: datetime
```

### Server-Side Cache Strategy

```python
# Simple dict cache in module scope (lives in API process memory)
_live_cache: dict[str, tuple[datetime, LiveGamesResponse]] = {}
_CACHE_TTL_SECONDS = 30

def _get_cached_or_fetch(date_str: str) -> LiveGamesResponse:
    now = datetime.now(timezone.utc)
    if date_str in _live_cache:
        cached_at, response = _live_cache[date_str]
        if (now - cached_at).total_seconds() < _CACHE_TTL_SECONDS:
            return response
    # Fetch fresh data...
    response = _fetch_live_from_mlb(date_str)
    _live_cache[date_str] = (now, response)
    return response
```

**Why 30s server-side cache:** Multiple browser tabs / users polling at 90s intervals. With 30s cache, the API makes at most 2 upstream MLB API calls per minute regardless of client count. The `statsapi.schedule()` call is lightweight (~50ms) and returns all games for a date in one request.

### Auto-Write Final Outcomes

When the live endpoint sees a game with `status == "Final"`, it writes the outcome to Postgres. This is the primary mechanism for outcome recording; the nightly reconciliation (Feature 4) is the safety net.

```python
def _record_final_outcome(pool, game_data: dict):
    """Write actual_winner to predictions table for a finalized game."""
    sql = """
        UPDATE predictions
        SET actual_winner = %(winner)s,
            prediction_correct = (
                CASE WHEN %(winner)s = home_team
                    THEN lr_prob > 0.5  -- simplified; real logic uses ensemble
                END
            ),
            reconciled_at = NOW()
        WHERE game_date = %(game_date)s
          AND home_team = %(home_team)s
          AND away_team = %(away_team)s
          AND actual_winner IS NULL
    """
```

### Frontend Integration

| Component | Change |
|-----------|--------|
| `api/types.ts` | Add `LiveGameData` and `LiveGamesResponse` types |
| `hooks/useLiveGames.ts` | NEW -- fetches `/games/live?date=X`; 90s refetchInterval; only active when date is today |
| `App.tsx` | Merge live game data with prediction data for display |
| `GameCard.tsx` | MODIFY -- show score, inning indicator, bases diamond when live data present |
| `components/LiveScoreOverlay.tsx` | NEW -- renders score + inning on game card; bases diamond for expanded view |

### Polling Strategy (Frontend)

```typescript
export function useLiveGames(date: string) {
  const isToday = date === getTodayET();
  return useQuery({
    queryKey: ['live-games', date],
    queryFn: () => fetchJson<LiveGamesResponse>(`/games/live?date=${date}`),
    refetchInterval: isToday ? 90_000 : false,  // 90s only for today
    refetchIntervalInBackground: false,          // respect visibilityState
    enabled: isToday,                            // don't poll for past/future dates
    staleTime: 60_000,
  });
}
```

---

## Feature 4: Outcome Reconciliation (Nightly Job)

### Architecture Decision

**What:** Add a fourth APScheduler job to the existing `BlockingScheduler`. This is purely additive -- no existing jobs are modified.

**When:** 2:00 AM ET -- after all West Coast games have concluded (latest regular season start: ~10pm ET, rarely extends past 1:30am ET).

### Integration Points

| Layer | Change Type | Details |
|-------|-------------|---------|
| `src/pipeline/schema.sql` | MODIFY | `ALTER TABLE predictions ADD COLUMN actual_winner VARCHAR(3), ADD COLUMN prediction_correct BOOLEAN, ADD COLUMN reconciled_at TIMESTAMPTZ` |
| `src/pipeline/db.py` | ADD FUNCTION | `reconcile_outcomes(pool, game_date)` -- fetches Final games from MLB API, updates predictions table |
| `src/pipeline/reconciler.py` | NEW FILE | `run_reconciliation(pool)` -- the job function |
| `src/pipeline/scheduler.py` | MODIFY | Add 4th job: `scheduler.add_job(run_reconciliation, CronTrigger(hour=2, minute=0, timezone="US/Eastern"), args=[pool], id="reconciliation")` |
| `scripts/run_pipeline.py` | MODIFY | Pass `pool` to reconciliation job (no artifacts needed) |

### Reconciliation Logic

```python
def run_reconciliation(pool):
    """Reconcile outcomes for yesterday's games (safety net for live poller)."""
    yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

    # 1. Find predictions with actual_winner IS NULL for yesterday
    # 2. Fetch final scores from statsapi.schedule(date=yesterday)
    # 3. For each Final game: UPDATE predictions SET actual_winner, prediction_correct, reconciled_at
    # 4. Log any games still not Final (rain delays, suspended games)
```

### Why a Separate Reconciler (Not Part of run_pipeline)

1. **No model artifacts needed** -- reconciliation is pure data lookup + DB update. Loading 6 model artifacts (the current `run_pipeline` prerequisite) would waste memory.
2. **Different failure mode** -- if reconciliation fails, predictions are unaffected. If it ran inside `run_pipeline`, a reconciliation error could abort the prediction pipeline.
3. **Different schedule** -- 2am ET vs 10am/1pm/5pm ET.

### prediction_correct Computation

```sql
-- For each prediction row, compare ensemble probability to actual outcome
prediction_correct = CASE
    WHEN actual_winner = home_team AND (lr_prob + rf_prob + xgb_prob) / 3 > 0.5 THEN TRUE
    WHEN actual_winner = away_team AND (lr_prob + rf_prob + xgb_prob) / 3 < 0.5 THEN TRUE
    ELSE FALSE
END
```

**Note:** This is per-row (per prediction_version). Each version (pre_lineup, post_lineup, confirmation) gets its own `prediction_correct` value, enabling accuracy comparison across pipeline runs.

### Schema Migration Strategy

The three new columns are NULLable and have no constraints. They can be added via `ALTER TABLE` in `apply_schema()` without downtime:

```sql
-- Idempotent: IF NOT EXISTS equivalent via DO block
DO $$ BEGIN
    ALTER TABLE predictions ADD COLUMN actual_winner VARCHAR(3);
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE predictions ADD COLUMN prediction_correct BOOLEAN;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE predictions ADD COLUMN reconciled_at TIMESTAMPTZ;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;
```

### New Index

```sql
CREATE INDEX IF NOT EXISTS idx_predictions_unreconciled
    ON predictions (game_date)
    WHERE actual_winner IS NULL AND is_latest = TRUE;
```

This partial index accelerates the reconciliation query (find games needing outcome data).

---

## Feature 5: History Route

### Architecture Decision: New FastAPI Endpoint + New React Route

This is the first feature requiring **client-side routing** in the frontend.

### New Backend Endpoint: `GET /api/v1/history`

**Query parameters:**
- `start_date` (required): YYYY-MM-DD
- `end_date` (required): YYYY-MM-DD
- `model` (optional): filter by prediction_version (pre_lineup, post_lineup, confirmation)

**Response:** Aggregated accuracy data + per-game prediction records.

```python
class HistoryGameRecord(BaseModel):
    game_date: date
    home_team: str
    away_team: str
    prediction_version: str
    ensemble_prob: float | None
    actual_winner: str | None
    prediction_correct: bool | None
    home_sp: str | None
    away_sp: str | None

class AccuracySummary(BaseModel):
    total_games: int
    correct_predictions: int
    accuracy_pct: float
    brier_score: float | None      # Requires actual outcome probabilities
    by_model: dict[str, dict]      # {version: {total, correct, accuracy_pct}}

class HistoryResponse(BaseModel):
    records: list[HistoryGameRecord]
    summary: AccuracySummary
    date_range: tuple[str, str]
```

### SQL Queries for History

**Per-game records:**
```sql
SELECT game_date, home_team, away_team, prediction_version,
       lr_prob, rf_prob, xgb_prob,
       (lr_prob + rf_prob + xgb_prob) / 3.0 AS ensemble_prob,
       actual_winner, prediction_correct, home_sp, away_sp
FROM predictions
WHERE game_date BETWEEN %(start_date)s AND %(end_date)s
  AND is_latest = TRUE
  AND actual_winner IS NOT NULL
ORDER BY game_date DESC, home_team
```

**Rolling accuracy by model (per prediction_version):**
```sql
SELECT prediction_version,
       COUNT(*) AS total_games,
       SUM(CASE WHEN prediction_correct THEN 1 ELSE 0 END) AS correct,
       ROUND(
           SUM(CASE WHEN prediction_correct THEN 1 ELSE 0 END)::numeric
           / NULLIF(COUNT(*), 0) * 100, 1
       ) AS accuracy_pct
FROM predictions
WHERE game_date BETWEEN %(start_date)s AND %(end_date)s
  AND is_latest = TRUE
  AND actual_winner IS NOT NULL
GROUP BY prediction_version
ORDER BY prediction_version
```

**Brier score computation (per prediction_version):**
```sql
SELECT prediction_version,
       AVG(
           POWER(
               (lr_prob + rf_prob + xgb_prob) / 3.0
               - CASE WHEN actual_winner = home_team THEN 1.0 ELSE 0.0 END,
               2
           )
       ) AS brier_score
FROM predictions
WHERE game_date BETWEEN %(start_date)s AND %(end_date)s
  AND is_latest = TRUE
  AND actual_winner IS NOT NULL
GROUP BY prediction_version
```

### Frontend Routing Setup

**Install react-router:**

```bash
npm install react-router
```

**Minimal router setup (no framework mode):**

```typescript
// main.tsx
import { createBrowserRouter, RouterProvider } from 'react-router';

const router = createBrowserRouter([
  { path: '/', element: <App /> },
  { path: '/history', element: <HistoryPage /> },
]);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
```

**Why this works with the existing backend:** The `SPAStaticFiles` class in `api/spa.py` already catches unknown paths and serves `index.html`. When a user navigates to `/history`, Nginx forwards to the API, the API finds no static file at `/history`, and falls back to `index.html`, which loads the React app, which reads the URL and renders the `HistoryPage` component. Zero backend routing changes needed.

### New Frontend Components

| Component | Purpose |
|-----------|---------|
| `HistoryPage.tsx` | Top-level page: date range picker + accuracy summary + records table |
| `DateRangePicker.tsx` | Start/end date inputs (native `<input type="date">` -- no library needed) |
| `AccuracySummaryCard.tsx` | Displays overall accuracy, Brier score, per-model breakdown |
| `HistoryTable.tsx` | Sortable table of prediction records with outcome markers |
| `hooks/useHistory.ts` | TanStack Query hook for `/history?start_date=X&end_date=Y` |
| `NavBar.tsx` | Minimal navigation: "Today" | "History" links (shared across pages) |

---

## New vs Modified Components Summary

### New Files

| File | Layer | Purpose |
|------|-------|---------|
| `api/routes/live.py` | Backend | Live game scores endpoint + server cache + Final outcome writer |
| `api/routes/history.py` | Backend | History endpoint with date range, accuracy aggregation |
| `src/pipeline/reconciler.py` | Backend | Nightly reconciliation job logic |
| `frontend/src/hooks/useLiveGames.ts` | Frontend | Live game polling hook |
| `frontend/src/hooks/useHistory.ts` | Frontend | History data fetch hook |
| `frontend/src/components/LiveScoreOverlay.tsx` | Frontend | Score + inning display on game cards |
| `frontend/src/components/DateNavigator.tsx` | Frontend | Date arrows + display for navigation |
| `frontend/src/components/HistoryPage.tsx` | Frontend | History route page |
| `frontend/src/components/DateRangePicker.tsx` | Frontend | Date range inputs for history |
| `frontend/src/components/AccuracySummaryCard.tsx` | Frontend | Accuracy metrics display |
| `frontend/src/components/HistoryTable.tsx` | Frontend | Prediction records table |
| `frontend/src/components/NavBar.tsx` | Frontend | Top-level navigation (Today / History) |

### Modified Files

| File | Layer | Changes |
|------|-------|---------|
| `src/pipeline/schema.sql` | Backend | Add 3 columns (actual_winner, prediction_correct, reconciled_at) + new index |
| `src/pipeline/db.py` | Backend | Add `reconcile_outcomes()`, `record_final_outcome()` functions |
| `src/pipeline/scheduler.py` | Backend | Add 4th CronTrigger job (reconciliation at 2am ET) |
| `src/data/mlb_schedule.py` | Backend | Add `fetch_schedule_for_date(date_str)` parameterized function |
| `api/main.py` | Backend | Register `live_router` and `history_router` |
| `api/models.py` | Backend | Add `LiveGameData`, `LiveGamesResponse`, `HistoryGameRecord`, `AccuracySummary`, `HistoryResponse` models; modify `PredictionResponse` |
| `api/routes/predictions.py` | Backend | Enhance schedule lookup with status/scores; support schedule-only entries |
| `frontend/src/main.tsx` | Frontend | Add `createBrowserRouter` + `RouterProvider`; move `QueryClientProvider` to wrap router |
| `frontend/src/App.tsx` | Frontend | Add `selectedDate` state; integrate `DateNavigator`; merge live game data |
| `frontend/src/api/types.ts` | Frontend | Add `LiveGameData`, `LiveGamesResponse`, `HistoryResponse` types; modify `PredictionResponse` |
| `frontend/src/hooks/usePredictions.ts` | Frontend | Accept `date` parameter; dynamic queryKey |
| `frontend/src/components/GameCard.tsx` | Frontend | Show live scores, game status, outcome markers |
| `frontend/package.json` | Frontend | Add `react-router` dependency |

### Unchanged (Explicitly)

| Component | Why Unchanged |
|-----------|---------------|
| `src/pipeline/runner.py` | Prediction pipeline logic untouched; reconciliation is a separate job |
| `src/pipeline/inference.py` | Model loading and prediction unchanged |
| `src/pipeline/live_features.py` | Feature building unchanged |
| `src/pipeline/health.py` | Health endpoint unchanged |
| `scripts/run_pipeline.py` | Entry point unchanged (scheduler picks up new job automatically) |
| Model artifacts | No retraining needed |
| `docker-compose.yml` | No new containers; no memory limit changes |
| `Dockerfile` | No new dependencies that require system packages |

---

## Recommended Build Order

The features have dependencies. Build in this order:

### Phase 1: Schema + Game Visibility Fix (Foundation)

**Depends on:** Nothing
**Enables:** Features 3, 4, 5

1. Add 3 new columns to `schema.sql` (idempotent ALTER TABLE)
2. Add new index for unreconciled predictions
3. Add `fetch_schedule_for_date()` to `mlb_schedule.py`
4. Enhance `_build_schedule_lookup()` to include status/scores
5. Add `game_status` to `PredictionResponse` (backend + frontend)
6. Update `GameCard.tsx` to show game status badge

**Why first:** The schema migration is the foundation for Features 3, 4, and 5. The game visibility fix is the simplest change and validates the schedule enrichment pattern used by all subsequent features.

### Phase 2: Date Navigation (Frontend-Heavy)

**Depends on:** Phase 1 (schedule enrichment)
**Enables:** Feature 5 (establishes date parameter pattern)

1. Add `DateNavigator` component
2. Modify `usePredictions` to accept date parameter
3. Add `schedule_only` flag for future dates
4. Modify `GameCard` to handle schedule-only rendering
5. Wire date state through `App.tsx`

**Why second:** Establishes the date-parameterized data flow that history will also use. Pure frontend change (backend date endpoint already exists).

### Phase 3: Live Score Polling (New Endpoint)

**Depends on:** Phase 1 (schema columns for outcome writing), Phase 2 (date parameterization)
**Enables:** Feature 4 (live poller writes outcomes that reconciler verifies)

1. Create `api/routes/live.py` with server-side cache
2. Add `LiveGameData` / `LiveGamesResponse` Pydantic models
3. Implement MLB Stats API calls for live scores
4. Implement auto-write of Final outcomes to Postgres
5. Register live router in `api/main.py`
6. Create `useLiveGames` hook
7. Create `LiveScoreOverlay` component
8. Integrate live data into `GameCard`

**Why third:** This is the most complex new feature. Having the schema and date navigation in place means the live poller has a target to write to and a UI framework to display in.

### Phase 4: Nightly Reconciliation (Backend-Only)

**Depends on:** Phase 1 (schema columns), Phase 3 (live poller sets the primary outcome path)
**Enables:** Feature 5 (history page needs reconciled outcomes)

1. Create `src/pipeline/reconciler.py`
2. Add `reconcile_outcomes()` to `db.py`
3. Add 4th job to `scheduler.py`
4. Test with `--once reconciliation` flag

**Why fourth:** The reconciler is a safety net for the live poller. It needs the schema in place (Phase 1) and the live outcome writing pattern established (Phase 3) so it can fill gaps rather than duplicate work.

### Phase 5: History Route (Full-Stack)

**Depends on:** Phase 1 (schema), Phase 4 (reconciled data to display)
**Enables:** Nothing (terminal feature)

1. Create `api/routes/history.py` with aggregation queries
2. Add history Pydantic models
3. Register history router
4. Install `react-router`; set up `createBrowserRouter` in `main.tsx`
5. Create `HistoryPage`, `DateRangePicker`, `AccuracySummaryCard`, `HistoryTable`
6. Create `useHistory` hook
7. Add `NavBar` component for page navigation

**Why last:** Requires reconciled outcome data to be meaningful. All other features must be in place first.

---

## Scalability Considerations

| Concern | Current (Day 1) | Season Midpoint (~1K games) | Full Season (~2.4K games) |
|---------|-----------------|----------------------------|--------------------------|
| Predictions table rows | ~50/day (15 games x 3 versions + updates) | ~7.5K rows | ~18K rows |
| History query | <100 rows | Indexed scan, <50ms | Indexed scan, <100ms |
| Live polling load | 15 games, 1 API call/30s | Same (server cache) | Same |
| Memory (API) | ~200MB baseline | No growth (no caching of history) | No growth |
| Memory (Worker) | ~800MB peak during pipeline | No growth (reconciler is lightweight) | No growth |

The predictions table will not need partitioning or archival within a single MLB season. With ~18K rows and proper indexes, all queries complete in single-digit milliseconds.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Storing Mutable Game State in Predictions Table
**What:** Adding columns like `current_inning`, `home_score` to the predictions table and updating them during games.
**Why bad:** Predictions are write-once snapshots. Updating them with live data mixes concerns, creates update contention, and makes the table's semantics ambiguous (is this row a prediction or a game record?).
**Instead:** Serve live game data from a separate endpoint that reads from MLB Stats API with server-side caching. Write only final outcomes (actual_winner, prediction_correct) once.

### Anti-Pattern 2: WebSocket for Live Scores
**What:** Adding WebSocket infrastructure for real-time score pushes.
**Why bad:** The project already established client-side polling as the pattern (v2.0 decision, documented in Out of Scope). Adding WebSocket requires new infrastructure (different Gunicorn worker type, sticky sessions, reconnection logic). The 90s polling interval for live scores does not justify the complexity.
**Instead:** Continue the polling pattern with TanStack Query's `refetchInterval`.

### Anti-Pattern 3: Running Predictions for Tomorrow
**What:** Scheduling or triggering model inference for tomorrow's games.
**Why bad:** Tomorrow's SP assignments are unreliable (change overnight, day-of scratches common). Running TEAM_ONLY predictions without SP data provides marginal value and may mislead users. Memory-constrained worker (1536M) should not run additional inference passes.
**Instead:** Show schedule-only view for future dates with explicit "Predictions available on game day" messaging.

### Anti-Pattern 4: Separate Database for Live Game Data
**What:** Adding Redis or a second Postgres database for live game state.
**Why bad:** Adds operational complexity (another container, another backup target, another failure point) for data that is cached in-memory for 30 seconds and thrown away.
**Instead:** In-memory dict cache in the API process. Zero infrastructure additions.

---

## Sources

- [MLB-StatsAPI PyPI](https://pypi.org/project/MLB-StatsAPI/) -- Python wrapper for MLB Stats API (already in requirements.txt as `MLB-StatsAPI==1.9.0`)
- [MLB-StatsAPI Endpoints Wiki](https://github.com/toddrob99/MLB-StatsAPI/wiki/Endpoints) -- game, game_linescore, game_boxscore, schedule endpoints
- [MLB-StatsAPI schedule() Function](https://github.com/toddrob99/MLB-StatsAPI/wiki/Function:-schedule) -- returns game_id, status, home_score, away_score, current_inning, inning_state
- [MLB-StatsAPI linescore() Function](https://github.com/toddrob99/MLB-StatsAPI/wiki/Function:-linescore) -- inning-by-inning scoring with gamePk parameter
- [APScheduler 3.x Interval Trigger](https://apscheduler.readthedocs.io/en/3.x/modules/triggers/interval.html) -- multiple trigger types on one scheduler
- [APScheduler 3.x User Guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html) -- BlockingScheduler with mixed CronTrigger + IntervalTrigger jobs
- [React Router v7 Installation](https://reactrouter.com/start/library/installation) -- library mode for existing Vite/React apps
- [TanStack Query + React Router Example](https://tanstack.com/query/latest/docs/framework/react/examples/react-router) -- integration patterns
- [React Router v7 Guide (LogRocket)](https://blog.logrocket.com/react-router-v7-guide/) -- createBrowserRouter setup for React 19
