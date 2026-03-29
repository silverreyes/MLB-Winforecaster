# Architecture Research: v2.0 Live Platform

**Domain:** MLB Pre-Game Win Probability -- SP Feature Integration + Live Dashboard Deployment
**Researched:** 2026-03-29
**Confidence:** HIGH (existing codebase thoroughly analyzed; deployment pattern mirrors GamePredictor; standard FastAPI/Docker/Postgres patterns)

---

## 1. FeatureBuilder SP Integration Strategy

### Current State Analysis

The existing `_add_sp_features()` method in `src/features/feature_builder.py` (lines 120-178) already computes four SP differential features from FanGraphs season-level data:

| Feature | Source | Coverage |
|---------|--------|----------|
| `sp_fip_diff` | FanGraphs `pitching_stats` | 83.1% |
| `sp_xfip_diff` | FanGraphs `pitching_stats` | 83.1% |
| `sp_k_pct_diff` | FanGraphs `pitching_stats` | 83.1% |
| `sp_siera_diff` | FanGraphs `pitching_stats` | 83.1% |

Additionally, `_add_advanced_features()` (lines 426-529) computes `sp_recent_era_diff` (30-day rolling ERA from MLB Stats API game logs, 89.4% coverage) and `xwoba_diff` (currently 100% NaN due to ADVF-07 bug).

### Recommendation: Extend `_add_sp_features()`, Do NOT Create a Separate Method

**Rationale:** The new SP features (ERA, home/away splits, workload, BB%, WHIP) draw from the same FanGraphs `pitching_stats` data source that `_add_sp_features()` already queries via `fetch_sp_stats()`. The existing `sp_lookup` dictionary at line 128 already extracts `ERA` (line 139) but does not use it as a differential feature. Adding new features to this same method keeps the single-pass lookup pattern and avoids a second iteration over the same data.

### New SP Features to Add

| Feature | Column Name | Source | Notes |
|---------|-------------|--------|-------|
| ERA differential | `sp_era_diff` | `sp_lookup["ERA"]` | Already extracted at line 139 but unused |
| BB% differential | `sp_bb_pct_diff` | `fetch_sp_stats` `BB%` column | Available in FanGraphs data |
| WHIP differential | `sp_whip_diff` | `fetch_sp_stats` `WHIP` column | Available in FanGraphs data |
| SP workload (IP) | `sp_ip_diff` | `fetch_sp_stats` `IP` column | Season IP as stamina proxy |
| Home/Away ERA split | `sp_split_era_diff` | **New data source needed** | FanGraphs splits; see note below |

**Home/Away splits note:** FanGraphs' `pitching_stats` returns season aggregates, not home/away splits. True split data requires `pybaseball.pitching_stats` with `split_seasons=True` or a separate FanGraphs splits endpoint. Given that BRef/FanGraphs are behind Cloudflare (discovered in v1.0, documented in `sp_recent_form.py` line 6), this data may be unreliable. **Recommendation:** Defer home/away splits to a later iteration; the `is_home` and `park_factor` features already capture home advantage at the venue level.

### Exact Code Changes in `_add_sp_features()`

**Modified:** `src/features/feature_builder.py` -- `_add_sp_features()` method

1. Extend the `sp_lookup` dictionary to include `BB%`, `WHIP`, `IP` (currently only extracts `FIP`, `xFIP`, `K%`, `SIERA`, `ERA`)
2. Add mapping loops for new stats (same pattern as lines 142-153)
3. Add differential computations: `sp_era_diff`, `sp_bb_pct_diff`, `sp_whip_diff`, `sp_ip_diff`
4. Drop intermediate columns (same pattern as lines 166-178)

**Modified:** `src/models/feature_sets.py` -- `FULL_FEATURE_COLS` list

Add new columns to `FULL_FEATURE_COLS`. The `CORE_FEATURE_COLS` list (line 32) currently excludes only `sp_recent_era_diff`; define a new `SP_ENHANCED_FEATURE_COLS` that includes all new SP features for the post-lineup model variant:

```python
# v2 feature sets
TEAM_ONLY_FEATURE_COLS = CORE_FEATURE_COLS  # Alias: pre-lineup predictions (no SP-specific)
SP_ENHANCED_FEATURE_COLS = FULL_FEATURE_COLS + [
    'sp_era_diff',
    'sp_bb_pct_diff',
    'sp_whip_diff',
    'sp_ip_diff',
]
```

### ADVF-07 Fix (xwOBA Column Pipeline)

The `_add_advanced_features()` method at line 434 has two bugs documented in PROJECT.md:
1. Statcast returns `'last_name, first_name'` as a single merged column (not separate `last_name` and `first_name` columns)
2. The xwOBA column is named `est_woba` in Statcast data, not `xwoba`

**Fix location:** `src/features/feature_builder.py` lines 440-455 (the `if "last_name" in sc_df.columns` branch)

The fix must handle the comma-separated name format from `pybaseball.statcast_pitcher_expected_stats()` and map `est_woba` to the lookup key. This will recover `xwoba_diff` from 0% to approximately 80-85% coverage.

### Impact on Existing Cached Parquet Files

