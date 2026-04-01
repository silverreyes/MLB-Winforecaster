# Phase 16: Historical Game Cache - Research

**Researched:** 2026-03-31
**Domain:** Postgres game result caching, incremental MLB API fetch, FeatureBuilder schedule replacement
**Confidence:** HIGH

## Summary

Phase 16 eliminates the root cause of MLB Stats API 502/503 failures: every pipeline run calls `fetch_schedule(season)` which pulls all ~2,400 games for the entire March--September season via `statsapi.schedule()`. The solution is a `game_logs` Postgres table storing completed game results, seeded once and grown incrementally.

The FeatureBuilder currently uses `fetch_schedule()` output for three purposes: (1) the schedule DataFrame backbone with columns `game_id`, `game_date`, `home_team`, `away_team`, `home_probable_pitcher`, `away_probable_pitcher`, `home_score`, `away_score`, `winning_team`, `losing_team`, `status`, `season`; (2) Pythagorean win% calculation using `home_score`/`away_score` per team per season; (3) cumulative win% (Log5) using `winning_team`/`home_team`/`away_team` per game. Rolling OPS comes from `fetch_team_game_log()` (separate MLB API call), not from the schedule. An existing `games` table in schema.sql has the right shape but is unused anywhere in the codebase -- it can serve as the foundation for `game_logs` or be replaced.

**Primary recommendation:** Create a `game_logs` table with the exact columns FeatureBuilder needs, add a `seed_game_logs.py` CLI script for one-time backfill, add an incremental sync function called at pipeline startup, and modify `FeatureBuilder._load_schedule()` to read from `game_logs` instead of calling `fetch_schedule()`.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CACHE-01 | `game_logs` table exists with required columns | Schema analysis confirms needed columns from FeatureBuilder; existing `games` table can be repurposed or replaced |
| CACHE-02 | One-time seed job backfills all completed 2025+2026 games | `statsapi.schedule()` endpoint verified to return `game_id`, `home_score`, `away_score`, `winning_team`, `losing_team` for Final games |
| CACHE-03 | Incremental fetch from last known date forward on each run | `MAX(date)` query + `statsapi.schedule(start_date, end_date)` with `status == 'Final'` filter handles this |
| CACHE-04 | FeatureBuilder reads from `game_logs` instead of `fetch_schedule()` | `_load_schedule()` is the single entry point; replacing its body with a DB query is surgical |
| CACHE-05 | Immutability guarantee via `INSERT ... ON CONFLICT DO NOTHING` | Unique constraint on `game_id` ensures completed games are never overwritten |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| psycopg | 3.3.3 | Postgres connection/queries | Already used in `src/pipeline/db.py` |
| psycopg_pool | (bundled) | Connection pooling | Already used via `get_pool()` |
| statsapi | (installed) | MLB Stats API wrapper | Already used for schedule/linescore data |
| pandas | 2.2.x | DataFrame construction from DB rows | Already pinned project-wide |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| argparse | stdlib | CLI for seed script | One-time seed invocation |
| logging | stdlib | Structured logging | All new functions |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Raw SQL via psycopg | SQLAlchemy ORM | Project uses raw psycopg everywhere; no ORM; stay consistent |
| Postgres table | Parquet file cache | Parquet cache already exists but is per-season, not incremental; DB enables SQL queries for features |
| Migration file | Schema.sql modification | Follow Phase 13 migration pattern (migration_002.sql) for additive-only changes |

**Installation:**
No new packages needed. All dependencies already installed.

## Architecture Patterns

### Recommended Project Structure
```
src/
  pipeline/
    schema.sql              # Existing (games table already defined)
    migration_002.sql        # NEW: game_logs table DDL (or ALTER existing games table)
    db.py                    # ADD: game_logs CRUD functions
    game_log_sync.py         # NEW: incremental sync logic
  features/
    feature_builder.py       # MODIFY: _load_schedule() reads from DB
scripts/
  seed_game_logs.py          # NEW: one-time backfill CLI
tests/
  test_pipeline/
    test_game_log_sync.py    # NEW: sync/seed tests
```

### Pattern 1: Schema -- `game_logs` Table
**What:** Postgres table storing completed game results with exactly the columns FeatureBuilder needs.
**When to use:** Always -- this is the core data store for the phase.
**Columns required by FeatureBuilder analysis:**

