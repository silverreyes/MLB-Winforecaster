# Phase 13: Schema Migration & Game Visibility - Research

**Researched:** 2026-03-30
**Domain:** PostgreSQL schema migration, FastAPI endpoint design, MLB Stats API game status, React/TanStack Query data layer
**Confidence:** HIGH

## Summary

Phase 13 has two parallel tracks: (1) an additive PostgreSQL migration adding `game_id` and reconciliation columns to the `predictions` table, and (2) a new `/games/{date}` endpoint that merges MLB schedule data with predictions to show all games on the dashboard with status badges.

The migration is straightforward -- PostgreSQL supports `ADD COLUMN IF NOT EXISTS` and `DROP CONSTRAINT IF EXISTS` for fully idempotent DDL. The existing `apply_schema()` pattern in `db.py` already handles idempotent enum creation. The migration adds 4 columns and rebuilds one unique constraint.

The visibility track requires replacing the `statsapi.schedule()` wrapper with `statsapi.get('schedule', ...)` to access `abstractGameState` and `codedGameState` -- the wrapper only exposes `detailedState`. A critical finding: postponed games have `abstractGameState: "Final"` (not "Preview"), so `codedGameState == "D"` is required to distinguish postponed from truly final games. The new `/games/{date}` endpoint merges schedule data with prediction rows, returning a unified `GameResponse` list that the frontend consumes via a new `useGames()` hook.

**Primary recommendation:** Build migration SQL as a separate `migration_001.sql` file executed by `apply_schema()` after the main schema, then build the `/games/{date}` endpoint using `statsapi.get('schedule', ...)` with an in-memory TTL cache per date.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- When a game is scheduled but has no prediction row: show a minimal stub card -- matchup names, game time, and status badge. No probability numbers, no edge signal. The stub card uses the same card shell as a prediction card; probability areas are simply absent/empty.
- Postponed games stay visible with a POSTPONED badge -- they do not disappear from the grid.
- Status badge (PRE-GAME / LIVE / FINAL / POSTPONED) appears on every card, both stub and prediction cards.
- Badge is live -- updates on existing 60s prediction-poll interval. No extra polling needed.
- Status source: `abstractGameState` from MLB Stats API (3 values: Preview -> PRE-GAME, Live -> LIVE, Final -> FINAL). POSTPONED detected via `codedGameState` or `detailedState`.
- Add `GET /api/v1/games/{date}` -- date-parameterized from the start so Phase 14 can use it.
- Existing `/predictions/today` remains unchanged.
- Frontend switches to `/games/{date}` as primary data source, defaulting to today's date.
- Schedule response cached in-memory with 60-90s TTL per date.
- New `GameResponse` type: `{ game_id, home_team, away_team, game_time, game_status, prediction: PredictionGroup | null }`.
- `game_id` (gamePk) is always present and non-nullable in GameResponse. If undetermined, exclude the game.
- `game_status` is always a string: `'PRE_GAME' | 'LIVE' | 'FINAL' | 'POSTPONED'`.
- Migrations are idempotent ALTER TABLE IF NOT EXISTS / ADD COLUMN IF NOT EXISTS statements.
- Applied in `apply_schema()` at container startup.
- SCHM-01: Add `game_id INTEGER`, drop existing `uq_prediction`, add new `uq_prediction` that includes `game_id`. Existing rows get `game_id = NULL`.
- SCHM-02: Add nullable `actual_winner TEXT`, `prediction_correct BOOLEAN`, `reconciled_at TIMESTAMPTZ`.
- Reconciliation columns excluded from the pipeline UPSERT column list.