**Feature store Parquet files must be regenerated.** The feature store (`data/cache/` via `src/data/cache.py`) stores raw source data (schedule, SP stats, team batting, Statcast) as separate Parquet files keyed by `(data_type, season)`. These raw caches do NOT need regeneration -- they contain the same source data. However:

1. **Raw SP stats caches (`sp_stats_{season}_mings{N}.parquet`):** Already contain `BB%`, `WHIP`, `IP`, `ERA` columns. No refetch needed.
2. **Feature matrix Parquet (if persisted):** Must be regenerated via `FeatureBuilder.build()` because new columns are added. The v1.0 pipeline does not persist the feature matrix -- it is recomputed per notebook run. No stale cache risk.
3. **Backtest results (`backtest_results.parquet` if persisted):** Must be regenerated since models are retrained with expanded feature set.

**Bottom line:** Raw data caches survive; feature matrix and backtest results are rebuilt. No migration script needed.

### Backward Compatibility: Pre-Lineup vs. Post-Lineup Predictions

The twice-daily pipeline produces two prediction versions:

| Run | Time | Feature Set | SP Data Available? |
|-----|------|-------------|-------------------|
| Pre-lineup | 10am ET | `TEAM_ONLY_FEATURE_COLS` | No -- starters may not be confirmed |
| Post-lineup | 1pm ET | `SP_ENHANCED_FEATURE_COLS` | Yes -- lineups posted ~11:30am ET |

**Implementation:** The `FeatureBuilder` already handles TBD starters via `_filter_tbd_starters()` (line 106). For pre-lineup predictions, the pipeline should:
1. Run `FeatureBuilder.build()` as normal (games with TBD starters are included but SP features are NaN)
2. Use `TEAM_ONLY_FEATURE_COLS` which excludes all SP-specific columns
3. The team-only model (trained on historical data without SP features) produces valid predictions

For post-lineup predictions:
1. Re-run `FeatureBuilder.build()` (or just re-fetch schedule to get confirmed SPs)
2. Use `SP_ENHANCED_FEATURE_COLS`
3. Games where SPs are still TBD/scratched fall back to team-only prediction with an `is_sp_confirmed` flag

**New field:** Add `prediction_version` enum (`pre_lineup` / `post_lineup`) to all pipeline outputs and database records.

---

## 2. Postgres Schema Design

### Design Principles

- One table per logical entity (games, predictions, pipeline runs)
- Both prediction versions (pre-lineup, post-lineup) stored as separate rows, not columns
- All three model probabilities (LR, RF, XGB) stored per prediction row
- Kalshi price is per-game, not per-prediction (fetched once per game)
- `is_latest` flag enables efficient "current predictions" query without subquery

### Schema

```sql
-- Games table: one row per MLB game per day
CREATE TABLE games (
    id              SERIAL PRIMARY KEY,
    game_date       DATE NOT NULL,
    home_team       VARCHAR(3) NOT NULL,
    away_team       VARCHAR(3) NOT NULL,
    home_score      SMALLINT,           -- NULL until game final
    away_score      SMALLINT,           -- NULL until game final
    home_win        BOOLEAN,            -- NULL until game final
    home_sp         VARCHAR(80),        -- NULL if TBD
    away_sp         VARCHAR(80),        -- NULL if TBD
    sp_confirmed    BOOLEAN NOT NULL DEFAULT FALSE,
    kalshi_yes_price NUMERIC(5,4),      -- 0.0000-1.0000, NULL if no market
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (game_date, home_team, away_team)
);

-- Predictions table: one row per (game, prediction_version)
-- Contains all three model probabilities in one row (not normalized to one row per model)
-- Rationale: the dashboard always displays all three models together;
-- normalizing to per-model rows triples row count for zero query benefit
CREATE TABLE predictions (
    id              SERIAL PRIMARY KEY,
    game_id         INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    version         VARCHAR(12) NOT NULL CHECK (version IN ('pre_lineup', 'post_lineup')),
    lr_prob         NUMERIC(5,4),       -- Logistic Regression calibrated prob
    rf_prob         NUMERIC(5,4),       -- Random Forest calibrated prob
    xgb_prob        NUMERIC(5,4),       -- XGBoost calibrated prob
    lr_raw          NUMERIC(5,4),       -- LR uncalibrated (for diagnostics)
    rf_raw          NUMERIC(5,4),       -- RF uncalibrated
    xgb_raw         NUMERIC(5,4),       -- XGB uncalibrated
    feature_set     VARCHAR(20) NOT NULL, -- 'team_only' or 'sp_enhanced'
    edge_lr         NUMERIC(5,4),       -- lr_prob - kalshi_yes_price
    edge_rf         NUMERIC(5,4),       -- rf_prob - kalshi_yes_price
    edge_xgb        NUMERIC(5,4),       -- xgb_prob - kalshi_yes_price
    is_latest       BOOLEAN NOT NULL DEFAULT TRUE,
    pipeline_run_id INTEGER REFERENCES pipeline_runs(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (game_id, version, pipeline_run_id)
);

-- Index for the primary dashboard query: "today's latest predictions"
CREATE INDEX idx_predictions_latest ON predictions (is_latest, created_at DESC)
    WHERE is_latest = TRUE;
CREATE INDEX idx_predictions_game_version ON predictions (game_id, version);

-- Pipeline runs: audit trail for each cron execution
CREATE TABLE pipeline_runs (
    id              SERIAL PRIMARY KEY,
    run_type        VARCHAR(12) NOT NULL CHECK (run_type IN ('pre_lineup', 'post_lineup', 'backfill', 'manual')),
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMPTZ,
    status          VARCHAR(10) NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'success', 'failed')),
    games_processed INTEGER DEFAULT 0,
    error_message   TEXT,
    model_version   VARCHAR(20)         -- e.g., 'v2.0.0' for artifact tracking
);

-- Historical results: join games with actual outcomes for accuracy tracking
-- (This is a VIEW, not a separate table)
CREATE VIEW prediction_results AS
SELECT
    g.game_date,
    g.home_team,
    g.away_team,
    g.home_win,
    g.home_sp,
    g.away_sp,
    g.kalshi_yes_price,
    p.version,
    p.lr_prob,
    p.rf_prob,
    p.xgb_prob,
    p.edge_lr,
    p.edge_rf,
    p.edge_xgb,
    p.feature_set,
    p.created_at AS predicted_at
FROM predictions p
JOIN games g ON p.game_id = g.id
WHERE p.is_latest = TRUE
  AND g.home_win IS NOT NULL;
```