```sql
CREATE TABLE IF NOT EXISTS game_logs (
    game_id         INTEGER PRIMARY KEY,
    game_date       DATE NOT NULL,
    home_team       VARCHAR(3) NOT NULL,
    away_team       VARCHAR(3) NOT NULL,
    home_score      INTEGER NOT NULL,
    away_score      INTEGER NOT NULL,
    winning_team    VARCHAR(3) NOT NULL,
    losing_team     VARCHAR(3) NOT NULL,
    home_probable_pitcher VARCHAR(100),
    away_probable_pitcher VARCHAR(100),
    season          INTEGER NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Performance indexes for FeatureBuilder queries
CREATE INDEX IF NOT EXISTS idx_game_logs_date ON game_logs (game_date);
CREATE INDEX IF NOT EXISTS idx_game_logs_season ON game_logs (season);
CREATE INDEX IF NOT EXISTS idx_game_logs_home_team ON game_logs (home_team, season);
CREATE INDEX IF NOT EXISTS idx_game_logs_away_team ON game_logs (away_team, season);
```

**Column justification (from FeatureBuilder code analysis):**
- `game_id`: PRIMARY KEY, used for ON CONFLICT DO NOTHING
- `game_date`: Used in `_load_schedule()` for as_of_date filter, rolling feature joins
- `home_team`, `away_team`: Used in every feature computation (normalized 3-letter codes)
- `home_score`, `away_score`: Used in `_add_offense_features()` for Pythagorean win%
- `winning_team`, `losing_team`: Used in `_add_outcome_label()` and `_compute_cumulative_win_pct()`
- `home_probable_pitcher`, `away_probable_pitcher`: Used in `_filter_tbd_starters()` and all SP feature lookups
- `season`: Used in every per-season groupby

**Columns NOT needed (from fetch_schedule but unused by features):**
- `status`: Always "Final" in game_logs (invariant)
- `is_shortened_season`: Computed from `season == 2020`
- `season_games`: Computed from `season == 2020`

### Pattern 2: Existing `games` Table Decision
**What:** schema.sql already defines a `games` table (lines 9-21) with columns: `id SERIAL PRIMARY KEY`, `game_date`, `home_team`, `away_team`, `game_id`, `home_score`, `away_score`, `home_win`, `status`.
**Current state:** This table is **never written to or read from anywhere in the codebase**. Zero references in `src/` or `tests/`.
**Decision:** Create a new `game_logs` table rather than repurposing `games`. Reasons:
1. `games` uses `id SERIAL PRIMARY KEY` -- we want `game_id INTEGER PRIMARY KEY` for immutability
2. `games` lacks `winning_team`, `losing_team`, `home_probable_pitcher`, `away_probable_pitcher`, `season`
3. `games` has `home_win BOOLEAN` but FeatureBuilder needs `winning_team VARCHAR(3)` for the label
4. Cleaner to add a new table than ALTER an unused one with 5+ columns
5. The existing `games` table can be dropped in a future cleanup phase

### Pattern 3: Seed Job
**What:** A one-time CLI script that backfills all completed 2025 and 2026 regular-season games.
**How:** Use `statsapi.schedule(start_date, end_date, sportId=1)` per season, filter to `game_type == "R"` and `status == "Final"`, normalize team names, batch INSERT with ON CONFLICT DO NOTHING.
**Trigger:** `python scripts/seed_game_logs.py` -- run manually or via Docker exec.

```python
# Pseudocode for seed
for season in [2025, 2026]:
    start, end = SEASON_DATES[season]
    games = statsapi.schedule(start_date=start, end_date=end, sportId=1)
    final_games = [g for g in games if g.get("game_type") == "R" and g.get("status") == "Final"]
    for g in final_games:
        insert_game_log(pool, normalize_game_dict(g))
```