### Claude's Discretion
- Exact visual treatment of stub card vs prediction card (dim vs omit probability area)
- In-memory cache implementation detail (module-level dict + timestamp vs. functools.lru_cache)
- Exact SQL for constraint drop-and-recreate (concurrent-safe approach if applicable)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SCHM-01 | Predictions table gains `game_id` column (integer); unique constraint updated to include `game_id` to prevent doubleheader row collision -- applied via idempotent migration | PostgreSQL `ADD COLUMN IF NOT EXISTS` and `DROP CONSTRAINT IF EXISTS` syntax verified; migration SQL pattern documented; pipeline `_PREDICTION_COLS` must be updated |
| SCHM-02 | Predictions table gains additive nullable columns: `actual_winner` (text), `prediction_correct` (boolean), `reconciled_at` (timestamp) -- applied via idempotent migration | Same DDL pattern; columns MUST be excluded from `_PREDICTION_UPDATE_COLS` to prevent pipeline UPSERT from overwriting reconciliation data |
| VIBL-01 | All games scheduled for the selected date remain visible on the dashboard regardless of game status | New `/games/{date}` endpoint merges MLB schedule (via `statsapi.get`) with prediction rows; stub cards (prediction: null) shown for games without predictions |
| VIBL-02 | Each game card displays a status badge showing current state (PRE-GAME / LIVE / FINAL / POSTPONED) | Status derived from `abstractGameState` + `codedGameState` in raw API; mapping: Preview->PRE_GAME, Live->LIVE, Final+codedD->POSTPONED, Final+else->FINAL |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PostgreSQL | 16 | Database -- schema migration target | Already running in docker-compose as `postgres:16-bookworm` |
| psycopg | 3.3.3 | Python Postgres driver | Already in use by `src/pipeline/db.py` |
| psycopg_pool | (bundled) | Connection pooling | Already in use |
| FastAPI | (existing) | API framework | Already serving `/api/v1/predictions/*` |
| Pydantic | (existing) | Response model validation | Already in use in `api/models.py` |
| MLB-StatsAPI | 1.9.0 | MLB Stats API wrapper | Already in use by `src/data/mlb_schedule.py` |
| @tanstack/react-query | 5.95.2 | Frontend data fetching/polling | Already in use by `usePredictions.ts` |
| React | 19.2.4 | Frontend UI framework | Already in use |
| TypeScript | ~5.9.3 | Frontend type system | Already in use |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `time` (stdlib) | N/A | TTL cache timestamp | In-memory schedule cache expiry |
| `threading.Lock` (stdlib) | N/A | Thread-safe cache access | FastAPI runs sync handlers in thread pool; concurrent requests to same date need lock |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Module-level dict + TTL cache | `functools.lru_cache` | `lru_cache` has no TTL; we need 60-90s expiry to get fresh status updates. Module-level dict wins. |
| `statsapi.schedule()` wrapper | `statsapi.get('schedule', ...)` raw | Wrapper strips `abstractGameState` and `codedGameState`. Raw API required for status badge. |
| Alembic migration framework | Inline SQL in `apply_schema()` | Only 2 migrations needed; Alembic adds dependency complexity. Inline SQL with IF NOT EXISTS is simpler. |

**No new packages required.** All dependencies are already installed.

## Architecture Patterns

### Recommended Project Structure
```
api/
  routes/
    games.py           # NEW: GET /games/{date} route
    predictions.py     # UNCHANGED: existing prediction routes
  models.py            # UPDATED: add GameResponse, PredictionGroup
  main.py              # UPDATED: register games router
src/
  pipeline/
    schema.sql         # UNCHANGED: base schema stays as-is
    migration_001.sql  # NEW: Phase 13 migration (game_id + reconciliation columns)
    db.py              # UPDATED: apply_schema() runs migrations, _PREDICTION_COLS updated
  data/
    mlb_schedule.py    # UPDATED: add fetch_schedule_for_date() using raw API
frontend/
  src/
    api/
      types.ts         # UPDATED: add GameResponse, GamesResponse types
    hooks/
      useGames.ts      # NEW: replaces usePredictions as primary data source
    components/
      StatusBadge.tsx   # NEW: PRE-GAME / LIVE / FINAL / POSTPONED badge
      GameCard.tsx      # UPDATED: accept GameResponse, show badge, handle null prediction
      GameCardGrid.tsx  # UPDATED: accept GameResponse[] instead of GameGroup[]
    App.tsx             # UPDATED: use useGames() instead of usePredictions()
```