### `is_latest` Flag Management

When a new prediction is inserted for the same `(game_id, version)`:
1. Set `is_latest = FALSE` on all existing rows for that `(game_id, version)`
2. Insert new row with `is_latest = TRUE`

This avoids expensive `DISTINCT ON` or window function queries for the dashboard. A simple trigger or application-level logic handles the update:

```sql
-- Application logic (in Python, not a trigger -- keeps schema simple)
-- Before insert:
UPDATE predictions SET is_latest = FALSE
WHERE game_id = :game_id AND version = :version AND is_latest = TRUE;
-- Then INSERT the new row with is_latest = TRUE
```

### Edge Computation

Edge values (`edge_lr`, `edge_rf`, `edge_xgb`) are computed at insert time by the pipeline, not by the API at query time. This means:
- Dashboard reads are pure `SELECT` with no computation
- If Kalshi price updates, the pipeline re-inserts predictions with recalculated edges (marks old row as `is_latest = FALSE`)

### Row Count Estimates

| Table | Rows per day | Rows per season (162 games x 30 teams / 2) |
|-------|-------------|---------------------------------------------|
| `games` | ~15 | ~2,430 |
| `predictions` | ~30 (15 games x 2 versions) | ~4,860 |
| `pipeline_runs` | 2 | ~324 |

At this scale, Postgres handles everything with zero performance concerns. No partitioning, no archival needed for years.

---

## 3. FastAPI Service Architecture

### Endpoint Design

| Method | Path | Response | Used By |
|--------|------|----------|---------|
| `GET` | `/api/v1/predictions/today` | Today's games with latest predictions (both versions) | Dashboard home page |
| `GET` | `/api/v1/predictions/{date}` | Predictions for a specific date (YYYY-MM-DD) | Dashboard historical view |
| `GET` | `/api/v1/predictions/latest-timestamp` | `{ "timestamp": "2026-03-29T13:05:00Z" }` | Client-side polling for updates |
| `GET` | `/api/v1/results` | Historical results with actual outcomes, paginated | Dashboard results page |
| `GET` | `/api/v1/results/accuracy` | Aggregate accuracy stats (Brier scores by model, by month) | Dashboard stats section |
| `GET` | `/api/v1/health` | `{ "status": "ok", "db": true, "models_loaded": true, "last_pipeline_run": "..." }` | Monitoring, uptime checks |

### Response Shape: `/api/v1/predictions/today`

```json
{
  "date": "2026-03-29",
  "last_updated": "2026-03-29T13:05:00Z",
  "games": [
    {
      "game_date": "2026-03-29",
      "home_team": "NYY",
      "away_team": "BOS",
      "home_sp": "Gerrit Cole",
      "away_sp": "Brayan Bello",
      "sp_confirmed": true,
      "kalshi_yes_price": 0.5800,
      "predictions": {
        "pre_lineup": {
          "feature_set": "team_only",
          "lr_prob": 0.5523,
          "rf_prob": 0.5612,
          "xgb_prob": 0.5701,
          "edge_lr": -0.0277,
          "edge_rf": -0.0188,
          "edge_xgb": -0.0099,
          "predicted_at": "2026-03-29T10:05:00Z"
        },
        "post_lineup": {
          "feature_set": "sp_enhanced",
          "lr_prob": 0.5891,
          "rf_prob": 0.5934,
          "xgb_prob": 0.6012,
          "edge_lr": 0.0091,
          "edge_rf": 0.0134,
          "edge_xgb": 0.0212,
          "predicted_at": "2026-03-29T13:05:00Z"
        }
      }
    }
  ]
}
```

### Model Artifact Management

**Location:** `/app/models/` inside the Docker container, mapped from a named Docker volume `model_artifacts`.

**Artifacts persisted (pkl/joblib files):**

