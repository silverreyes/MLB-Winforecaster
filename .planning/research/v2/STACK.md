# Technology Stack — v2.0 (SP Features + Live Dashboard)

**Project:** MLB Win Probability Model
**Researched:** 2026-03-29
**Scope:** NEW dependencies only. v1 stack (pybaseball, pandas 2.2.x, scikit-learn, XGBoost, statsapi, etc.) is validated and not re-researched here.

---

## Track 1: SP Data Acquisition

### The pybaseball Reliability Problem

pybaseball 2.2.7 (last PyPI release: September 2023) is **effectively unmaintained**. The maintainer is unresponsive, 40+ PRs are languishing, and multiple contributors have publicly stated the project is dead (GitHub issue [#495](https://github.com/jldbc/pybaseball/issues/495), March 2026).

**Endpoint-by-endpoint reliability assessment:**

| Function | Data Source | Status | Confidence |
|----------|------------|--------|------------|
| `pitching_stats(season, qual=0)` | FanGraphs `/leaders-legacy.aspx` | **INTERMITTENT** -- Cloudflare 403s ([#479](https://github.com/jldbc/pybaseball/issues/479)); multi-year >10 seasons returns 500 ([#492](https://github.com/jldbc/pybaseball/issues/492)); monthly queries cap at 30 rows ([#469](https://github.com/jldbc/pybaseball/issues/469)). Master branch has partial fix but no PyPI release. | LOW |
| `statcast_pitcher_expected_stats(season)` | Baseball Savant CSV endpoint | **RELIABLE** -- Hits `baseballsavant.mlb.com/leaderboard/expected_statistics?type=pitcher&csv=true` directly. No Cloudflare, no scraping. Returns xwOBA, xBA, xSLG, xERA. | HIGH |
| `statcast_batter_expected_stats(season)` | Baseball Savant CSV endpoint | **RELIABLE** -- Same direct CSV pattern as pitcher variant. | HIGH |
| `team_batting(season)` | FanGraphs `/leaders-legacy.aspx` | **INTERMITTENT** -- Same Cloudflare 403 issue as `pitching_stats`. | LOW |
| `pitching_stats_range(start, end)` | Baseball Reference | **BROKEN** -- BRef behind Cloudflare JS-challenge, returns 403. Already replaced in v1 with MLB Stats API game logs. | BROKEN |

**Key insight:** pybaseball's Statcast/Baseball Savant functions are reliable because they hit official MLB CSV endpoints directly. pybaseball's FanGraphs functions are unreliable because they scrape HTML behind Cloudflare. pybaseball's Baseball Reference functions are broken.

### Recommended SP Data Strategy

**Use a two-source approach:**

#### Source 1: pybaseball `pitching_stats()` for FanGraphs advanced stats (FIP, xFIP, SIERA, K%, BB%, WHIP)

Despite intermittent 403s, this function DOES work when FanGraphs is not actively blocking. The v1 codebase already caches results to Parquet, so each season only needs to be fetched ONCE. Strategy:

1. Install from master branch: `pip install git+https://github.com/jldbc/pybaseball.git@master` (contains FanGraphs URL fixes not in 2.2.7)
2. Fetch each season 2015-2024 individually (NOT as a single 10-year span -- [#492](https://github.com/jldbc/pybaseball/issues/492) confirms multi-year queries fail)
3. Cache to Parquet immediately on success (already implemented in `src/data/sp_stats.py`)
4. If a season fetch fails due to 403, retry with exponential backoff (1 retry per minute, 3 attempts max)
5. Once cached, never re-fetch -- the historical data is immutable

**Why not abandon FanGraphs entirely?** FIP, xFIP, and SIERA are FanGraphs-computed metrics that require league-level constants (FIP constant, HR/FB%). Computing them from raw stats requires fly ball data that the MLB Stats API does not provide. FanGraphs is the only source that provides these pre-computed for every pitcher-season.

**Fallback if FanGraphs is permanently blocked:** Compute FIP manually from MLB Stats API data:
- `FIP = ((13 * HR) + (3 * (BB + HBP)) - (2 * K)) / IP + FIP_constant`
- FIP constant derivable from league averages (also available via MLB Stats API)
- xFIP requires fly ball data -- would need Statcast batted ball data as substitute
- This is a viable but more complex path; try pybaseball first

#### Source 2: Baseball Savant CSV (via pybaseball or direct) for Statcast metrics

Already implemented in v1 (`src/data/statcast.py`). The `statcast_pitcher_expected_stats()` function reliably returns xwOBA, xBA, xSLG, xERA per pitcher-season. Continue using this.

#### Source 3: MLB Stats API for game-level pitcher logs

Already implemented in v1 (`src/features/sp_recent_form.py`). Provides per-game ERA, IP, ER for rolling window calculations. The MLB Stats API provides ERA, WHIP, W, L, SO, BB, IP, H, HR, HBP per game via the `person/hydrate=stats(type=gameLog)` endpoint. It does NOT provide FIP, xFIP, K%, or BB% -- those must come from FanGraphs or be computed.

#### Home/Away Splits

The MLB Stats API supports `type=statSplits,group=pitching` with `sitCodes=h,a` for home/away splits. This provides ERA, WHIP, SO, BB, IP broken down by home/away. Use this for split features rather than FanGraphs.

### SP Data: What NOT to Use

| Option | Why Not |
|--------|---------|
| `pybaseballstats` | Uses Polars (not pandas), FanGraphs source "temporarily disabled" per their own docs, tiny community (<50 GitHub stars) |
| `baseball-scraper` | Last updated March 2020, requires Selenium/Chrome for FanGraphs, dead project |
| Retrosheet | Game logs available 2015-2024 but provides only traditional box score stats (no FIP/xFIP/advanced). Useful for validation but not a primary source. |
| `fangraphs` PyPI package | Undocumented, scraping-based, tiny community, no advantage over pybaseball |
| Direct FanGraphs JSON API | Returns 403 (confirmed by direct test of `/api/leaders/major-league/data` endpoint). Same Cloudflare protection as legacy endpoint. |

### SP Data: Pinned Versions

| Library | Version | Install Method | Purpose |
|---------|---------|---------------|---------|
| pybaseball | master (git) | `pip install git+https://github.com/jldbc/pybaseball.git@master` | FanGraphs pitching_stats, Statcast expected stats. Master contains FanGraphs URL fixes not in 2.2.7. Pin to a specific commit hash once confirmed working. |
| MLB-StatsAPI | 1.9.0 | `pip install MLB-StatsAPI==1.9.0` | Pitcher game logs, home/away splits, schedule data. Already in v1 requirements. |
| httpx | 0.28.1 | `pip install httpx==0.28.1` | Direct Baseball Savant CSV downloads as fallback if pybaseball Statcast functions break. Async-capable for parallel season fetches. |

**Confidence:** MEDIUM -- pybaseball FanGraphs functions are intermittently available. The cache-once strategy mitigates this: we only need them to work ONCE per season during initial data acquisition. Statcast functions are HIGH confidence.

---

## Track 2: Live Dashboard Stack

### Backend (Python)

| Technology | Version | Purpose | Why This Version |
|------------|---------|---------|-----------------|
| FastAPI | 0.135.2 | REST API framework | Latest stable (released 2026-03-23). Async-native, Pydantic v2 integration, OpenAPI docs built-in. Already proven in GamePredictor template on VPS. |
| uvicorn | 0.42.0 | ASGI server | Latest stable (released 2026-03-16). Runs FastAPI in production. Use with `--workers 2` behind nginx for the app container. |
| Pydantic | 2.12.5 | Request/response validation, settings | Latest stable v2 release. FastAPI 0.135.x requires Pydantic v2. Do NOT use 2.13.0b2 (beta). |
| SQLAlchemy | 2.0.48 | ORM + async Postgres access | Latest stable (released 2026-03-02). Use async engine with `create_async_engine()`. Do NOT use 2.1.0b1 (beta). |
| asyncpg | 0.31.0 | Async PostgreSQL driver | Latest stable (released 2025-11-24). Required by SQLAlchemy async PostgreSQL dialect (`postgresql+asyncpg://`). |
| Alembic | 1.18.4 | Database migrations | Latest stable (released 2026-02-10). Auto-generates migrations from SQLAlchemy models. Async-compatible. |
| APScheduler | 3.11.2 | Twice-daily pipeline scheduler | Latest stable 3.x (released 2025-12-22). Use `AsyncIOScheduler` with `CronTrigger` for 10am/1pm ET runs. No Redis/broker needed. Do NOT use 4.0.0a6 (alpha). |

**Why APScheduler over Celery:** The pipeline runs twice daily on a fixed schedule. This is a cron pattern, not a distributed task queue. Celery requires Redis or RabbitMQ as a message broker -- unnecessary complexity for a single-node deployment with two scheduled jobs. APScheduler runs in-process with the FastAPI app, uses asyncio natively, and stores job state in memory (persistent job store available via SQLAlchemy if needed, but unnecessary for fixed-interval cron).

**What NOT to add:**

| Technology | Why Not |
|------------|---------|
| Redis | Only needed for Celery or caching. APScheduler doesn't need it. FastAPI response times are fast enough without a cache layer for this traffic level. |
| Celery | Overkill. Two cron jobs do not need a distributed task queue. |
| asyncz | APScheduler 3.x AsyncIOScheduler covers the same ground with far more community support and documentation. |
| Gunicorn | uvicorn with `--workers` is sufficient. Gunicorn's process management adds complexity with no benefit at this scale. |
| SQLModel | Thin wrapper around SQLAlchemy + Pydantic. Adds a dependency for marginal DX improvement. Use SQLAlchemy models + Pydantic schemas directly. |

### Frontend (React)

| Technology | Version | Purpose | Why This Version |
|------------|---------|---------|-----------------|
| React | 19.2.4 | UI framework | Latest stable (released 2026-01-26). New features (Activity API, useEffectEvent) are nice-to-have but not required. Using 19.x because the dashboard is greenfield and there's no migration burden. |
| Vite | 8.0.3 | Build tool / dev server | Latest stable. Instant HMR, fast production builds via Rollup. Standard React toolchain in 2026. |
| TypeScript | 5.8+ | Type safety | Current stable. Use `--template react-ts` with Vite. |

**Why NOT Next.js:** The dashboard is a single-page application that fetches data from the FastAPI backend. There is no SEO requirement, no server-side rendering need, no file-based routing complexity. Plain React + Vite is simpler, faster to build, and the static build output (`dist/`) can be served directly by nginx. Next.js adds a Node.js server runtime, routing opinions, and deployment complexity for zero benefit here.

**Why NOT React 18 LTS:** React 18 LTS is the "safe" choice for existing projects. This is a greenfield dashboard with no legacy code. React 19 is stable, well-tested, and the ecosystem (Vite, major libraries) fully supports it.

### Database

| Technology | Version | Purpose | Why This Version |
|------------|---------|---------|-----------------|
| PostgreSQL | 17.5 | Prediction storage, pipeline state | Latest stable 17.x. GamePredictor already runs Postgres via Docker on the VPS. Use the same major version for consistency. |

**Schema scope (minimal):** Predictions table (game_id, date, home_team, away_team, home_prob, model_type, pipeline_version [pre-lineup/post-lineup], created_at), Kalshi prices table (game_id, open_price, timestamp), Pipeline runs table (run_id, type, status, started_at, completed_at). No need for complex relational modeling -- this is a write-heavy append-only prediction store.

---

## Docker Compose Services

Following the GamePredictor template (FastAPI + uvicorn + worker + Postgres on single Docker Compose stack).

### Service Architecture

```
[Host Nginx :443] --> [App Nginx :8082] --> [FastAPI :8000]
                                       --> [React static files]

[Scheduler] --> [FastAPI internal] --> [Postgres :5432]
```

### Docker Image Tags

| Service | Image | Tag | Purpose |
|---------|-------|-----|---------|
| `api` | `python` | `3.12-slim-bookworm` | FastAPI + uvicorn. Python 3.12 for best pandas 2.2.x / pybaseball compatibility. Slim variant (~150MB vs ~900MB full). Bookworm (Debian 12) for stable base. |
| `scheduler` | `python` | `3.12-slim-bookworm` | APScheduler worker running twice-daily pipeline. Same image as api (shared Dockerfile, different entrypoint). |
| `db` | `postgres` | `17.5-alpine` | PostgreSQL. Alpine variant for small image size (~80MB). Pin to patch version for reproducibility. |
| `nginx` | `nginx` | `1.28-alpine` | App-level reverse proxy. Routes `/api/*` to FastAPI, serves React static build for everything else. Alpine variant (~40MB). |
| `frontend` (build-only) | `node` | `22-alpine` | Multi-stage build: `npm run build` produces static `dist/`, copied into nginx image. Node container does NOT run in production. |

### Docker Compose Structure

```yaml
services:
  db:
    image: postgres:17.5-alpine
    volumes:
      - pgdata:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: mlbforecaster
      POSTGRES_USER: mlb
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mlb"]
      interval: 5s
      retries: 5

  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+asyncpg://mlb:${DB_PASSWORD}@db:5432/mlbforecaster

  scheduler:
    build:
      context: .
      dockerfile: Dockerfile.api  # Same image, different entrypoint
    command: python -m app.scheduler
    depends_on:
      db:
        condition: service_healthy

  nginx:
    build:
      context: .
      dockerfile: Dockerfile.nginx  # Multi-stage: builds React, copies dist/ into nginx
    ports:
      - "8082:80"
    depends_on:
      - api

volumes:
  pgdata:
```

**Port 8082** because GamePredictor already occupies 8080. Host nginx (already running on VPS) proxies `mlbforecaster.silverreyes.net` to `localhost:8082`.

---

## Full v2 Requirements (New Dependencies Only)

### Backend (requirements-api.txt)

```
# Web framework
fastapi==0.135.2
uvicorn[standard]==0.42.0
pydantic==2.12.5
pydantic-settings==2.8.1

# Database
sqlalchemy[asyncio]==2.0.48
asyncpg==0.31.0
alembic==1.18.4

# Scheduler
apscheduler==3.11.2

# HTTP client (for Baseball Savant direct fallback)
httpx==0.28.1

# Existing v1 dependencies (carry forward)
pybaseball @ git+https://github.com/jldbc/pybaseball.git@master
MLB-StatsAPI==1.9.0
pandas>=2.2.3,<2.3
pyarrow>=15.0.0
scikit-learn>=1.3.0,<2.0
xgboost>=2.0.0,<3.0
requests==2.31.0
python-dotenv==1.0.1
```

### Frontend (package.json key deps)

```json
{
  "dependencies": {
    "react": "^19.2.4",
    "react-dom": "^19.2.4"
  },
  "devDependencies": {
    "vite": "^8.0.3",
    "typescript": "^5.8.0",
    "@vitejs/plugin-react-swc": "^4.0.0"
  }
}
```

### pandas 2.2.x Compatibility

All new backend dependencies have been verified compatible with pandas 2.2.x:

| Library | pandas Interaction | Compatible? |
|---------|-------------------|-------------|
| FastAPI | None (Pydantic models, not DataFrames) | Yes |
| SQLAlchemy 2.0.48 | Optional pandas integration; `pd.read_sql()` works with 2.2.x | Yes |
| APScheduler 3.11.2 | None | Yes |
| asyncpg 0.31.0 | None (raw SQL driver) | Yes |
| httpx 0.28.1 | None | Yes |

**No new dependency conflicts with the pandas 2.2.x pin.**

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| SP data source | pybaseball (master) + MLB Stats API | pybaseballstats | Polars-only output, FanGraphs disabled in their own lib, tiny community |
| SP data source | pybaseball (master) + MLB Stats API | Direct FanGraphs JSON API | Returns 403 (confirmed). Same Cloudflare protection. |
| SP data source | pybaseball (master) + MLB Stats API | Retrosheet | No advanced stats (FIP/xFIP). Game logs only. |
| Web framework | FastAPI | Django REST Framework | Overkill ORM, sync-first, slower for this use case |
| Web framework | FastAPI | Flask | No async, no auto-validation, no OpenAPI generation |
| Scheduler | APScheduler | Celery + Redis | Two cron jobs do not need a distributed task queue + broker |
| Scheduler | APScheduler | Linux cron + script | Works but harder to manage in Docker, no health monitoring, no retry logic |
| Database | PostgreSQL | SQLite | No concurrent access from API + scheduler, no async driver |
| Frontend | React + Vite | Next.js | SPA dashboard, no SSR/SEO need, unnecessary runtime complexity |
| Frontend | React + Vite | Svelte/Vue | React is the most common choice; team familiarity matters |
| ORM | SQLAlchemy 2.0 | SQLModel | Thin wrapper adds dependency for marginal benefit |
| ORM | SQLAlchemy 2.0 | Raw asyncpg | Loses migrations, model validation, query builder |

---

## Sources

### Verified (HIGH confidence)
- [pybaseball PyPI](https://pypi.org/project/pybaseball/) -- v2.2.7, Sep 2023 (last release)
- [pybaseball GitHub Issues #479](https://github.com/jldbc/pybaseball/issues/479) -- FanGraphs 403 error (Cloudflare)
- [pybaseball GitHub Issues #492](https://github.com/jldbc/pybaseball/issues/492) -- Multi-year 500 error
- [pybaseball GitHub Issues #495](https://github.com/jldbc/pybaseball/issues/495) -- Project maintenance status (dead)
- [FastAPI PyPI](https://pypi.org/project/fastapi/) -- v0.135.2, Mar 2026
- [uvicorn PyPI](https://pypi.org/project/uvicorn/) -- v0.42.0, Mar 2026
- [SQLAlchemy PyPI](https://pypi.org/project/SQLAlchemy/) -- v2.0.48, Mar 2026
- [asyncpg PyPI](https://pypi.org/project/asyncpg/) -- v0.31.0, Nov 2025
- [Alembic PyPI](https://pypi.org/project/alembic/) -- v1.18.4, Feb 2026
- [APScheduler PyPI](https://pypi.org/project/APScheduler/) -- v3.11.2, Dec 2025
- [Pydantic PyPI](https://pypi.org/project/pydantic/) -- v2.12.5 stable
- [Baseball Savant expected stats endpoint](https://baseballsavant.mlb.com/leaderboard/expected_statistics?type=pitcher) -- Confirmed accessible, returns CSV directly
- [PostgreSQL Docker Hub](https://hub.docker.com/_/postgres) -- 17.5-alpine available
- [nginx Docker Hub](https://hub.docker.com/_/nginx) -- 1.28-alpine / stable-alpine available
- [React versions](https://react.dev/versions) -- 19.2.4 latest stable
- [Vite releases](https://vite.dev/releases) -- 8.0.3 latest stable

### Cross-referenced (MEDIUM confidence)
- [FanGraphs FIP formula](https://library.fangraphs.com/pitching/fip/) -- FIP constant calculation
- [MLB Stats API docs](https://appac.github.io/mlb-data-api-docs/) -- Pitcher stat fields (no FIP/xFIP)
- [APScheduler vs Celery comparison](https://leapcell.io/blog/scheduling-tasks-in-python-apscheduler-vs-celery-beat)
- [FastAPI + SQLAlchemy + asyncpg integration](https://github.com/grillazz/fastapi-sqlalchemy-asyncpg)