### Pattern 1: Idempotent Migration via `apply_schema()`
**What:** Migration SQL uses `ADD COLUMN IF NOT EXISTS` and `DROP CONSTRAINT IF EXISTS` so it can be re-run safely on every container start.
**When to use:** Always -- the worker container calls `apply_schema(pool)` on every startup.
**Example:**
```sql
-- Source: PostgreSQL 16 ALTER TABLE documentation
-- SCHM-01: Add game_id column
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS game_id INTEGER;

-- Drop old unique constraint and create new one including game_id
ALTER TABLE predictions DROP CONSTRAINT IF EXISTS uq_prediction;
ALTER TABLE predictions ADD CONSTRAINT uq_prediction
    UNIQUE (game_date, home_team, away_team, prediction_version, is_latest, game_id);

-- SCHM-02: Add reconciliation columns
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS actual_winner TEXT;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS prediction_correct BOOLEAN;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS reconciled_at TIMESTAMPTZ;

-- Index for reconciliation queries (Phase 16)
CREATE INDEX IF NOT EXISTS idx_predictions_game_id ON predictions (game_id)
    WHERE game_id IS NOT NULL;
```

### Pattern 2: Raw MLB Stats API for Status Fields
**What:** Use `statsapi.get('schedule', params)` instead of `statsapi.schedule()` to access `abstractGameState` and `codedGameState`.
**When to use:** The `/games/{date}` endpoint needs these fields for status badge mapping.
**Example:**
```python
# Source: verified against MLB Stats API on 2026-03-30
import statsapi

def fetch_schedule_for_date(date_str: str) -> list[dict]:
    """Fetch MLB schedule using raw API to get status fields.

    Args:
        date_str: Date in YYYY-MM-DD format.

    Returns:
        List of game dicts with game_id, teams, status fields, game_time.
    """
    # statsapi.get expects MM/DD/YYYY format
    from datetime import datetime
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    api_date = dt.strftime("%m/%d/%Y")

    data = statsapi.get('schedule', {
        'sportId': 1,
        'date': api_date,
    })

    games = []
    for date_entry in data.get('dates', []):
        for game in date_entry.get('games', []):
            if game.get('gameType') != 'R':
                continue  # Regular season only

            status = game.get('status', {})
            abstract_state = status.get('abstractGameState', 'Preview')
            coded_state = status.get('codedGameState', 'S')

            # Map to badge status
            if coded_state == 'D':
                game_status = 'POSTPONED'
            elif abstract_state == 'Final':
                game_status = 'FINAL'
            elif abstract_state == 'Live':
                game_status = 'LIVE'
            else:
                game_status = 'PRE_GAME'

            games.append({
                'game_id': game['gamePk'],
                'home_name': game['teams']['home']['team']['name'],
                'away_name': game['teams']['away']['team']['name'],
                'game_datetime': game['gameDate'],
                'game_status': game_status,
                'doubleheader': game.get('doubleHeader', 'N'),
                'game_num': game.get('gameNumber', 1),
            })

    return games
```

### Pattern 3: In-Memory TTL Cache
**What:** Module-level dict with per-date TTL for schedule data. Thread-safe via Lock.
**When to use:** Cache schedule API responses to avoid hitting MLB API on every 60s poll cycle.
**Example:**
```python
import time
import threading

_schedule_cache: dict[str, tuple[float, list[dict]]] = {}
_cache_lock = threading.Lock()
_CACHE_TTL_SECONDS = 75  # 60-90s range per CONTEXT.md

def get_schedule_cached(date_str: str) -> list[dict]:
    """Return cached schedule, fetching fresh if expired."""
    now = time.monotonic()
    with _cache_lock:
        if date_str in _schedule_cache:
            ts, data = _schedule_cache[date_str]
            if now - ts < _CACHE_TTL_SECONDS:
                return data

    # Fetch fresh data outside the lock
    fresh = fetch_schedule_for_date(date_str)
    with _cache_lock:
        _schedule_cache[date_str] = (now, fresh)
    return fresh
```