### Pattern 4: Incremental Sync
**What:** On each pipeline run, fetch only games from `MAX(game_date)` in `game_logs` to today.
**When:** Called in `run_pipeline.py` at startup, BEFORE any pipeline version runs.
**Strategy:**
1. Query `SELECT MAX(game_date) FROM game_logs` -> `last_date`
2. If `last_date` is None, skip (seed hasn't run yet -- log warning)
3. Compute `start_date = last_date` (inclusive, catches any games from that day not yet Final at last sync)
4. Compute `end_date = yesterday` (today's games may not be Final yet)
5. Call `statsapi.schedule(start_date, end_date, sportId=1)`
6. Filter to `game_type == "R"` and `status == "Final"`
7. INSERT ... ON CONFLICT DO NOTHING (safe for re-runs)

**Why start_date = last_date (inclusive):** A pipeline run at 10am may have synced games through April 15, but West Coast games from April 15 weren't Final yet. The next sync includes April 15 again, but ON CONFLICT DO NOTHING prevents duplicates.

### Pattern 5: FeatureBuilder Modification
**What:** Replace `_load_schedule()` to read from `game_logs` Postgres table instead of calling `fetch_schedule()`.
**Scope of change:** ONLY `_load_schedule()` method body changes. All downstream methods (`_add_outcome_label`, `_add_offense_features`, `_compute_cumulative_win_pct`) consume the same DataFrame columns.
**Key constraint:** FeatureBuilder must receive a DB connection pool. Currently it takes `seasons` and `as_of_date`. The pool can be passed as an optional constructor parameter (default None falls back to `fetch_schedule()` for backward compat with backtest notebooks).

```python
class FeatureBuilder:
    def __init__(self, seasons, as_of_date=None, pool=None):
        self.seasons = seasons
        self.as_of_date = as_of_date
        self._pool = pool  # None = legacy Parquet path

    def _load_schedule(self):
        if self._pool is not None:
            return self._load_from_game_logs()
        # Legacy fallback for notebooks/backtest
        return self._load_from_parquet_cache()
```

**LiveFeatureBuilder change:** Pass the pool through:
```python
class LiveFeatureBuilder:
    def __init__(self, pool=None):
        self._builder = FeatureBuilder(
            seasons=[self.season - 1, self.season],
            as_of_date=self.today_str,
            pool=pool,  # NEW: use game_logs when pool provided
        )
```

**Runner change:** Pass pool to LiveFeatureBuilder:
```python
def run_pipeline(version, artifacts, pool, feature_builder=None):
    if feature_builder is None:
        feature_builder = LiveFeatureBuilder(pool=pool)
```

### Anti-Patterns to Avoid
- **Do NOT drop the Parquet cache system:** Backtest notebooks still need it. game_logs only replaces live pipeline schedule fetches.
- **Do NOT modify `fetch_schedule()` itself:** It stays as-is for backward compat. The change is in FeatureBuilder's `_load_schedule()`.
- **Do NOT include non-Final games in game_logs:** Only "Final" status games belong. In-progress and scheduled games are handled by `fetch_schedule_for_date()` and `fetch_today_schedule()`.
- **Do NOT add game_logs to the 75s TTL cache system:** game_logs data is immutable and read from DB; no TTL needed.
- **Do NOT call incremental sync inside each pipeline version run:** Sync once at startup (in `run_pipeline.py`), not per-game or per-version.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Team name normalization | Custom mapping | `normalize_team()` from `src.data.team_mappings` | Already handles all 30 teams + historical aliases |
| Season date ranges | Hardcoded dates in seed | `SEASON_DATES` dict from `src.data.mlb_schedule` | Already maintained and tested |
| Connection pooling | Manual connections | `get_pool()` from `src.pipeline.db` | Already configured with proper min/max sizes |
| Upsert idempotency | Manual duplicate checks | `INSERT ... ON CONFLICT DO NOTHING` | Postgres-native, atomic, zero race conditions |

## Common Pitfalls

### Pitfall 1: Forgetting to Normalize Team Names Before Insert
**What goes wrong:** `statsapi.schedule()` returns full team names like "New York Yankees" but game_logs stores 3-letter codes like "NYY". Inserting full names breaks all downstream lookups.
**Why it happens:** The normalization happens in `fetch_schedule()` (line 69-81) but would be missed in a new seed/sync function.
**How to avoid:** Always call `normalize_team()` on `home_name`, `away_name`, `winning_team`, `losing_team` before insert. Include the `_SKIP_NORMALIZE` sentinel check for "Tie" values.
**Warning signs:** VARCHAR(3) constraint violation on insert; mismatched team codes in feature lookups.

### Pitfall 2: West Coast Games Not Final at Sync Time
**What goes wrong:** An incremental sync at 10am ET misses West Coast night games from the previous day that ended after midnight ET.
**Why it happens:** Using `end_date = yesterday` with strict date boundaries.
**How to avoid:** Use `start_date = last_date` (inclusive) so the next sync re-checks games from the last known date. ON CONFLICT DO NOTHING handles duplicates safely.
**Warning signs:** Missing late-night games in game_logs; gap in rolling feature calculations.

### Pitfall 3: FeatureBuilder Backward Compatibility Break
**What goes wrong:** Backtest notebooks and training scripts stop working because FeatureBuilder now requires a pool.
**Why it happens:** Making pool a required constructor parameter instead of optional.
**How to avoid:** Pool defaults to None; when None, `_load_schedule()` falls back to the existing `fetch_schedule()` Parquet path. This preserves all existing notebook workflows.
**Warning signs:** ImportError or TypeError in notebooks that construct FeatureBuilder without pool.

### Pitfall 4: Tie Games in `winning_team`/`losing_team`
**What goes wrong:** `normalize_team("Tie")` raises ValueError. `normalize_team("")` raises ValueError.
**Why it happens:** `statsapi.schedule()` returns `winning_team = ""` for in-progress/scheduled games and `winning_team = "Tie"` for rare tied games.
**How to avoid:** Only insert Final games. For the rare "Tie" case, use the same `_SKIP_NORMALIZE` guard from `fetch_schedule()`. Alternatively, skip tied games entirely (they are extremely rare in the modern era -- only happens in suspended games).
**Warning signs:** ValueError stack trace during seed/sync.

### Pitfall 5: Running Seed Before Schema Migration
**What goes wrong:** `INSERT INTO game_logs` fails because the table doesn't exist.
**Why it happens:** Schema migration and seed are separate steps; seed runs before migration.
**How to avoid:** Seed script calls `apply_schema(pool)` first, which runs schema.sql + all migrations. Or: migration_002.sql is applied at API/worker startup via existing `apply_schema()` flow, so seed only needs to run after at least one startup.
**Warning signs:** "relation game_logs does not exist" error.

### Pitfall 6: LiveFeatureBuilder Still Calls fetch_today_schedule()
**What goes wrong:** `get_today_games()` still calls `fetch_today_schedule()` (the separate today-only API call). This is CORRECT behavior -- game_logs replaces the historical season schedule fetch, not the today-only game list fetch.
**Why it happens:** Confusion between `fetch_schedule(season)` (full season, what we're replacing) and `fetch_today_schedule()` (today only, still needed for discovering today's games).
**How to avoid:** Clearly document that game_logs replaces ONLY `_load_schedule()` in FeatureBuilder. `get_today_games()` in LiveFeatureBuilder continues to call `fetch_today_schedule()`.
**Warning signs:** No today games visible in pipeline despite games being scheduled.

## Code Examples

### Example 1: game_logs INSERT with ON CONFLICT DO NOTHING
```python
# Source: Pattern from existing db.py insert_prediction()
def insert_game_log(pool: ConnectionPool, data: dict) -> bool:
    """Insert a completed game into game_logs. Returns True if inserted, False if duplicate."""
    sql = """
        INSERT INTO game_logs (
            game_id, game_date, home_team, away_team,
            home_score, away_score, winning_team, losing_team,
            home_probable_pitcher, away_probable_pitcher, season
        ) VALUES (
            %(game_id)s, %(game_date)s, %(home_team)s, %(away_team)s,
            %(home_score)s, %(away_score)s, %(winning_team)s, %(losing_team)s,
            %(home_probable_pitcher)s, %(away_probable_pitcher)s, %(season)s
        )
        ON CONFLICT (game_id) DO NOTHING
    """
    with pool.connection() as conn:
        cur = conn.execute(sql, data)
        inserted = cur.rowcount > 0
        conn.commit()
    return inserted
```

### Example 2: Batch Insert for Seed
```python
# Source: psycopg3 executemany pattern
def batch_insert_game_logs(pool: ConnectionPool, games: list[dict]) -> int:
    """Batch insert completed games. Returns count of newly inserted rows."""
    sql = """
        INSERT INTO game_logs (
            game_id, game_date, home_team, away_team,
            home_score, away_score, winning_team, losing_team,
            home_probable_pitcher, away_probable_pitcher, season
        ) VALUES (
            %(game_id)s, %(game_date)s, %(home_team)s, %(away_team)s,
            %(home_score)s, %(away_score)s, %(winning_team)s, %(losing_team)s,
            %(home_probable_pitcher)s, %(away_probable_pitcher)s, %(season)s
        )
        ON CONFLICT (game_id) DO NOTHING
    """
    inserted = 0
    with pool.connection() as conn:
        for game in games:
            cur = conn.execute(sql, game)
            inserted += cur.rowcount
        conn.commit()
    return inserted
```

### Example 3: FeatureBuilder Loading from game_logs
```python
# Source: Adapted from _load_schedule() at feature_builder.py:103
def _load_from_game_logs(self) -> pd.DataFrame:
    """Load schedule data from game_logs Postgres table."""
    placeholders = ", ".join(["%s"] * len(self.seasons))
    sql = f"""
        SELECT game_id, game_date, home_team, away_team,
               home_score, away_score, winning_team, losing_team,
               home_probable_pitcher, away_probable_pitcher, season
        FROM game_logs
        WHERE season IN ({placeholders})
        ORDER BY game_date
    """
    with self._pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, self.seasons)
            rows = cur.fetchall()

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["game_date"] = pd.to_datetime(df["game_date"])

    if self.as_of_date is not None:
        cutoff = pd.to_datetime(self.as_of_date)
        df = df[df["game_date"] < cutoff].copy()

    # Add computed columns expected by downstream methods
    df["is_shortened_season"] = df["season"] == 2020
    df["season_games"] = df["season"].apply(lambda s: 60 if s == 2020 else 162)
    df["status"] = "Final"  # game_logs only stores Final games

    return df
```

### Example 4: Incremental Sync
```python
# Source: New function, pattern from existing db.py queries
def sync_game_logs(pool: ConnectionPool) -> int:
    """Fetch newly completed games since last known date in game_logs.
    Returns count of new rows inserted."""
    # Get last known date
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(game_date) FROM game_logs")
            row = cur.fetchone()
            last_date = row[0] if row else None

    if last_date is None:
        logger.warning("game_logs empty -- run seed_game_logs.py first")
        return 0

    from datetime import date
    start = last_date.strftime("%m/%d/%Y")
    yesterday = (date.today() - timedelta(days=1)).strftime("%m/%d/%Y")
    # ... fetch, filter Final + regular season, normalize, batch insert
```

### Example 5: Normalizing a statsapi Schedule Dict
```python
# Source: Pattern from fetch_schedule() at mlb_schedule.py:68-81
_SKIP_NORMALIZE = {"", "Tie"}

def normalize_game_dict(g: dict, season: int) -> dict:
    """Convert raw statsapi.schedule() dict to game_logs insert dict."""
    return {
        "game_id": g["game_id"],
        "game_date": g["game_date"],
        "home_team": normalize_team(g["home_name"]),
        "away_team": normalize_team(g["away_name"]),
        "home_score": g["home_score"],
        "away_score": g["away_score"],
        "winning_team": normalize_team(g["winning_team"]) if g.get("winning_team") not in _SKIP_NORMALIZE else g.get("winning_team", ""),
        "losing_team": normalize_team(g["losing_team"]) if g.get("losing_team") not in _SKIP_NORMALIZE else g.get("losing_team", ""),
        "home_probable_pitcher": g.get("home_probable_pitcher") or None,
        "away_probable_pitcher": g.get("away_probable_pitcher") or None,
        "season": season,
    }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `fetch_schedule(season)` on every pipeline run | `game_logs` DB table + incremental sync | Phase 16 | Eliminates full-season API call; fixes 502/503 errors |
| Parquet-only caching for schedule | DB for live pipeline, Parquet for backtest | Phase 16 | Live pipeline never touches Parquet schedule cache |
| FeatureBuilder reads from Parquet via `fetch_schedule()` | FeatureBuilder reads from Postgres when pool provided | Phase 16 | Single DB query replaces 2 API calls per pipeline run |

**Key insight:** The current Parquet cache for schedule data (key `schedule_{season}`) is NOT the problem. The problem is that the cache is invalidated on every run because today's games aren't Final yet, so the full season is re-fetched. game_logs solves this by only storing immutable Final games and never re-fetching them.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (via pyproject.toml) |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_pipeline/test_game_log_sync.py -x` |
| Full suite command | `pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CACHE-01 | game_logs table created by migration | unit | `pytest tests/test_pipeline/test_schema.py -x -k game_logs` | Needs additions to existing file |
| CACHE-02 | Seed job inserts all Final 2025+2026 games | unit | `pytest tests/test_pipeline/test_game_log_sync.py -x -k seed` | Wave 0 |
| CACHE-03 | Incremental sync fetches from last date forward | unit | `pytest tests/test_pipeline/test_game_log_sync.py -x -k sync` | Wave 0 |
| CACHE-04 | FeatureBuilder reads from game_logs when pool provided | unit | `pytest tests/test_pipeline/test_game_log_sync.py -x -k feature_builder` | Wave 0 |
| CACHE-05 | ON CONFLICT DO NOTHING prevents overwrites | unit | `pytest tests/test_pipeline/test_game_log_sync.py -x -k immutability` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_pipeline/test_game_log_sync.py -x`
- **Per wave merge:** `pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_pipeline/test_game_log_sync.py` -- covers CACHE-01 through CACHE-05
- [ ] Migration file `src/pipeline/migration_002.sql` -- game_logs DDL
- [ ] `scripts/seed_game_logs.py` -- CLI seed script

## Open Questions

1. **Should the existing unused `games` table be dropped?**
   - What we know: `games` is defined in schema.sql but never referenced in any source file
   - What's unclear: Whether any external tool or admin query references it
   - Recommendation: Leave `games` table as-is in Phase 16 (additive-only per carry-forward decisions). Add a comment in schema.sql marking it as deprecated. Clean up in a future phase.

2. **Should the seed script be runnable as a Docker exec command?**
   - What we know: The worker container runs `python scripts/run_pipeline.py`. The seed is a one-time operation.
   - What's unclear: Whether the user wants it as a separate Docker service or a manual exec
   - Recommendation: Make it a standalone CLI script (`python scripts/seed_game_logs.py`) runnable via `docker compose exec worker python scripts/seed_game_logs.py`. No need for a separate Docker service.

3. **Should game_logs include games from seasons before 2025?**
   - What we know: The product owner specified "all completed 2025 games AND completed 2026 games". FeatureBuilder currently loads `[self.season - 1, self.season]` for the live pipeline (i.e., 2025 + 2026 in 2026).
   - What's unclear: Whether backfilling 2015-2024 into game_logs would also be valuable
   - Recommendation: Seed 2025 + 2026 only per product owner decision. Historical seasons (2015-2024) remain available via the Parquet cache for notebooks. If a future phase needs them in DB, the seed script can be parameterized with `--seasons`.

4. **Should incremental sync run in the API container or only the worker?**
   - What we know: FeatureBuilder is only instantiated in the worker (pipeline) container. The API reads predictions from DB, not features.
   - What's unclear: Whether the API might eventually read game_logs for display
   - Recommendation: Sync runs in the worker only, at `run_pipeline.py` startup before any scheduled jobs. The API container applies the migration (creating the table) but does not sync data.

## Sources

### Primary (HIGH confidence)
- `src/features/feature_builder.py` -- Direct code analysis of `_load_schedule()`, `_add_outcome_label()`, `_add_offense_features()`, `_compute_cumulative_win_pct()` revealed exact column requirements
- `src/data/mlb_schedule.py` -- Direct code analysis of `fetch_schedule()` return columns (lines 30-36, 68-109)
- `src/pipeline/db.py` -- Direct code analysis of existing DB patterns, connection pool, schema application
- `src/pipeline/schema.sql` -- Confirmed unused `games` table (lines 9-21)
- `src/pipeline/migration_001.sql` -- Migration pattern established in Phase 13
- Live `statsapi.schedule()` output -- Verified Final game dict keys include `game_id`, `home_name`, `away_name`, `home_score`, `away_score`, `winning_team`, `losing_team`, `status`, `game_type`

### Secondary (MEDIUM confidence)
- `src/pipeline/live_features.py` -- Confirmed LiveFeatureBuilder constructor pattern and pool-passing opportunity
- `src/pipeline/runner.py` -- Confirmed LiveFeatureBuilder instantiation point where pool is available

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in use, no new dependencies
- Architecture: HIGH -- direct code analysis of FeatureBuilder data flow, verified column requirements empirically
- Pitfalls: HIGH -- derived from actual codebase patterns (normalize_team sentinel handling, cache behavior)
- Schema design: HIGH -- columns derived from actual FeatureBuilder column usage, verified against statsapi output

**Research date:** 2026-03-31
**Valid until:** 2026-04-30 (stable domain -- MLB API and psycopg are mature)