| File | Contents | Size (est.) |
|------|----------|-------------|
| `lr_team_only.joblib` | Fitted LR Pipeline + IsotonicRegression calibrator | ~50 KB |
| `rf_team_only.joblib` | Fitted RF Pipeline + IsotonicRegression calibrator | ~5 MB |
| `xgb_team_only.joblib` | Fitted XGBClassifier + IsotonicRegression calibrator | ~2 MB |
| `lr_sp_enhanced.joblib` | Fitted LR Pipeline + IsotonicRegression calibrator | ~50 KB |
| `rf_sp_enhanced.joblib` | Fitted RF Pipeline + IsotonicRegression calibrator | ~5 MB |
| `xgb_sp_enhanced.joblib` | Fitted XGBClassifier + IsotonicRegression calibrator | ~2 MB |
| `model_metadata.json` | Training date, feature columns, fold info, Brier scores | ~2 KB |

**Total: ~15 MB** -- trivial for the 8 GB RAM VPS.

**Loading pattern:** FastAPI lifespan event (not deprecated `@app.on_event`):

```python
from contextlib import asynccontextmanager
import joblib

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load all model artifacts into app.state
    app.state.models = {
        "lr_team_only": joblib.load("/app/models/lr_team_only.joblib"),
        "rf_team_only": joblib.load("/app/models/rf_team_only.joblib"),
        "xgb_team_only": joblib.load("/app/models/xgb_team_only.joblib"),
        "lr_sp_enhanced": joblib.load("/app/models/lr_sp_enhanced.joblib"),
        "rf_sp_enhanced": joblib.load("/app/models/rf_sp_enhanced.joblib"),
        "xgb_sp_enhanced": joblib.load("/app/models/xgb_sp_enhanced.joblib"),
    }
    app.state.model_metadata = json.load(open("/app/models/model_metadata.json"))
    yield
    # Shutdown: cleanup (optional, Python GC handles it)
    app.state.models.clear()

app = FastAPI(lifespan=lifespan)
```

