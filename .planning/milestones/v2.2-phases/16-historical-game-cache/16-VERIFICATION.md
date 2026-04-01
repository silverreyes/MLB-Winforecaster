---
phase: 16-historical-game-cache
verified: 2026-04-01T00:00:00Z
status: passed
score: "12/12 must-haves verified"
re_verification: false
---

# Phase 16: Historical Game Cache Verification Report

**Phase Goal:** The pipeline never re-fetches immutable completed game data from the MLB Stats API; instead it reads from a local game_logs Postgres table, seeded once and grown incrementally.
**Verified:** 2026-04-01
**Status:** passed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | game_logs table has columns: game_id (VARCHAR PK), game_date, home_team, away_team, home_score, away_score, winning_team, losing_team, home_probable_pitcher, away_probable_pitcher, season | VERIFIED | `src/pipeline/migration_002.sql` lines 4-16: `CREATE TABLE IF NOT EXISTS game_logs (game_id VARCHAR PRIMARY KEY, game_date DATE NOT NULL, home_team VARCHAR NOT NULL, away_team VARCHAR NOT NULL, home_score INTEGER NOT NULL, away_score INTEGER NOT NULL, winning_team VARCHAR NOT NULL, losing_team VARCHAR NOT NULL, home_probable_pitcher VARCHAR, away_probable_pitcher VARCHAR, season INTEGER NOT NULL)` |
| 2 | migration_002.sql creates game_logs with CREATE TABLE IF NOT EXISTS (idempotent) | VERIFIED | `src/pipeline/migration_002.sql` line 4: `CREATE TABLE IF NOT EXISTS game_logs (` -- idempotent DDL, safe to re-run |
| 3 | migration_002.sql creates at least 3 indexes on game_logs | VERIFIED | `src/pipeline/migration_002.sql` lines 19-22: 4 indexes created -- `idx_game_logs_date` (game_date), `idx_game_logs_season` (season), `idx_game_logs_home_team` (home_team, season), `idx_game_logs_away_team` (away_team, season) -- all with `CREATE INDEX IF NOT EXISTS` |
| 4 | apply_schema() in db.py executes migration_002.sql after schema.sql | VERIFIED | `src/pipeline/db.py` lines 89-95: `migration_002_path = _MIGRATION_DIR / "migration_002.sql"` with conditional existence check, then `conn.execute(migration_sql)` and `conn.commit()` -- executed after migration_001.sql block (lines 75-87) |
| 5 | batch_insert_game_logs() uses INSERT ... ON CONFLICT DO NOTHING (immutability) | VERIFIED | `src/pipeline/db.py` lines 399-423: `def batch_insert_game_logs(pool, games)` with SQL at line 415: `ON CONFLICT (game_id) DO NOTHING`; returns count of newly inserted rows via `cur.rowcount` aggregation |
| 6 | sync_game_logs() queries MAX(game_date), fetches from max-1 day to yesterday | VERIFIED | `src/pipeline/db.py` lines 426-496: `def sync_game_logs(pool)` executes `SELECT MAX(game_date) FROM game_logs` at line 440; line 449: `start = (last_date - timedelta(days=1))` (1-day overlap); line 450: `end = date_cls.today() - timedelta(days=1)` (yesterday) |
| 7 | seed_game_logs.py script backfills 2025 and 2026 completed games | VERIFIED | `scripts/seed_game_logs.py` lines 131-138: argparse with `--seasons` argument, `default=[2025, 2026]`; lines 60-124: `seed(seasons)` function iterates seasons, fetches via `statsapi.schedule()`, filters Final + R games, calls `batch_insert_game_logs()` |
| 8 | run_pipeline.py calls sync_game_logs at startup | VERIFIED | `scripts/run_pipeline.py` line 21: `from src.pipeline.db import get_pool, apply_schema, mark_stale_runs_failed, sync_game_logs`; line 54: `synced = sync_game_logs(pool)` in `_run_scheduler`; line 83: `synced = sync_game_logs(pool)` in `_run_once` -- both wrapped in try/except for non-fatal failure |
| 9 | FeatureBuilder accepts pool parameter (default None for backward compat) | VERIFIED | `src/features/feature_builder.py` line 68: `def __init__(self, seasons: list[int], as_of_date: str | None = None, pool=None):` with line 71: `self._pool = pool  # None = legacy Parquet/API path (backward compat)` |
| 10 | FeatureBuilder._load_from_game_logs queries game_logs table when pool provided | VERIFIED | `src/features/feature_builder.py` lines 131-171: `def _load_from_game_logs(self)` executes `SELECT game_id, game_date, ... FROM game_logs WHERE season IN (...)`, constructs DataFrame, adds computed columns (is_shortened_season, season_games, status='Final') |
| 11 | LiveFeatureBuilder passes pool to FeatureBuilder constructor | VERIFIED | `src/pipeline/live_features.py` lines 41-52: `def __init__(self, pool=None):` then line 49-52: `self._builder = FeatureBuilder(seasons=[self.season - 1, self.season], as_of_date=self.today_str, pool=pool)` |
| 12 | runner.py passes pool to LiveFeatureBuilder | VERIFIED | `src/pipeline/runner.py` line 76: `feature_builder = LiveFeatureBuilder(pool=pool)` inside run_pipeline function |