### Pattern 4: GameResponse Merge Logic
**What:** The `/games/{date}` endpoint merges schedule data with prediction rows, producing one `GameResponse` per game.
**When to use:** This is the core logic of the endpoint.
**Example:**
```python
def build_games_response(schedule: list[dict], predictions: list[dict]) -> list[GameResponse]:
    """Merge schedule games with prediction rows.

    - Games with predictions: game_id from schedule or db, prediction populated
    - Games without predictions: stub card (prediction = null)
    - Predictions without schedule match: still included (shouldn't happen but safe)
    """
    # Build prediction lookup: (home_team, away_team, game_id) -> predictions
    pred_by_game_id = {}
    pred_by_teams = {}
    for p in predictions:
        gid = p.get('game_id')
        if gid:
            pred_by_game_id.setdefault(gid, []).append(p)
        else:
            key = (p['home_team'], p['away_team'])
            pred_by_teams.setdefault(key, []).append(p)

    results = []
    matched_pred_ids = set()

    for game in schedule:
        game_id = game['game_id']
        home = normalize_team(game['home_name'])
        away = normalize_team(game['away_name'])

        # Try game_id match first, then team match
        preds = pred_by_game_id.get(game_id, [])
        if not preds:
            preds = pred_by_teams.get((home, away), [])

        # Build PredictionGroup from matched predictions
        prediction_group = _build_prediction_group(preds) if preds else None

        results.append(GameResponse(
            game_id=game_id,
            home_team=home,
            away_team=away,
            game_time=game['game_datetime'],
            game_status=game['game_status'],
            prediction=prediction_group,
        ))

    return results
```

### Anti-Patterns to Avoid
- **Using `statsapi.schedule()` for status detection:** The wrapper only exposes `detailedState` in its `status` field, which has 127+ values. Use `statsapi.get('schedule', ...)` to access `abstractGameState` and `codedGameState`.
- **Assuming postponed games have `abstractGameState: "Preview"`:** They have `"Final"`. Must check `codedGameState == "D"` for postponed detection.
- **Adding reconciliation columns to `_PREDICTION_UPDATE_COLS`:** The pipeline UPSERT would overwrite values written by Phase 16's reconciliation. These columns must be excluded from the update set.
- **Grouping by `(home_team, away_team)` without `game_id`:** Doubleheaders have the same teams twice. The new endpoint uses `game_id` as the primary key for game identity.
- **Dropping the `uq_prediction` constraint without IF EXISTS:** On first container start, constraint exists. On subsequent starts with new code, it needs to be droppable idempotently.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Schedule API parsing | Custom HTTP client for MLB API | `statsapi.get('schedule', params)` | Already installed, handles base URL, auth, error handling |
| Team name normalization | Manual team name mapping | `normalize_team()` from `src/data/team_mappings.py` | Already handles 100+ variants, battle-tested |
| Date format conversion | Custom date parsing | `datetime.strptime` / `strftime` | Stdlib handles YYYY-MM-DD <-> MM/DD/YYYY |
| Frontend data fetching | Custom fetch + useState | TanStack React Query `useQuery` | Already configured with 60s polling, handles stale/error states |
| API response validation | Manual dict construction | Pydantic `BaseModel` | Already the pattern for all existing endpoints |

**Key insight:** Phase 13 adds no new dependencies. Every tool needed already exists in the codebase or stdlib.

## Common Pitfalls