**Why joblib over pickle:** joblib handles large NumPy arrays (RF's 300 decision trees) more efficiently. scikit-learn's own documentation recommends joblib for sklearn model persistence. Both the sklearn Pipeline and the IsotonicRegression calibrator are stored together in a dict per artifact file.

### FastAPI Project Structure

```
api/
    __init__.py
    main.py              # FastAPI app, lifespan, CORS
    config.py            # Settings via pydantic-settings (DATABASE_URL, MODEL_DIR, etc.)
    database.py          # SQLAlchemy async engine + session
    models/              # SQLAlchemy ORM models (games, predictions, pipeline_runs)
        __init__.py
        game.py
        prediction.py
        pipeline_run.py
    schemas/             # Pydantic response/request schemas
        __init__.py
        prediction.py
        result.py
        health.py
    routers/
        __init__.py
        predictions.py   # /api/v1/predictions/* endpoints
        results.py       # /api/v1/results/* endpoints
        health.py        # /api/v1/health endpoint
    services/
        __init__.py
        prediction_service.py  # Query logic, edge computation
        result_service.py      # Historical accuracy queries
```

### Database Access

Use SQLAlchemy 2.0 async with `asyncpg` driver:
- `DATABASE_URL = postgresql+asyncpg://mlb:password@db:5432/mlb_forecaster`
- Connection pool: min 2, max 5 (2 CPU VPS -- no point in large pool)
- Alembic for schema migrations (essential for production schema evolution)

---

## 4. Docker Compose Service Topology

### Services (Port 8082)

```yaml
version: "3.8"

services:
  # --- Database ---
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: mlb_forecaster
      POSTGRES_USER: mlb
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mlb -d mlb_forecaster"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - internal

  # --- FastAPI Backend (serves HTTP) ---
  api:
    build:
      context: .
      dockerfile: Dockerfile
    restart: unless-stopped
    command: uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 2
    ports:
      - "8082:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://mlb:${DB_PASSWORD}@db:5432/mlb_forecaster
      MODEL_DIR: /app/models
    volumes:
      - model_artifacts:/app/models
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - internal

  # --- Prediction Pipeline Worker (runs on cron schedule) ---
  worker:
    build:
      context: .
      dockerfile: Dockerfile
    restart: unless-stopped
    command: supercronic /app/crontab
    environment:
      DATABASE_URL: postgresql+psycopg2://mlb:${DB_PASSWORD}@db:5432/mlb_forecaster
      MODEL_DIR: /app/models
      KALSHI_API_KEY: ${KALSHI_API_KEY}
    volumes:
      - model_artifacts:/app/models
      - data_cache:/app/data/raw
    depends_on:
      db:
        condition: service_healthy
    networks:
      - internal

  # --- React Frontend (Nginx serving static build) ---
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    restart: unless-stopped
    networks:
      - internal

volumes:
  pgdata:
    driver: local
  model_artifacts:
    driver: local
  data_cache:
    driver: local

networks:
  internal:
    driver: bridge
```

### Service Responsibilities

| Service | Image | Responsibility | Scaling |
|---------|-------|---------------|---------|
| `db` | `postgres:16-alpine` | Persistent data storage, ACID transactions | Single instance (8 GB RAM is plenty) |
| `api` | Custom (Python + FastAPI) | Serve HTTP endpoints, load model artifacts at startup, return predictions | 2 uvicorn workers (matches 2 CPU) |
| `worker` | Same image as `api` | Run twice-daily pipeline (fetch today's games, compute features, predict, store in Postgres) | Single instance with supercronic |
| `frontend` | `node:20-alpine` build + `nginx:alpine` serve | Serve React static build | Single instance |

### Why `worker` Uses the Same Docker Image as `api`

Both services need:
- `src/` package (FeatureBuilder, data loaders, model training code)
- `api/` package (database models for writing predictions)
- Python dependencies (pandas, scikit-learn, xgboost, pybaseball)

Using the same image with a different `command` avoids maintaining two Dockerfiles and ensures the worker and API always use identical code versions. The only difference:
- `api` command: `uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 2`
- `worker` command: `supercronic /app/crontab`

### Why Supercronic Instead of Celery/APScheduler

| Option | Why Not |
|--------|---------|
| Celery + Redis | Requires Redis container, broker config, Flower monitoring. Massive overkill for 2 cron jobs per day. |
| APScheduler in-process | Runs inside the API process -- if the API restarts, scheduled jobs are lost. Couples scheduling to serving. |
| System cron | Doesn't inherit Docker environment variables, output doesn't appear in `docker logs`. |
| **Supercronic** | Purpose-built for containers. Reads crontab file, logs to stdout, handles signals properly. Zero dependencies. |

### Crontab File (`crontab`)

```
# Pre-lineup predictions: 10:00 AM ET (14:00 UTC during EDT, 15:00 UTC during EST)
0 14 * * * python -m pipeline.run --version pre_lineup >> /proc/1/fd/1 2>&1

# Post-lineup predictions: 1:00 PM ET (17:00 UTC during EDT, 18:00 UTC during EST)
0 17 * * * python -m pipeline.run --version post_lineup >> /proc/1/fd/1 2>&1
```

### Worker Pipeline Logic (`pipeline/run.py`)

```
1. Fetch today's schedule from MLB Stats API (live, not cached)
2. For each game:
   a. Upsert into games table (game_date, home_team, away_team, SP info)
   b. Fetch current Kalshi price, update games.kalshi_yes_price
3. Build feature vector for today's games using FeatureBuilder
   - Pre-lineup: use TEAM_ONLY_FEATURE_COLS (ignore SP columns even if available)
   - Post-lineup: use SP_ENHANCED_FEATURE_COLS (fallback to team-only if SP is TBD)
4. Load persisted model artifacts from /app/models/
5. Run predict_proba for all 3 models, apply IsotonicRegression calibration
6. Compute edge = model_prob - kalshi_yes_price for each model
7. Mark previous predictions for same (game_id, version) as is_latest=FALSE
8. Insert new prediction rows with is_latest=TRUE
9. Update pipeline_runs table with status=success and games_processed count
```

### Shared Volume: `model_artifacts`

Both `api` and `worker` mount the same `model_artifacts` volume at `/app/models/`. The worker writes model artifacts during retraining; the API reads them at startup. For the initial deployment, model artifacts are generated locally and copied into the volume. Subsequent retraining runs update the volume in-place.

**Model hot-reload:** Not needed for v2.0. Models are retrained monthly at most. The API service restarts after a retrain (the worker triggers `docker compose restart api` or the deploy script does).

---

## 5. Host Nginx Configuration

### Pattern: Following GamePredictor (Port 8080)

The existing GamePredictor stack uses:
- Docker Compose with internal Nginx + FastAPI/uvicorn + worker + Postgres
- Host Nginx (1.24.0) on the VPS reverse-proxies to port 8080
- Certbot manages SSL certificates

The MLB Forecaster follows the exact same pattern on port 8082.

### Nginx Vhost Configuration

**File:** `/etc/nginx/sites-available/mlbforecaster.silverreyes.net`

```nginx
# HTTP -> HTTPS redirect
server {
    listen 80;
    listen [::]:80;
    server_name mlbforecaster.silverreyes.net;

    # Certbot ACME challenge
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS reverse proxy to Docker Compose stack on port 8082
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name mlbforecaster.silverreyes.net;

    # Certbot-managed SSL certificates
    ssl_certificate     /etc/letsencrypt/live/mlbforecaster.silverreyes.net/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mlbforecaster.silverreyes.net/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # API endpoints -> FastAPI container
    location /api/ {
        proxy_pass http://127.0.0.1:8082;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts (pipeline health check can take a few seconds)
        proxy_connect_timeout 10s;
        proxy_read_timeout 30s;
    }

    # Frontend static assets -> same port (Docker internal Nginx serves these)
    location / {
        proxy_pass http://127.0.0.1:8082;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Cache static assets
        proxy_cache_valid 200 1h;
    }
}
```

**Wait -- the frontend and API are on the same port 8082?** Yes. Inside Docker Compose, the `api` service binds port 8082:8000. The React frontend can be served two ways:

**Option A (recommended): API serves frontend static files.** FastAPI mounts the React build output as static files. One exposed port, zero routing complexity.

**Option B: Internal Nginx in Docker Compose routes /api to API, / to frontend.** Adds an extra container. Only worth it if the frontend needs its own Nginx config (gzip, caching headers). For a simple React SPA, this is overkill.

**Recommendation: Option A.** FastAPI serves the React build directory via `StaticFiles` mount. The host Nginx handles SSL termination and proxies everything to port 8082. This matches the simplicity target of a 2-CPU VPS.

```python
# In api/main.py, AFTER all API routers are mounted:
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="/app/frontend/dist", html=True), name="frontend")
```

This means all `/api/*` routes are handled by FastAPI routers (matched first), and everything else falls through to the React SPA's `index.html`.

### SSL Certificate Setup

```bash
# On VPS as deploy user:
sudo certbot certonly --webroot -w /var/www/certbot \
    -d mlbforecaster.silverreyes.net \
    --email silver@silverreyes.net \
    --agree-tos --non-interactive

# Enable site and reload
sudo ln -s /etc/nginx/sites-available/mlbforecaster.silverreyes.net \
           /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Certbot auto-renewal is already configured system-wide via `systemd timer` or cron (set up for GamePredictor). The new cert renews automatically.

---

## 6. React Frontend Architecture

### Technology Choices

| Technology | Version | Why |
|------------|---------|-----|
| React | 19.x | Standard; team familiarity |
| Vite | 6.x | Fast builds, HMR, TypeScript out of box |
| TypeScript | 5.x | Type safety for API response shapes |
| Tailwind CSS | 4.x | Utility-first; easy dark theme with CSS variables |
| TanStack Query (React Query) | 5.x | Server state management, built-in polling via `refetchInterval` |
| React Router | 7.x | Client-side routing for SPA |

**No component library (shadcn/ui, MUI, etc.).** The dashboard has 3 pages with simple tables and cards. Tailwind utility classes are sufficient. Adding a component library for 3 pages adds bundle size for no benefit.

### Page Structure

```
/                   -> Today's Predictions (home page)
/results            -> Historical Results
/about              -> About the model (static content)
```

### Page Data Requirements

**Page: Today's Predictions (`/`)**

| Data Source | Endpoint | Polling | Notes |
|-------------|----------|---------|-------|
| Today's games + predictions | `GET /api/v1/predictions/today` | Every 60 seconds (initial fetch, then refetch) | Main content |
| Latest update timestamp | `GET /api/v1/predictions/latest-timestamp` | Every 30 seconds | Lightweight check for change notification |

**Display per game:**
- Home team vs. Away team
- Starting pitchers (with "TBD" if unconfirmed)
- Pre-lineup predictions: LR / RF / XGB probabilities
- Post-lineup predictions: LR / RF / XGB probabilities (or "Pending" if 10am run hasn't happened yet)
- Kalshi price
- Edge signals (color-coded: green = positive edge, red = negative, gray = no Kalshi price)
- Prediction version timestamp

**Page: Historical Results (`/results`)**

| Data Source | Endpoint | Polling | Notes |
|-------------|----------|---------|-------|
| Past results with outcomes | `GET /api/v1/results?page=1&per_page=20` | None (static data) | Paginated table |
| Accuracy statistics | `GET /api/v1/results/accuracy` | None | Aggregate Brier scores |

**Display:**
- Table: date, teams, model predictions, actual outcome, Kalshi price, edge, P&L
- Summary cards: aggregate Brier score per model, win rate, total simulated P&L

**Page: About (`/about`)**
- Static content. No API calls. Describes methodology, model details, data sources.

### Client-Side Timestamp Polling for Change Notifications

The dashboard needs to detect when new predictions are available (10am pre-lineup run, 1pm post-lineup run) without WebSocket or push notifications.

**Pattern:**

```typescript
// In the main layout component:
const { data: timestamp } = useQuery({
    queryKey: ['latest-timestamp'],
    queryFn: () => fetch('/api/v1/predictions/latest-timestamp').then(r => r.json()),
    refetchInterval: 30_000,  // Poll every 30 seconds
});

const [lastSeen, setLastSeen] = useState<string | null>(null);
const [showBanner, setShowBanner] = useState(false);

useEffect(() => {
    if (!timestamp?.timestamp) return;
    if (lastSeen && timestamp.timestamp !== lastSeen) {
        setShowBanner(true);  // Show "New predictions available" banner
        // Optional: trigger browser Notification API
        if (Notification.permission === 'granted') {
            new Notification('MLB Forecaster', {
                body: 'New predictions available',
                icon: '/favicon.ico',
            });
        }
    }
    setLastSeen(timestamp.timestamp);
}, [timestamp]);
```

**Why this works:** The `/api/v1/predictions/latest-timestamp` endpoint returns a single ISO timestamp string (~50 bytes). Polling every 30 seconds costs negligible bandwidth. When the timestamp changes (pipeline wrote new predictions), the frontend shows a banner and optionally fires a browser notification.

**Browser Notification API setup:** On first visit, the frontend requests `Notification.requestPermission()`. Users who grant permission get desktop notifications when predictions update. No service worker, no push subscription, no server-side notification infrastructure.

### Dark/Amber Aesthetic

Tailwind CSS with custom CSS variables for the color palette:

```css
:root {
    --bg-primary: #0f0f0f;
    --bg-secondary: #1a1a1a;
    --bg-card: #242424;
    --text-primary: #e5e5e5;
    --text-secondary: #a3a3a3;
    --accent: #f59e0b;         /* amber-500 */
    --accent-light: #fbbf24;   /* amber-400 */
    --accent-dark: #d97706;    /* amber-600 */
    --positive: #22c55e;       /* green for positive edge */
    --negative: #ef4444;       /* red for negative edge */
    --neutral: #6b7280;        /* gray for no data */
}
```

### Frontend Build and Deployment

The React app is built at Docker image build time:

```dockerfile
# frontend/Dockerfile (multi-stage)
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Output: /app/dist/ (static files served by FastAPI StaticFiles mount)
FROM scratch AS export
COPY --from=build /app/dist /dist
```

The API Dockerfile copies the frontend build output into `/app/frontend/dist/` where FastAPI's `StaticFiles` mount serves it. This means the frontend does not need its own container at runtime -- it is baked into the API image.

**Revised Docker Compose (final):** Remove the `frontend` service. The `api` service includes and serves the frontend build. Three services total: `db`, `api`, `worker`.

---

## 7. Complete v2.0 System Architecture

```
                         INTERNET
                            |
                    [ Certbot SSL ]
                            |
                +-----------v-----------+
                |   Host Nginx (1.24)   |
                |   mlbforecaster.      |
                |   silverreyes.net     |
                |   :443 -> :8082       |
                +-----------+-----------+
                            |
                    port 8082 (localhost)
                            |
          +-----------------v-----------------+
          |     Docker Compose Network        |
          |                                   |
          |   +----------+    +-----------+   |
          |   |   api    |    |  worker   |   |
          |   | FastAPI  |    | supercronic|  |
          |   | uvicorn  |    | 10am/1pm  |   |
          |   | :8000    |    | pipeline  |   |
          |   | + React  |    |           |   |
          |   | static   |    |           |   |
          |   +----+-----+    +-----+-----+   |
          |        |                |          |
          |        |  model_artifacts vol      |
          |        |    (shared r/w)           |
          |        |                |          |
          |   +----v-----+    +----v------+   |
          |   | Postgres |<---| data_cache|   |
          |   |  :5432   |    | volume    |   |
          |   | pgdata   |    |           |   |
          |   +----------+    +-----------+   |
          +-----------------------------------+
```

### Component Inventory

**Modified existing components (Track 1):**

| Component | File | Change |
|-----------|------|--------|
| FeatureBuilder | `src/features/feature_builder.py` | Extend `_add_sp_features()` with ERA, BB%, WHIP, IP differentials |
| FeatureBuilder | `src/features/feature_builder.py` | Fix `_add_advanced_features()` xwOBA column bug (ADVF-07) |
| Feature sets | `src/models/feature_sets.py` | Add `SP_ENHANCED_FEATURE_COLS`, alias `TEAM_ONLY_FEATURE_COLS` |
| Model training | `src/models/train.py` | No changes (factories are feature-set agnostic) |
| Calibration | `src/models/calibrate.py` | No changes |
| Backtest | `src/models/backtest.py` | Add new folds for expanded feature set validation |

**New components (Track 2):**

| Component | Location | Purpose |
|-----------|----------|---------|
| FastAPI app | `api/` | HTTP server, model serving, Postgres queries |
| Pipeline runner | `pipeline/` | Twice-daily cron logic (fetch, predict, store) |
| Model persistence | `scripts/train_and_persist.py` | One-time script: train all 6 model variants, save as joblib |
| Docker Compose | `docker-compose.yml` | Service orchestration |
| Dockerfile | `Dockerfile` | Multi-stage build (Python + frontend assets) |
| Frontend | `frontend/` | React + Vite + Tailwind SPA |
| Nginx vhost | Deploy config | Host reverse proxy for SSL termination |
| DB schema | `db/init.sql` | Postgres schema (games, predictions, pipeline_runs) |
| Alembic migrations | `alembic/` | Schema versioning for production |

---

## 8. Build Order (Dependency Graph)

The build order is critical because Track 2 depends on Track 1 outputs (trained models, expanded FeatureBuilder). Within Track 2, database must exist before the API, and trained model artifacts must exist before the pipeline.

### Phase Ordering

```
Phase 1: SP Feature Integration (Track 1)
    |
    |- 1a. Extend _add_sp_features() with new differentials
    |- 1b. Fix ADVF-07 (xwOBA column bug)
    |- 1c. Update feature_sets.py (TEAM_ONLY + SP_ENHANCED)
    |- 1d. Rebuild feature store (FeatureBuilder.build())
    |- 1e. Retrain all 6 model combinations with walk-forward backtest
    |- 1f. Evaluate: compare v1 vs v2 Brier scores
    |
Phase 2: Model Persistence
    |
    |- 2a. Create train_and_persist.py (train final models, save joblib artifacts)
    |- 2b. Generate 6 joblib files + model_metadata.json
    |       (Depends on: Phase 1 complete -- feature sets finalized)
    |
Phase 3: Database & API Foundation
    |
    |- 3a. Write db/init.sql (schema from Section 2)
    |- 3b. Set up Alembic
    |- 3c. Build FastAPI app structure (routers, schemas, database.py)
    |- 3d. Implement /health endpoint (verifies DB connection + models loaded)
    |- 3e. Implement /predictions/today and /predictions/{date} endpoints
    |- 3f. Implement /predictions/latest-timestamp endpoint
    |- 3g. Implement /results endpoints
    |       (Depends on: Phase 2 -- API loads model artifacts at startup)
    |
Phase 4: Pipeline Worker
    |
    |- 4a. Create pipeline/run.py (fetch schedule, build features, predict, store)
    |- 4b. Integrate FeatureBuilder with live schedule fetch (not cached)
    |- 4c. Add Kalshi live price fetch for edge computation
    |- 4d. Create crontab file for supercronic
    |- 4e. Test pipeline end-to-end locally (writes to local Postgres)
    |       (Depends on: Phase 3 -- needs database schema and ORM models)
    |
Phase 5: Docker & Deployment
    |
    |- 5a. Write Dockerfile (multi-stage: frontend build + Python app)
    |- 5b. Write docker-compose.yml
    |- 5c. Test locally with docker compose up
    |- 5d. Set up VPS: DNS record for mlbforecaster.silverreyes.net
    |- 5e. Deploy to VPS: docker compose up -d
    |- 5f. Configure host Nginx vhost + Certbot SSL
    |- 5g. Verify end-to-end: HTTPS -> API -> predictions
    |       (Depends on: Phase 4 -- needs working pipeline + API)
    |
Phase 6: React Frontend
    |
    |- 6a. Scaffold Vite + React + TypeScript + Tailwind project
    |- 6b. Implement dark/amber theme CSS variables
    |- 6c. Build Today's Predictions page (main dashboard)
    |- 6d. Build Historical Results page
    |- 6e. Implement timestamp polling + browser notifications
    |- 6f. Build About page
    |- 6g. Integrate into Dockerfile (multi-stage build)
    |       (Can start in parallel with Phase 3 -- just needs API contract/types)
    |
Phase 7: Portfolio Integration
    |
    |- 7a. Create mlb-winforecaster page in Astro SSR site
    |- 7b. Add project card to silverreyes.net portfolio
    |       (Depends on: Phase 5 -- needs live URL to link to)
```

### Parallelization Opportunities

- **Phase 6 (frontend) can start during Phase 3** as long as API types/schemas are defined first. Use mock data during frontend dev.
- **Phase 1a and 1b** are independent fixes within FeatureBuilder -- can be done in parallel.
- **Phase 3a-3b (DB schema)** and **Phase 6a-6b (frontend scaffold)** are independent of each other.

### What Must Exist Before What

| Dependency | Reason |
|-----------|--------|
| SP features (1) before model persistence (2) | Models must train on final feature set |
| Model artifacts (2) before API (3) | API loads models at startup via lifespan |
| DB schema (3a) before API endpoints (3c-3g) | Endpoints query Postgres |
| DB schema (3a) before pipeline (4) | Pipeline writes to Postgres |
| API + pipeline (3+4) before Docker deploy (5) | Docker wraps working services |
| Docker deploy (5) before SSL/Nginx (5f) | SSL cert needs the server running |
| Live URL (5g) before portfolio (7) | Portfolio page links to dashboard |

---

## Scalability Considerations

| Concern | Current (v2.0) | If 10K daily users | If 100K daily users |
|---------|----------------|---------------------|---------------------|
| API throughput | 2 uvicorn workers, ~200 req/s | Sufficient | Add workers or second VPS |
| Database | Single Postgres, ~5K rows/season | Sufficient for decades | Sufficient for decades |
| Model inference | In-memory, <10ms per prediction | Sufficient | Sufficient (batch, not per-request) |
| Static assets | Served by FastAPI StaticFiles | Add CDN (Cloudflare) | Add CDN |
| Cron pipeline | 2 runs/day, ~30s each | Sufficient | Sufficient |

**This system is dramatically over-provisioned for its workload.** 15 games/day, 2 prediction runs, ~5K annual rows. The VPS with 2 CPU / 8 GB RAM could handle 100x the load. No scaling concerns for the foreseeable future.

---

## Sources

- [FastAPI Lifespan Events (official docs)](https://fastapi.tiangolo.com/advanced/events/)
- [FastAPI in Docker Containers (official docs)](https://fastapi.tiangolo.com/deployment/docker/)
- [Loading Models into FastAPI Applications](https://apxml.com/courses/fastapi-ml-deployment/chapter-3-integrating-ml-models/loading-models-fastapi)
- [FastAPI + PostgreSQL + Celery Stack with Docker Compose](https://oneuptime.com/blog/post/2026-02-08-how-to-set-up-a-fastapi-postgresql-celery-stack-with-docker-compose/view)
- [Production-Ready FastAPI Project Structure (2026)](https://dev.to/thesius_code_7a136ae718b7/production-ready-fastapi-project-structure-2026-guide-b1g)
- [APScheduler vs Celery comparison](https://leapcell.io/blog/scheduling-tasks-in-python-apscheduler-vs-celery-beat)
- [Docker Compose Cron Jobs with Supercronic](https://distr.sh/blog/docker-compose-cron-jobs/)
- [How to Run Cron Jobs Inside Docker Containers](https://oneuptime.com/blog/post/2026-01-06-docker-cron-jobs/view)