**Score:** 12/12 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/pipeline/migration_002.sql` | CREATE TABLE game_logs, indexes, idempotent DDL | VERIFIED | 22 lines: CREATE TABLE IF NOT EXISTS with 11 columns (game_id VARCHAR PK), 4 CREATE INDEX IF NOT EXISTS statements |
| `src/pipeline/db.py` | batch_insert_game_logs(), sync_game_logs(), apply_schema with migration_002 | VERIFIED | Lines 89-95: apply_schema executes migration_002.sql; lines 399-423: batch_insert with ON CONFLICT DO NOTHING; lines 426-496: sync from MAX(game_date) |
| `scripts/seed_game_logs.py` | CLI seed script for 2025+2026 backfill | VERIFIED | 143 lines: argparse --seasons (default [2025, 2026]), statsapi.schedule fetch, Final+R filter, normalize_team, batch_insert_game_logs |
| `src/pipeline/runner.py` | sync_game_logs call, pool wiring to LiveFeatureBuilder | VERIFIED | Line 76: `LiveFeatureBuilder(pool=pool)` passes pool through constructor chain |
| `src/features/feature_builder.py` | pool parameter, _load_from_game_logs method | VERIFIED | Line 68: `pool=None` default parameter; lines 111-112: `if self._pool is not None: return self._load_from_game_logs()`; lines 131-171: full _load_from_game_logs implementation |
| `src/pipeline/live_features.py` | LiveFeatureBuilder pool passthrough | VERIFIED | Line 41: `def __init__(self, pool=None):`; line 52: `pool=pool` passed to FeatureBuilder constructor |
| `tests/test_pipeline/test_game_log_sync.py` | Tests for schema, insert, immutability, sync, FeatureBuilder DB path | VERIFIED | 6 test functions: test_migration_creates_game_logs_table (CACHE-01), test_batch_insert_returns_count (CACHE-02), test_immutability_duplicate_insert (CACHE-05), test_sync_empty_table_returns_zero (CACHE-03), test_sync_fetches_from_max_date (CACHE-03), test_feature_builder_reads_game_logs (CACHE-04) |
| `tests/test_pipeline/conftest.py` | DROP TABLE IF EXISTS game_logs in clean_tables | VERIFIED | Line 48: `conn.execute("DROP TABLE IF EXISTS game_logs CASCADE")` in clean_tables fixture, ensuring test isolation |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/pipeline/db.py` apply_schema | `src/pipeline/migration_002.sql` execution | apply_schema reads and executes migration DDL | WIRED | db.py lines 89-95: `migration_002_path = _MIGRATION_DIR / "migration_002.sql"` then `conn.execute(migration_sql)` |
| `src/pipeline/db.py` sync_game_logs | batch_insert_game_logs -> ON CONFLICT DO NOTHING | sync fetches new games then batch inserts idempotently | WIRED | db.py line 494: `inserted = batch_insert_game_logs(pool, final_games)` at end of sync_game_logs; batch_insert SQL line 415: `ON CONFLICT (game_id) DO NOTHING` |
| `scripts/run_pipeline.py` | sync_game_logs(pool) at pipeline startup | Both _run_scheduler and _run_once call sync before jobs | WIRED | run_pipeline.py line 54: `synced = sync_game_logs(pool)` in _run_scheduler; line 83: same in _run_once; both wrapped in try/except |
| `src/pipeline/runner.py` -> LiveFeatureBuilder(pool=pool) -> FeatureBuilder(pool=pool) -> _load_from_game_logs | Pool wiring chain from runner to DB query | Constructor chain passes pool through 3 levels | WIRED | runner.py line 76: `LiveFeatureBuilder(pool=pool)`; live_features.py line 52: `pool=pool` to FeatureBuilder; feature_builder.py lines 111-112: pool gates DB vs API path |
| `scripts/seed_game_logs.py` | batch_insert_game_logs for backfill | Seed script imports and calls batch insert | WIRED | seed_game_logs.py line 20: `from src.pipeline.db import apply_schema, batch_insert_game_logs, get_pool`; line 105: `inserted = batch_insert_game_logs(pool, final_games)` |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CACHE-01 | 16-01 | game_logs table exists with required columns | SATISFIED | migration_002.sql lines 4-16: CREATE TABLE IF NOT EXISTS game_logs with game_id VARCHAR PK, game_date DATE, home_team VARCHAR, away_team VARCHAR, home_score INTEGER, away_score INTEGER, winning_team VARCHAR, losing_team VARCHAR, home_probable_pitcher VARCHAR, away_probable_pitcher VARCHAR, season INTEGER; test_migration_creates_game_logs_table verifies all 11 columns present |
| CACHE-02 | 16-02 | One-time seed job backfills 2025+2026 | SATISFIED | seed_game_logs.py lines 131-138: argparse `--seasons` with `default=[2025, 2026]`, `nargs="+"` accepts year list; line 105: calls `batch_insert_game_logs(pool, final_games)` per season; test_batch_insert_returns_count verifies insert functionality |
| CACHE-03 | 16-01, 16-02 | Incremental fetch from last known date | SATISFIED | sync_game_logs in db.py line 440: `cur.execute("SELECT MAX(game_date) FROM game_logs")`; line 449: `start = (last_date - timedelta(days=1))`; line 450: `end = date_cls.today() - timedelta(days=1)`; fetches only new window; test_sync_fetches_from_max_date verifies start_date = MAX(game_date) - 1 |
| CACHE-04 | 16-03 | FeatureBuilder reads from game_logs | SATISFIED | feature_builder.py lines 111-112: `if self._pool is not None: return self._load_from_game_logs()`; lines 131-171: _load_from_game_logs queries game_logs table with `SELECT ... FROM game_logs WHERE season IN (...)`; pool=None default preserves backward compat; test_feature_builder_reads_game_logs verifies DB path used and fetch_schedule NOT called |
| CACHE-05 | 16-01 | Immutability via ON CONFLICT DO NOTHING | SATISFIED | batch_insert_game_logs SQL at db.py line 415: `ON CONFLICT (game_id) DO NOTHING`; test_immutability_duplicate_insert confirms: first insert returns 1, duplicate insert returns 0, original row unchanged (home_score=5, away_score=3 not overwritten by 99/88) |