### Pitfall 1: Postponed Games Have abstractGameState "Final"
**What goes wrong:** Developer maps `abstractGameState == "Final"` to FINAL badge. Postponed games show FINAL instead of POSTPONED.
**Why it happens:** MLB's status taxonomy puts postponed games under `abstractGameState: "Final"` with `codedGameState: "D"`. This is counterintuitive.
**How to avoid:** Always check `codedGameState` first: if `"D"` -> POSTPONED, else if `abstractGameState == "Final"` -> FINAL.
**Warning signs:** Postponed games showing "FINAL" badge with no score.

### Pitfall 2: Unique Constraint Migration With NULL game_id
**What goes wrong:** Old rows have `game_id = NULL`. PostgreSQL treats NULLs as distinct in UNIQUE constraints. Two rows for the same game/version/is_latest with `game_id = NULL` would NOT violate the unique constraint.
**Why it happens:** Adding a nullable column to a unique constraint means the constraint is effectively weakened for existing rows where the column is NULL.
**How to avoid:** This is actually acceptable for Phase 13. Existing rows predate doubleheader-aware inserts. New rows written by the updated pipeline will always include `game_id`. The constraint prevents NEW doubleheader collisions. Old rows are grandfathered. However, document this behavior so Phase 16 reconciliation doesn't expect uniqueness on old rows.
**Warning signs:** Multiple prediction rows for the same pre-game_id matchup on the same day (expected for historical data).

### Pitfall 3: Pipeline UPSERT Must Include game_id
**What goes wrong:** After adding `game_id` to the unique constraint, the `ON CONFLICT ON CONSTRAINT uq_prediction` clause in `insert_prediction()` requires `game_id` in the INSERT column list. If `game_id` is not provided, the UPSERT may insert duplicates instead of updating.
**Why it happens:** The unique constraint now includes `game_id`. If the insert doesn't include `game_id`, PostgreSQL compares NULL (omitted) against NULL (existing) -- and NULLs are not equal, so no conflict is detected.
**How to avoid:** Add `game_id` to `_PREDICTION_COLS` in `db.py`. Pass `game_id` from `game["game_id"]` in all `insert_prediction()` calls in `runner.py`. This is the most critical integration point.
**Warning signs:** Duplicate prediction rows appearing after migration.

### Pitfall 4: Thread-Safety of Schedule Cache
**What goes wrong:** Multiple FastAPI threads (sync handlers run in thread pool) read/write the cache dict concurrently, causing race conditions or stale reads.
**Why it happens:** FastAPI runs sync `def` handlers in a thread pool. Multiple concurrent requests for the same date could race on cache check and fetch.
**How to avoid:** Use `threading.Lock` around cache reads and writes. Keep the lock duration short (just dict operations, not the API call). Fetch fresh data outside the lock, then store under lock.
**Warning signs:** Occasional duplicate API calls or stale data served intermittently.

### Pitfall 5: Frontend Key Collision for Doubleheaders
**What goes wrong:** `GameCardGrid` currently uses `${game.away_team}-${game.home_team}` as React key. Doubleheaders produce two cards with the same key.
**Why it happens:** The old `GameGroup` type had no `game_id` field. The new `GameResponse` does.
**How to avoid:** Use `game_id` (which is `gamePk`, always unique) as the React key: `key={game.game_id}`.
**Warning signs:** React console warning about duplicate keys; only one card rendering for a doubleheader.

### Pitfall 6: statsapi.schedule() Returns detailedState as "status"
**What goes wrong:** Developer reads `fetch_today_schedule()` output, sees `status: "Final"`, thinks it covers all final states. It does not -- "Game Over", "Final: Rain", etc. are separate `detailedState` values.
**Why it happens:** The `statsapi.schedule()` Python wrapper maps `game["status"]["detailedState"]` to its `status` field (verified in source code inspection). It does NOT expose `abstractGameState` or `codedGameState`.
**How to avoid:** The new `fetch_schedule_for_date()` function uses `statsapi.get('schedule', ...)` which returns the raw JSON including `status.abstractGameState`, `status.codedGameState`, and `status.detailedState`.
**Warning signs:** Games stuck in wrong badge state; "Game Over" games not showing FINAL.

