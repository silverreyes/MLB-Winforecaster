# Phase 7: Live Pipeline and Database - Research

**Researched:** 2026-03-29
**Domain:** PostgreSQL database schema, scheduled Python pipeline, live MLB/Kalshi data fetching, model inference from persisted artifacts
**Confidence:** HIGH

## Summary

Phase 7 transforms the batch-oriented ML project into a live daily prediction system. The core challenge is threefold: (1) design a Postgres schema that enforces the three-run daily lifecycle (pre_lineup/post_lineup/confirmation) with database-level constraints preventing invalid state, (2) build a pipeline runner that fetches today's games, constructs features using the existing `FeatureBuilder` infrastructure, runs inference against persisted joblib artifacts, computes Kalshi edge signals, and inserts rows -- all scheduled at 10am/1pm/5pm ET, and (3) handle the messy real-world cases (TBD starters, late lineup changes, Kalshi API unavailability) gracefully.

The existing codebase provides strong building blocks: `statsapi.schedule()` already fetches game data with probable pitchers (the live pipeline just needs to call it for today's date with non-Final status), the `FeatureBuilder` class handles all feature engineering, and the model artifacts are persisted as joblib dicts containing `{model, calibrator, feature_cols}`. The live pipeline is essentially a thin orchestration layer that wires these together with Postgres persistence.

**Primary recommendation:** Use psycopg 3.3 (direct, no ORM) for Postgres access, raw SQL migration files (no Alembic -- overkill for 3 stable tables), APScheduler 3.x with CronTrigger for scheduling within the worker container, and restructure `FeatureBuilder` to support single-day feature construction (currently it processes full seasons in batch).

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PIPE-01 | Postgres schema: `games`, `predictions`, `pipeline_runs` tables with indexes | Schema design section with enum/CHECK constraint patterns, index strategy |
| PIPE-02 | Pre-lineup pipeline at 10am ET using TEAM_ONLY features, SP fields null | Live feature construction via FeatureBuilder, artifact loading, TEAM_ONLY_FEATURE_COLS |
| PIPE-03 | Post-lineup pipeline at 1pm ET using SP_ENHANCED features with confirmed SPs | SP resolution chain, SP_ENHANCED_PRUNED_COLS (17 features), FeatureBuilder._resolve_sp_stats |
| PIPE-04 | Confirmation pipeline at 5pm ET, re-fetches SPs, detects changes, marks old rows | is_latest flag management, sp_may_have_changed detection pattern |
| PIPE-05 | Kalshi live price fetch + edge_signal computation at insert time | Kalshi GET /markets?status=open&series_ticker=KXMLBGAME, edge.compute_edge_signals |
| PIPE-06 | SP name stored per prediction row, sp_may_have_changed flag | Schema column design, confirmation run comparison logic |
| PIPE-07 | Fallback to TEAM_ONLY when SPs TBD, prediction_status enum enforcement | CHECK constraint or prediction_status enum, sp_uncertainty flag, database-level invariant |
| PIPE-08 | Pipeline logging to persistent file, GET /api/v1/health endpoint | pipeline_runs table, structured logging, health endpoint data contract |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| psycopg | 3.3.3 | PostgreSQL adapter for Python | Modern psycopg3 -- native async support, pipeline mode, proper connection context managers. Production/Stable. No ORM overhead for 3 simple tables. |
| psycopg[binary] | 3.3.3 | Pre-compiled C extension for psycopg | Avoids needing libpq-dev build dependencies; faster than pure-Python fallback |
| psycopg[pool] | 3.3.3 | Connection pooling | ConnectionPool for the worker process to avoid per-query connection overhead |
| APScheduler | 3.11.2 | In-process cron-style job scheduling | CronTrigger supports exact time-of-day scheduling (10am/1pm/5pm ET). Runs inside the worker container. Lightweight, no external dependency. |
| joblib | (already installed) | Model artifact loading | Already used for artifact persistence in Phase 6. `joblib.load()` returns the `{model, calibrator, feature_cols}` dict. |
| python-dotenv | 1.0.1 (already installed) | Environment variable management | Already in requirements.txt. Load DATABASE_URL and KALSHI_API_KEY from .env |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytz | (stdlib zoneinfo preferred) | Timezone handling for ET scheduling | APScheduler CronTrigger needs timezone='US/Eastern'. Python 3.11 has `zoneinfo` built-in. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| psycopg3 (raw SQL) | SQLAlchemy + Alembic | Overkill for 3 tables with known-stable schema. SQLAlchemy adds ~15K lines of abstraction for simple INSERT/SELECT. |
| APScheduler | System crontab in Docker | Crontab works but requires a separate cron process in the container. APScheduler runs in the same Python process -- simpler logging, error handling, graceful shutdown. |
| APScheduler | schedule library | `schedule` is simpler but has no timezone support and no job persistence. APScheduler's CronTrigger is purpose-built for "run at 10am ET daily". |
| Raw SQL migrations | Alembic | Alembic is overkill: the schema is designed once and changes rarely. A single `schema.sql` file with CREATE TABLE IF NOT EXISTS is sufficient. |

**Installation:**
```bash
pip install "psycopg[binary,pool]" APScheduler
```

**Version verification:** psycopg 3.3.3 (2026-02-18), APScheduler 3.11.2 (latest stable). Both verified via PyPI. Python 3.11.9 is within supported range for both.

## Architecture Patterns

### Recommended Project Structure
```
src/
  pipeline/
    __init__.py
    runner.py          # Main pipeline orchestrator (fetch -> features -> predict -> store)
    scheduler.py       # APScheduler setup with CronTrigger jobs
    db.py              # Postgres connection pool, insert/update helpers
    schema.sql         # CREATE TABLE statements (run once or on startup)
    live_features.py   # Adapter: FeatureBuilder for single-day live prediction
    health.py          # Health check data aggregation
  data/
    kalshi.py          # (existing) -- extend with fetch_kalshi_live_prices()
    mlb_schedule.py    # (existing) -- extend with fetch_today_schedule()
  models/
    artifacts/         # (existing) -- joblib files loaded at startup
scripts/
  run_pipeline.py      # Entry point: loads models, starts scheduler, blocks
```

### Pattern 1: Artifact Loading at Startup
**What:** Load all 6 model artifacts once at process start, hold in memory, pass to pipeline runs.
**When to use:** Always -- model loading is expensive (RF artifacts are ~6MB), inference is cheap.
**Example:**
```python
# Source: project's run_v2_training.py artifact format
import joblib
from pathlib import Path

ARTIFACT_DIR = Path("models/artifacts")
ARTIFACT_NAMES = [
    "lr_team_only", "lr_sp_enhanced",
    "rf_team_only", "rf_sp_enhanced",
    "xgb_team_only", "xgb_sp_enhanced",
]

def load_all_artifacts() -> dict[str, dict]:
    """Load all 6 model artifacts at startup. Fail hard if any missing."""
    artifacts = {}
    for name in ARTIFACT_NAMES:
        path = ARTIFACT_DIR / f"{name}.joblib"
        if not path.exists():
            raise FileNotFoundError(f"Missing model artifact: {path}")
        artifact = joblib.load(path)
        # Each artifact is: {model, calibrator, feature_cols, model_name, feature_set}
        artifacts[name] = artifact
    return artifacts
```

### Pattern 2: Three-Run Pipeline with Version Semantics
**What:** Each pipeline run is parameterized by `prediction_version` (pre_lineup, post_lineup, confirmation), which determines which feature set to use, whether SPs must be confirmed, and how to handle is_latest flags.
**When to use:** Core pipeline dispatch pattern.
**Example:**
```python
def run_pipeline(version: str, artifacts: dict, db_pool):
    """
    version: 'pre_lineup' | 'post_lineup' | 'confirmation'

    pre_lineup:    TEAM_ONLY models only, SP fields null
    post_lineup:   SP_ENHANCED models (only for games with confirmed SPs)
    confirmation:  Full re-run, compare SPs to post_lineup, flag changes
    """
    games = fetch_today_schedule()  # statsapi.schedule(date=today)

    for game in games:
        if version == 'pre_lineup':
            features = build_team_only_features(game)
            run_models(artifacts, 'team_only', features, game, version, db_pool)
        elif version in ('post_lineup', 'confirmation'):
            home_sp, away_sp = game['home_probable_pitcher'], game['away_probable_pitcher']
            if sp_confirmed(home_sp) and sp_confirmed(away_sp):
                features = build_sp_enhanced_features(game, home_sp, away_sp)
                run_models(artifacts, 'sp_enhanced', features, game, version, db_pool)
                run_models(artifacts, 'team_only', features, game, version, db_pool)
            else:
                # TBD starters: TEAM_ONLY only, sp_uncertainty=True
                features = build_team_only_features(game)
                run_models(artifacts, 'team_only', features, game, version, db_pool,
                          sp_uncertainty=True)
```

### Pattern 3: Confirmation Run Change Detection
**What:** The 5pm confirmation run compares current SP assignments against the 1pm post_lineup predictions. If a starter changed, mark old row `is_latest=FALSE`, insert new row with `sp_may_have_changed=TRUE`.
**When to use:** Exclusively in the confirmation run.
**Example:**
```python
def handle_confirmation(game, current_sp, db_pool):
    """Compare current SP to post_lineup SP. Flag changes."""
    existing = get_post_lineup_prediction(game['game_id'], db_pool)
    if existing and (existing['home_sp'] != current_sp['home'] or
                     existing['away_sp'] != current_sp['away']):
        mark_not_latest(existing['id'], db_pool)
        insert_prediction(game, current_sp, version='confirmation',
                         sp_may_have_changed=True, db_pool=db_pool)
    else:
        # SPs unchanged -- confirmation row still inserted (full re-run)
        insert_prediction(game, current_sp, version='confirmation',
                         sp_may_have_changed=False, db_pool=db_pool)
```

### Pattern 4: Database-Level Invariant Enforcement
**What:** Use a Postgres CHECK constraint with a `prediction_status` enum to prevent post_lineup rows without confirmed starters.
**When to use:** Schema design -- enforces PIPE-07 at the database level, not just application code.
**Example:**
```sql
CREATE TYPE prediction_status AS ENUM ('confirmed', 'pending_sp', 'tbd');

-- The CHECK ensures post_lineup can only exist when status is 'confirmed'
ALTER TABLE predictions ADD CONSTRAINT chk_post_lineup_confirmed
  CHECK (
    prediction_version != 'post_lineup'
    OR prediction_status = 'confirmed'
  );
```

### Anti-Patterns to Avoid
- **Duplicating feature logic outside FeatureBuilder:** The project constraint doc explicitly warns "FeatureBuilder must be shared between backtest and live pipelines." The live pipeline must adapt the existing FeatureBuilder, not rewrite feature computation.
- **Loading models inside each pipeline run:** Model loading (especially RF at 6MB) should happen once at startup, not per-run. Hold artifacts in memory.
- **Computing edge_signal at query time:** Requirements specify edge is computed at insert time and stored. This avoids stale Kalshi prices corrupting historical edge analysis.
- **Using ORM for simple table operations:** With 3 tables and well-defined INSERT/SELECT patterns, an ORM adds complexity without benefit.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cron scheduling in Python | Custom sleep loop with time checks | APScheduler CronTrigger | Handles DST, missed fire policies, timezone-aware scheduling. Sleep loops drift and miss edge cases. |
| Connection pooling | Opening/closing connections per query | psycopg ConnectionPool | Pool manages lifecycle, handles stale connections, reconnects automatically |
| Timezone conversion for ET scheduling | Manual UTC offset math | `zoneinfo.ZoneInfo("US/Eastern")` (stdlib) | EDT/EST transitions are tricky. stdlib handles them correctly. |
| Feature engineering for live data | Rewriting feature computation | Adapt existing `FeatureBuilder` | Project constraint: single source of truth for feature logic. Divergence causes "great backtest, terrible live" failure. |
| Edge signal computation | Re-deriving the edge formula | `src.models.edge.compute_edge_signals()` | Already implemented and tested. Reuse the module. |
| Team name normalization | Ad-hoc string matching | `src.data.team_mappings.normalize_team()` | Already handles 100+ variants including Kalshi-specific codes |

**Key insight:** The pipeline is an orchestration layer, not a computation layer. All heavy lifting (features, models, edge signals, team normalization) already exists in `src/`. The pipeline's job is: fetch today's data, wire it through existing modules, and persist results to Postgres.

## Common Pitfalls

### Pitfall 1: Fetching Today's Schedule with Status Filter
**What goes wrong:** The existing `fetch_schedule()` filters to `status == "Final"` games only. For live predictions, we need games that have NOT yet been played (status "Scheduled", "Pre-Game", "Warmup", etc.).
**Why it happens:** The historical pipeline only cares about completed games. The live pipeline needs the opposite.
**How to avoid:** Write a new `fetch_today_schedule()` function that calls `statsapi.schedule(date=today_str, sportId=1)` and filters to `game_type == "R"` but does NOT filter on status. Return all games regardless of status.
**Warning signs:** Empty game list when you expect 15 games on a full MLB day.

### Pitfall 2: FeatureBuilder Designed for Batch, Not Live
**What goes wrong:** `FeatureBuilder.build()` loads entire season schedules, iterates all seasons, builds lookup tables from historical data. For live predictions, we need features for today's games only, using data available right now.
**Why it happens:** FeatureBuilder was designed for historical batch processing (Phases 2-6).
**How to avoid:** Create a `live_features.py` adapter that:
  1. Loads the current season's data up to yesterday (for rolling features)
  2. Constructs the feature row for each today's game
  3. Reuses the same formulas and lookups from FeatureBuilder but doesn't rebuild everything from scratch
  Important: Do NOT duplicate feature logic. Either refactor FeatureBuilder to accept a "mode" parameter, or build a thin wrapper that calls FeatureBuilder's private methods.
**Warning signs:** Feature values for live predictions differing from what backtest would produce for the same game.

### Pitfall 3: Kalshi Ticker Construction for Live Games
**What goes wrong:** The existing `kalshi.py` fetches settled markets. For live predictions, we need to fetch OPEN markets for today's games. The ticker format is `KXMLBGAME-{game_id}-{TEAM}`, and we need to construct the right ticker or search by series.
**Why it happens:** Phase 4 only needed historical (settled) data.
**How to avoid:** Use `GET /markets?status=open&series_ticker=KXMLBGAME` to fetch all open MLB game markets, then match by date and team codes (same parsing as existing `_parse_ticker()`). Use `yes_ask_dollars` or `last_price_dollars` for the current price signal.
**Warning signs:** No Kalshi prices found for today's games. Likely a status filter issue (using "settled" instead of "open").

### Pitfall 4: Timezone Handling for ET Scheduling
**What goes wrong:** APScheduler cron jobs fire at wrong times because the server is in UTC but schedules are specified in ET.
**Why it happens:** EDT (UTC-4) vs EST (UTC-5) transition is easy to forget.
**How to avoid:** Always pass `timezone='US/Eastern'` to CronTrigger. Use `zoneinfo.ZoneInfo("US/Eastern")` for all time comparisons. Store `pipeline_runs.run_started_at` in UTC.
**Warning signs:** Pipeline running at 2pm ET instead of 1pm ET after DST change.

### Pitfall 5: Race Condition on is_latest Flag
**What goes wrong:** If two pipeline runs overlap (e.g., slow 1pm run still writing when 5pm confirmation starts), both may see stale `is_latest` state.
**Why it happens:** No locking or atomic update pattern.
**How to avoid:** Use a single transaction for the confirmation run's "read existing + mark old + insert new" operation. Postgres row-level locking within the transaction prevents races. Also add a `pipeline_runs` lock: don't start a new run if a previous run of the same version for the same date is still in progress.
**Warning signs:** Multiple rows with `is_latest=TRUE` for the same game and version.

### Pitfall 6: SP Name Format Mismatch Between MLB API and Model
**What goes wrong:** MLB Stats API returns pitcher names like "Gerrit Cole" but FanGraphs (used in training) may have subtle differences. The existing 5-tier resolution chain in FeatureBuilder handles this for historical data, but live prediction needs the same resolution.
**Why it happens:** Name format inconsistency across data sources.
**How to avoid:** Reuse `FeatureBuilder._resolve_sp_stats()` and the full ID bridge infrastructure. Do not write a simpler name-matching shortcut for live.
**Warning signs:** SP features all coming back as NaN for live predictions despite known starters.

### Pitfall 7: Prediction Row Uniqueness
**What goes wrong:** Re-running the pipeline (e.g., after a crash) inserts duplicate rows for the same game/version combination.
**Why it happens:** No unique constraint on (game_date, home_team, away_team, prediction_version) or similar.
**How to avoid:** Add a UNIQUE constraint on `(game_date, home_team, away_team, prediction_version)` with an ON CONFLICT strategy (either UPSERT or skip). The confirmation run is a special case: it may need to insert a new row if SP changed, but should update in place if SP unchanged.
**Warning signs:** Duplicate predictions appearing in API responses.

## Code Examples

Verified patterns from the existing codebase and official sources:

### Loading and Using Model Artifacts for Inference
```python
# Source: project's run_v2_training.py lines 100-111 (verified artifact format)
import joblib
import numpy as np
import pandas as pd

artifact = joblib.load("models/artifacts/lr_sp_enhanced.joblib")
model = artifact["model"]         # Fitted sklearn Pipeline or XGBClassifier
calibrator = artifact["calibrator"]  # Fitted IsotonicRegression
feature_cols = artifact["feature_cols"]  # List of 17 feature column names

# For a single game's features (as a 1-row DataFrame):
X = pd.DataFrame([features_dict])[feature_cols]
raw_prob = model.predict_proba(X)[:, 1]
calibrated_prob = calibrator.predict(raw_prob)
# calibrated_prob[0] is P(home_win) for this game
```

### Fetching Today's Games (Live Schedule)
```python
# Source: existing mlb_schedule.py pattern + statsapi docs
import statsapi
from datetime import date

def fetch_today_schedule() -> list[dict]:
    """Fetch today's MLB games with probable pitchers."""
    today = date.today().strftime("%m/%d/%Y")
    games = statsapi.schedule(start_date=today, end_date=today, sportId=1)
    # Filter to regular season only
    return [g for g in games if g.get("game_type") == "R"]
```

### Fetching Live Kalshi Prices
```python
# Source: existing kalshi.py pagination pattern + Kalshi API docs
def fetch_kalshi_live_prices() -> dict[str, float]:
    """Fetch current Kalshi prices for open MLB game markets.

    Returns: {game_key: yes_price} where game_key = "YYYY-MM-DD_HOME_AWAY"
    """
    markets = _paginate_endpoint("markets", {
        "status": "open",
        "series_ticker": "KXMLBGAME",
    })
    prices = {}
    for m in markets:
        parsed = _parse_ticker(m.get("ticker", ""))
        if not parsed:
            continue
        home = _safe_normalize(parsed["home_code"])
        away = _safe_normalize(parsed["away_code"])
        # Use last_price_dollars or yes_ask_dollars for current signal
        if parsed["is_home_yes"]:
            key = f"{parsed['date']}_{home}_{away}"
            price = float(m.get("last_price_dollars", "0") or "0")
            if price > 0:
                prices[key] = price
    return prices
```

### Postgres Schema (Core Tables)
```sql
-- Source: Phase 7 requirements PIPE-01
CREATE TYPE prediction_version AS ENUM ('pre_lineup', 'post_lineup', 'confirmation');
CREATE TYPE prediction_status AS ENUM ('confirmed', 'pending_sp', 'tbd');

CREATE TABLE IF NOT EXISTS games (
    id             SERIAL PRIMARY KEY,
    game_date      DATE NOT NULL,
    home_team      VARCHAR(3) NOT NULL,
    away_team      VARCHAR(3) NOT NULL,
    game_id        INTEGER,        -- MLB Stats API gamePk
    home_score     INTEGER,
    away_score     INTEGER,
    home_win       BOOLEAN,
    status         VARCHAR(20),    -- 'Scheduled', 'Final', etc.
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (game_date, home_team, away_team)
);

CREATE TABLE IF NOT EXISTS predictions (
    id                    SERIAL PRIMARY KEY,
    game_date             DATE NOT NULL,
    home_team             VARCHAR(3) NOT NULL,
    away_team             VARCHAR(3) NOT NULL,
    prediction_version    prediction_version NOT NULL,
    prediction_status     prediction_status NOT NULL DEFAULT 'tbd',

    -- Model probabilities (calibrated P(home_win))
    lr_prob               REAL,
    rf_prob               REAL,
    xgb_prob              REAL,

    -- Feature set used
    feature_set           VARCHAR(20) NOT NULL,  -- 'team_only' or 'sp_enhanced'

    -- SP metadata
    home_sp               VARCHAR(100),
    away_sp               VARCHAR(100),
    sp_uncertainty         BOOLEAN DEFAULT FALSE,
    sp_may_have_changed    BOOLEAN DEFAULT FALSE,

    -- Kalshi data
    kalshi_yes_price       REAL,
    edge_signal            VARCHAR(10),  -- 'BUY_YES', 'BUY_NO', 'NO_EDGE'

    -- Lifecycle
    is_latest              BOOLEAN DEFAULT TRUE,
    created_at             TIMESTAMPTZ DEFAULT NOW(),

    -- DB-level invariant: post_lineup requires confirmed starters
    CONSTRAINT chk_post_lineup_confirmed CHECK (
        prediction_version != 'post_lineup'
        OR prediction_status = 'confirmed'
    ),
    -- Prevent exact duplicates (re-run safety)
    CONSTRAINT uq_prediction UNIQUE (game_date, home_team, away_team, prediction_version, is_latest)
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                SERIAL PRIMARY KEY,
    prediction_version prediction_version NOT NULL,
    run_date          DATE NOT NULL,
    run_started_at    TIMESTAMPTZ NOT NULL,
    run_finished_at   TIMESTAMPTZ,
    status            VARCHAR(20) NOT NULL DEFAULT 'running',  -- 'running', 'success', 'failed'
    games_processed   INTEGER DEFAULT 0,
    error_message     TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_predictions_date ON predictions (game_date);
CREATE INDEX IF NOT EXISTS idx_predictions_latest ON predictions (game_date, is_latest) WHERE is_latest = TRUE;
CREATE INDEX IF NOT EXISTS idx_predictions_version ON predictions (game_date, prediction_version);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_date ON pipeline_runs (run_date, prediction_version);
```

### APScheduler CronTrigger Setup
```python
# Source: APScheduler 3.x docs + project requirements (10am/1pm/5pm ET)
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = BlockingScheduler()

scheduler.add_job(
    run_pipeline,
    CronTrigger(hour=10, minute=0, timezone="US/Eastern"),
    args=["pre_lineup", artifacts, db_pool],
    id="pre_lineup",
    misfire_grace_time=300,  # 5 min grace period
)

scheduler.add_job(
    run_pipeline,
    CronTrigger(hour=13, minute=0, timezone="US/Eastern"),
    args=["post_lineup", artifacts, db_pool],
    id="post_lineup",
    misfire_grace_time=300,
)

scheduler.add_job(
    run_pipeline,
    CronTrigger(hour=17, minute=0, timezone="US/Eastern"),
    args=["confirmation", artifacts, db_pool],
    id="confirmation",
    misfire_grace_time=300,
)

scheduler.start()  # Blocks forever
```

### Edge Signal Computation at Insert Time
```python
# Source: existing src/models/edge.py (verified)
from src.models.edge import KALSHI_FEE_RATE

def compute_edge_for_prediction(model_prob: float, kalshi_price: float,
                                 threshold: float = 0.05) -> str:
    """Compute edge signal for a single prediction.

    Returns 'BUY_YES', 'BUY_NO', or 'NO_EDGE'.
    """
    if kalshi_price is None or kalshi_price <= 0:
        return 'NO_EDGE'
    edge = model_prob - kalshi_price
    if abs(edge) <= threshold:
        return 'NO_EDGE'
    return 'BUY_YES' if edge > 0 else 'BUY_NO'
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| psycopg2 | psycopg 3.3.x | 2021+ | Context manager closes connections, pipeline mode, native async. New code should use psycopg3. |
| CalibratedClassifierCV(cv='prefit') | IsotonicRegression directly | sklearn 1.8.0 | This project already uses the current approach (Phase 6). Artifacts contain fitted IsotonicRegression objects. |
| APScheduler 4.x alpha | APScheduler 3.11.x stable | Ongoing | APScheduler 4 is in alpha and not production-ready. Stick with 3.x for stability. |
| Kalshi v1 API | Kalshi v2 trade API | 2024 | Existing kalshi.py already uses v2 (api.elections.kalshi.com/trade-api/v2). Same base URL for live markets. |

**Deprecated/outdated:**
- `psycopg2`: Still works but psycopg3 is the recommended path for new projects. psycopg3 has better context management and is production-stable.
- `APScheduler 4.x`: Still in alpha/beta. Do not use for production scheduling. The 3.x branch is actively maintained.

## Open Questions

1. **FeatureBuilder Refactoring Scope**
   - What we know: FeatureBuilder processes full seasons. Live pipeline needs single-day features. The formulas (pythagorean win%, log5, rolling OPS, park factor) are all in the existing code.
   - What's unclear: How much of FeatureBuilder can be reused directly vs. needs refactoring. The bulk of complexity is in SP features (season-to-date rolling stats require historical game logs).
   - Recommendation: Build a `LiveFeatureBuilder` adapter class that calls the existing data-fetching functions (fetch_sp_stats, _get_pitcher_id_map, _fetch_pitcher_game_log_v2, etc.) for the current season, computes features for today's games only, and reuses the same formulas. This is a new class, not a modification of FeatureBuilder, to avoid breaking backtest.

2. **Kalshi Live Price Timing**
   - What we know: Kalshi opens markets before game day. The API returns `last_price_dollars` (last trade) and `yes_ask_dollars` (current ask).
   - What's unclear: Whether KXMLBGAME markets are open early enough for the 10am ET pre_lineup run, and which price field best represents the "current market" price.
   - Recommendation: Use `last_price_dollars` if available (matches Phase 4 convention), fall back to `yes_ask_dollars`. If no market found, store NULL and edge_signal = 'NO_EDGE'. This is a graceful degradation, not a pipeline failure.

3. **Feature Data Freshness for Current Season**
   - What we know: FanGraphs SP stats (used for WHIP, SIERA, FIP, xFIP) are season-level aggregates. The current season's data must be fetched fresh (not from cache) for accurate live predictions.
   - What's unclear: pybaseball's `pitching_stats()` reliability for mid-season fetching (it may have Cloudflare issues noted in sp_recent_form.py).
   - Recommendation: For FanGraphs features, fetch with a short cache TTL (4 hours). For MLB Stats API features (game logs, schedule), fetch live with no caching for today's data. The pipeline should handle FanGraphs unavailability gracefully by using most-recent cached data.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.1.1 |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PIPE-01 | Schema creation, constraints, indexes | integration | `pytest tests/test_pipeline_db.py::test_schema_creation -x` | No -- Wave 0 |
| PIPE-01 | CHECK constraint prevents post_lineup without confirmed status | integration | `pytest tests/test_pipeline_db.py::test_post_lineup_constraint -x` | No -- Wave 0 |
| PIPE-02 | Pre-lineup run produces team_only predictions | integration | `pytest tests/test_pipeline_runner.py::test_pre_lineup_run -x` | No -- Wave 0 |
| PIPE-03 | Post-lineup run produces sp_enhanced predictions | integration | `pytest tests/test_pipeline_runner.py::test_post_lineup_run -x` | No -- Wave 0 |
| PIPE-04 | Confirmation run detects SP changes and flags them | unit | `pytest tests/test_pipeline_runner.py::test_confirmation_sp_change -x` | No -- Wave 0 |
| PIPE-05 | Edge signal computed correctly at insert time | unit | `pytest tests/test_pipeline_runner.py::test_edge_signal_insert -x` | No -- Wave 0 |
| PIPE-06 | SP name stored, sp_may_have_changed set correctly | unit | `pytest tests/test_pipeline_runner.py::test_sp_metadata_stored -x` | No -- Wave 0 |
| PIPE-07 | TBD starters produce TEAM_ONLY with sp_uncertainty=True | unit | `pytest tests/test_pipeline_runner.py::test_tbd_starters_fallback -x` | No -- Wave 0 |
| PIPE-07 | DB rejects post_lineup with non-confirmed status | integration | `pytest tests/test_pipeline_db.py::test_constraint_violation -x` | No -- Wave 0 |
| PIPE-08 | Pipeline runs logged, health data retrievable | integration | `pytest tests/test_pipeline_runner.py::test_pipeline_logging -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_pipeline_db.py tests/test_pipeline_runner.py -x -q`
- **Per wave merge:** `pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_pipeline_db.py` -- covers PIPE-01, PIPE-07 (schema + constraint tests, requires test Postgres or SQLite adapter)
- [ ] `tests/test_pipeline_runner.py` -- covers PIPE-02 through PIPE-08 (pipeline logic tests with mocked DB and data sources)
- [ ] `tests/conftest.py` -- add fixtures for: mock DB connection, sample game data, mock Kalshi responses, loaded model artifacts
- [ ] Docker Postgres for integration tests: `docker run -d --name mlb-test-pg -e POSTGRES_PASSWORD=test -p 5433:5432 postgres:16`

**Note on test strategy:** DB constraint tests (PIPE-01, PIPE-07) require a real Postgres instance (CHECK constraints and enums are Postgres-specific). Use a test Postgres container. Pipeline logic tests (PIPE-02 through PIPE-06, PIPE-08) can mock the DB layer and test the orchestration/feature/prediction logic in isolation.

## Sources

### Primary (HIGH confidence)
- Project codebase: `src/models/feature_sets.py`, `src/features/feature_builder.py`, `src/data/kalshi.py`, `src/data/mlb_schedule.py`, `src/models/edge.py`, `src/models/calibrate.py`, `scripts/run_v2_training.py`, `models/artifacts/model_metadata.json` -- direct inspection of artifact format, feature columns, data fetching patterns
- [psycopg PyPI](https://pypi.org/project/psycopg/) -- version 3.3.3, Python >=3.10, install instructions
- [psycopg3 documentation](https://www.psycopg.org/psycopg3/docs/) -- connection management, pooling, context managers
- [Kalshi API - Get Markets](https://docs.kalshi.com/api-reference/market/get-markets) -- query params (status, series_ticker), response fields (last_price_dollars, yes_ask_dollars)
- [PostgreSQL Enum Documentation](https://www.postgresql.org/docs/current/datatype-enum.html) -- enum type creation and usage

### Secondary (MEDIUM confidence)
- [APScheduler PyPI](https://pypi.org/project/APScheduler/) -- version 3.11.2, CronTrigger, timezone support
- [APScheduler 3.x documentation](https://apscheduler.readthedocs.io/en/3.x/) -- CronTrigger API, misfire_grace_time
- [MLB-StatsAPI GitHub Wiki](https://github.com/toddrob99/MLB-StatsAPI/wiki/Function:-schedule) -- schedule() function parameters
- [Crunchy Data: Enums vs Check Constraints](https://www.crunchydata.com/blog/enums-vs-check-constraints-in-postgres) -- tradeoffs for schema design
- [Close Engineering: Native enums or CHECK constraints](https://making.close.com/posts/native-enums-or-check-constraints-in-postgresql/) -- practical enum vs CHECK guidance

### Tertiary (LOW confidence)
- FanGraphs data availability for mid-season live fetching via pybaseball -- needs validation. The sp_recent_form.py already notes Cloudflare issues with BRef; FanGraphs may have similar issues. Recommend testing early.
- APScheduler job persistence across container restarts -- the scheduler runs in-memory by default. If the container restarts, missed jobs rely on `misfire_grace_time`. For this use case (3 daily runs), this is acceptable.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- psycopg3 and APScheduler are mature, well-documented, versions verified against PyPI
- Architecture: HIGH -- patterns derived directly from existing codebase (artifact format, feature engineering, edge computation are all inspected code)
- Pitfalls: HIGH -- identified from direct codebase analysis (status filter issue, FeatureBuilder batch design, Kalshi settled-vs-open)
- Validation: MEDIUM -- test strategy is clear but DB integration test setup (Docker Postgres) adds complexity

**Research date:** 2026-03-29
**Valid until:** 2026-04-28 (stable domain, 30 days)