All 5 requirements fully satisfied. No orphaned requirements.

### Anti-Patterns Found

No blockers or warnings detected.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | -- | -- | -- | -- |

Scan covered: migration_002.sql, db.py (game log functions), seed_game_logs.py, run_pipeline.py, feature_builder.py (_load_from_game_logs), live_features.py (pool passthrough), test_game_log_sync.py, conftest.py. No TODO/FIXME/PLACEHOLDER comments found in Phase 16 code. No stub implementations.

### Human Verification Required

The following behaviors require visual or browser-level confirmation and cannot be verified programmatically:

#### 1. Seed Script End-to-End Execution

**Test:** Run `python scripts/seed_game_logs.py --seasons 2025 2026` against a Postgres instance with an empty game_logs table.
**Expected:** Log output shows fetched game counts per season and total new rows inserted. Query `SELECT COUNT(*) FROM game_logs` returns >2000 rows (2025 full season + 2026 partial).
**Why human:** Requires live MLB Stats API access and a running Postgres instance; integration test coverage verifies mocked paths only.

#### 2. Pipeline Startup Sync

**Test:** Start the worker process (`python scripts/run_pipeline.py`) after a day without syncing.
**Expected:** Log output shows "Synced N new game(s) to game_logs" before scheduler jobs begin.
**Why human:** Requires running pipeline process with database and MLB API access.

### Gaps Summary

None. All 12 observable truths are verified, all 8 artifacts confirmed (exists, substantive, wired), all 5 key links are confirmed wired, all 5 requirements (CACHE-01 through CACHE-05) are fully satisfied.

Test evidence:
- `tests/test_pipeline/test_game_log_sync.py` -- 6 tests covering migration, insert, immutability, sync, FeatureBuilder DB path
- Phase 16 implementation commits: 82d79d6, f510dd6, d270dd8, d369bce, 31525de, 440d5be, 9bbcc44

---

_Verified: 2026-04-01_
_Verifier: Claude (gsd-executor)_