## Code Examples

### Migration SQL (Verified Pattern)
```sql
-- Source: PostgreSQL 16 ALTER TABLE documentation
-- Phase 13 Migration: game_id + reconciliation columns

-- SCHM-01: game_id column
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS game_id INTEGER;

-- SCHM-01: Rebuild unique constraint to include game_id
ALTER TABLE predictions DROP CONSTRAINT IF EXISTS uq_prediction;
ALTER TABLE predictions ADD CONSTRAINT uq_prediction
    UNIQUE (game_date, home_team, away_team, prediction_version, is_latest, game_id);

-- SCHM-02: Reconciliation columns
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS actual_winner TEXT;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS prediction_correct BOOLEAN;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS reconciled_at TIMESTAMPTZ;

-- Performance index for game_id lookups
CREATE INDEX IF NOT EXISTS idx_predictions_game_id ON predictions (game_id)
    WHERE game_id IS NOT NULL;
```

### Updated _PREDICTION_COLS in db.py
```python
# Source: existing db.py pattern
_PREDICTION_COLS = [
    "game_date", "home_team", "away_team", "prediction_version",
    "prediction_status", "lr_prob", "rf_prob", "xgb_prob", "feature_set",
    "home_sp", "away_sp", "sp_uncertainty", "sp_may_have_changed",
    "kalshi_yes_price", "edge_signal", "is_latest",
    "game_id",  # NEW: Phase 13 SCHM-01
]

# Reconciliation columns deliberately excluded from update set:
# actual_winner, prediction_correct, reconciled_at
# This prevents the pipeline UPSERT from overwriting Phase 16 writes.
_PREDICTION_UPDATE_COLS = [
    "prediction_status", "lr_prob", "rf_prob", "xgb_prob", "feature_set",
    "home_sp", "away_sp", "sp_uncertainty", "sp_may_have_changed",
    "kalshi_yes_price", "edge_signal",
]
```

### Pydantic Models for /games/{date}
```python
# Source: existing api/models.py patterns
from pydantic import BaseModel
from datetime import date, datetime
from typing import Literal

class PredictionGroup(BaseModel):
    """Pre-lineup and/or post-lineup predictions for a single game."""
    pre_lineup: PredictionResponse | None = None
    post_lineup: PredictionResponse | None = None

class GameResponse(BaseModel):
    """Single game entry for the /games/{date} endpoint."""
    game_id: int
    home_team: str
    away_team: str
    game_time: datetime | None
    game_status: Literal['PRE_GAME', 'LIVE', 'FINAL', 'POSTPONED']
    prediction: PredictionGroup | None = None

class GamesDateResponse(BaseModel):
    """Response shape for GET /games/{date}."""
    games: list[GameResponse]
    generated_at: datetime
```

### Frontend GameResponse Type
```typescript
// Source: existing frontend/src/api/types.ts pattern

export type GameStatus = 'PRE_GAME' | 'LIVE' | 'FINAL' | 'POSTPONED';

export interface PredictionGroup {
  pre_lineup: PredictionResponse | null;
  post_lineup: PredictionResponse | null;
}

export interface GameResponse {
  game_id: number;
  home_team: string;
  away_team: string;
  game_time: string | null;
  game_status: GameStatus;
  prediction: PredictionGroup | null;
}

export interface GamesDateResponse {
  games: GameResponse[];
  generated_at: string;
}
```

### Status Badge Component Pattern
```tsx
// Source: component architecture from existing SpBadge.tsx pattern
interface StatusBadgeProps {
  status: GameStatus;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span className={`${styles.badge} ${styles[status.toLowerCase()]}`}>
      {status.replace('_', '-')}
    </span>
  );
}
```

### Status Mapping Logic (Critical)
```python
# Source: verified against https://statsapi.mlb.com/api/v1/gameStatus on 2026-03-30
def map_game_status(status_obj: dict) -> str:
    """Map MLB status object to badge status.

    Args:
        status_obj: The 'status' dict from raw schedule API containing
                    abstractGameState, codedGameState, detailedState.

    Returns:
        One of: 'PRE_GAME', 'LIVE', 'FINAL', 'POSTPONED'
    """
    coded = status_obj.get('codedGameState', 'S')
    abstract = status_obj.get('abstractGameState', 'Preview')

    # Check postponed FIRST -- codedGameState "D" overrides abstractGameState "Final"
    if coded == 'D':
        return 'POSTPONED'

    if abstract == 'Final':
        return 'FINAL'
    elif abstract == 'Live':
        return 'LIVE'
    else:
        return 'PRE_GAME'
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `statsapi.schedule()` for status | `statsapi.get('schedule', ...)` for raw status fields | Phase 13 | Required for `abstractGameState` + `codedGameState` access |
| Team-pair grouping `(home, away)` | `game_id` (gamePk) as primary key | Phase 13 | Fixes doubleheader collisions in predictions table and frontend |
| `/predictions/today` as sole dashboard data source | `/games/{date}` as primary, `/predictions/today` retained | Phase 13 | Games without predictions become visible |

**Deprecated/outdated:**
- `GameGroup` TypeScript type: Superseded by `GameResponse` for the dashboard. Retained for backwards compatibility with `/predictions/today` but the primary dashboard uses `GameResponse`.
- `usePredictions()` hook: Replaced by `useGames()` as the primary dashboard data hook. May be retained for backward compatibility but is no longer the entry point.
- `_build_schedule_lookup()` in predictions.py: Only used by `/predictions/today`; not needed for `/games/{date}` which gets schedule data natively.

## Open Questions

1. **NULL game_id in unique constraint behavior**
   - What we know: PostgreSQL treats NULLs as distinct in UNIQUE constraints. Old rows with `game_id = NULL` won't conflict with each other.
   - What's unclear: Whether this could cause unexpected duplicate inserts during the transition period (old code writes without game_id, new code writes with game_id).
   - Recommendation: This is acceptable. The transition is atomic (container restart with new code). After restart, all new inserts include `game_id`. Old rows are grandfathered.

2. **Cache eviction for non-today dates**
   - What we know: Phase 14 will allow date navigation, meaning multiple dates could be cached.
   - What's unclear: Memory impact of caching many dates.
   - Recommendation: For Phase 13, only today's date is ever requested. Add a max-entries guard (e.g., 7 dates max) now to prevent unbounded growth when Phase 14 arrives.

3. **Existing `fetch_today_schedule()` callers**
   - What we know: `fetch_today_schedule()` is called by `live_features.py::get_today_games()` and `predictions.py::_build_schedule_lookup()`.
   - What's unclear: Whether to update `fetch_today_schedule()` in place or create a parallel function.
   - Recommendation: Create a new `fetch_schedule_for_date(date_str)` function using raw API. Leave `fetch_today_schedule()` unchanged for backward compatibility with the pipeline and `/predictions/today`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (via pyproject.toml) |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `pytest tests/test_pipeline/test_schema.py tests/test_api/test_predictions.py -x -q` |
| Full suite command | `pytest -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCHM-01 | game_id column exists after migration; unique constraint includes game_id | integration (Postgres) | `pytest tests/test_pipeline/test_schema.py::TestMigration::test_game_id_column -x` | No -- Wave 0 |
| SCHM-01 | Pipeline UPSERT includes game_id without error | integration (Postgres) | `pytest tests/test_pipeline/test_schema.py::TestMigration::test_upsert_with_game_id -x` | No -- Wave 0 |
| SCHM-02 | reconciliation columns exist after migration | integration (Postgres) | `pytest tests/test_pipeline/test_schema.py::TestMigration::test_reconciliation_columns -x` | No -- Wave 0 |
| SCHM-02 | reconciliation columns NOT in UPSERT update set | unit | `pytest tests/test_pipeline/test_schema.py::TestMigration::test_reconciliation_excluded_from_upsert -x` | No -- Wave 0 |
| VIBL-01 | /games/{date} returns all scheduled games including those without predictions | unit (mocked) | `pytest tests/test_api/test_games.py::TestGamesEndpoint::test_stub_cards_for_unpredicted_games -x` | No -- Wave 0 |
| VIBL-01 | /games/{date} returns predictions merged with schedule | unit (mocked) | `pytest tests/test_api/test_games.py::TestGamesEndpoint::test_games_with_predictions -x` | No -- Wave 0 |
| VIBL-02 | game_status maps correctly from MLB API status | unit | `pytest tests/test_api/test_games.py::TestStatusMapping::test_status_mapping -x` | No -- Wave 0 |
| VIBL-02 | Postponed games get POSTPONED status (not FINAL) | unit | `pytest tests/test_api/test_games.py::TestStatusMapping::test_postponed_detection -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_pipeline/test_schema.py tests/test_api/test_games.py -x -q`
- **Per wave merge:** `pytest -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_api/test_games.py` -- covers VIBL-01, VIBL-02 (new games endpoint tests, status mapping)
- [ ] `tests/test_pipeline/test_schema.py::TestMigration` -- covers SCHM-01, SCHM-02 (migration column tests, requires Postgres)
- [ ] `tests/test_pipeline/conftest.py` -- update `sample_prediction_data` fixture to include `game_id` field
- [ ] `tests/test_api/conftest.py` -- no changes expected (mock pool pattern sufficient)

## Sources

### Primary (HIGH confidence)
- **PostgreSQL 16 ALTER TABLE docs** - `ADD COLUMN IF NOT EXISTS` and `DROP CONSTRAINT IF EXISTS` syntax verified: [PostgreSQL ALTER TABLE](https://www.postgresql.org/docs/current/sql-altertable.html)
- **MLB Stats API /gameStatus endpoint** - 127 status codes verified; `abstractGameState` three-value taxonomy confirmed; postponed = `codedGameState: "D"` with `abstractGameState: "Final"`: [MLB Stats API gameStatus](https://statsapi.mlb.com/api/v1/gameStatus)
- **MLB-StatsAPI 1.9.0 source code** - `statsapi.schedule()` returns `detailedState` as `status`, NOT `abstractGameState`; verified via `inspect.getsource()` on installed package
- **Live API verification** - `statsapi.get('schedule', {'sportId': 1, 'date': '03/30/2026'})` confirmed returning `status.abstractGameState`, `status.codedGameState` in response
- **Existing codebase** - `src/pipeline/db.py`, `src/pipeline/schema.sql`, `api/routes/predictions.py`, `api/models.py`, `frontend/src/api/types.ts`, `frontend/src/hooks/usePredictions.ts`, `frontend/src/components/GameCard.tsx` -- all read and analyzed

### Secondary (MEDIUM confidence)
- **MLB Stats API schedule endpoint structure** - Response shape verified from `.planning/research/STACK.md` (previously researched and confirmed): `dates[].games[].status.{abstractGameState, codedGameState, detailedState}`
- **Pitfalls documentation** - `.planning/research/PITFALLS.md` Pitfalls 6, 10 directly applicable to Phase 13

### Tertiary (LOW confidence)
- None -- all findings verified against primary sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already installed and in use; no new dependencies
- Architecture: HIGH - Follows existing patterns (sync FastAPI handlers, psycopg3, Pydantic models, TanStack Query hooks)
- Pitfalls: HIGH - Status mapping verified against live MLB API; constraint behavior verified against PostgreSQL docs; pipeline UPSERT integration verified by reading source code
- Migration SQL: HIGH - `ADD COLUMN IF NOT EXISTS` and `DROP CONSTRAINT IF EXISTS` tested against PostgreSQL 16 docs

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (stable -- no fast-moving dependencies)
