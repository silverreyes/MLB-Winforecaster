# Architecture Patterns — v2.0 (SP Features + Live Dashboard)

**Domain:** MLB pre-game win probability model with live prediction dashboard
**Researched:** 2026-03-29
**Scope:** v2 deployment architecture only. v1 notebook pipeline architecture is documented in `.planning/research/ARCHITECTURE.md`.

---

## System Architecture Overview

```
                         INTERNET
                            |
                     [Hostinger KVM 2]
                            |
                   [Host Nginx :443]
                   (SSL termination)
                     /            \
    silverreyes.net/*         mlbforecaster.silverreyes.net
    [Astro SSR :3000]              |
                            [App Nginx :8082]
                           /              \
                    /api/* routes      /* static files
                         |              (React dist/)
                   [FastAPI :8000]
                   (uvicorn, 2 workers)
                         |
                   [PostgreSQL :5432]
                         |
                   [Scheduler]
                   (APScheduler, same image)
```

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| Host Nginx | SSL termination, virtual host routing, Certbot cert renewal | App Nginx (proxy_pass to :8082) |
| App Nginx (Docker) | Route `/api/*` to FastAPI, serve React static build for all other paths | FastAPI container (:8000), static files (volume mount) |
| FastAPI API | REST endpoints: `/api/predictions/today`, `/api/predictions/{date}`, `/api/health`, `/api/pipeline/status` | PostgreSQL (via SQLAlchemy async), Kalshi API (read-only) |
| Scheduler | Twice-daily pipeline: fetch schedule, run models, store predictions | PostgreSQL (via SQLAlchemy async), MLB Stats API, Kalshi API, shared `src/` model code |
| PostgreSQL | Prediction storage, pipeline run tracking | Accessed by API and Scheduler |
| React Frontend | SPA dashboard: display today's games, probabilities, edge signals | FastAPI API (fetch JSON) |

### Data Flow: Daily Pipeline

```
10:00 AM ET (pre-lineup):
  Scheduler triggers
  -> statsapi.schedule(sportId=1, date=today)
  -> For each game: load team features from feature store
  -> Run LR, RF, XGBoost predict (team-only features)
  -> Fetch Kalshi opening prices for today's games
  -> Store predictions in Postgres (version="pre-lineup")
  -> Update pipeline_runs table (status="complete")

1:00 PM ET (post-lineup):
  Scheduler triggers
  -> statsapi.schedule(sportId=1, date=today)  [re-fetch for confirmed SPs]
  -> For each game with confirmed SP:
     -> Load team features + SP features from feature store
     -> Run LR, RF, XGBoost predict (full feature set)
  -> For games without confirmed SP:
     -> Keep pre-lineup prediction, set uncertainty_flag=true
  -> Fetch updated Kalshi prices
  -> Store predictions in Postgres (version="post-lineup")
  -> Compute edge signals (model_prob vs kalshi_price)
  -> Update pipeline_runs table

React dashboard polls:
  -> GET /api/predictions/today
  -> Compare last-modified timestamp
  -> If changed, update display + trigger browser notification
```

---

## Patterns to Follow

### Pattern 1: Shared `src/` Between Backtest and Live Pipeline

**What:** All feature engineering, model loading, and prediction logic lives in `src/` and is imported by both the Jupyter notebook pipeline (v1 backtest) and the FastAPI/scheduler pipeline (v2 live).

**Why:** This is the #1 architectural constraint from v1 (documented in `project_constraints.md`). Divergence between backtest and live feature engineering is the most common cause of "great backtest, terrible live results."

**Implementation:**
```python
# In scheduler pipeline (v2):
from src.features.feature_builder import FeatureBuilder
from src.models.trainer import load_model, predict

# Same imports as in notebook 08_model_training.ipynb
builder = FeatureBuilder(seasons=[2024])
features = builder.build_game_features(game_date, home_team, away_team, ...)
prediction = predict(model, features)
```

**Key constraint:** The `src/` package must be installable inside the Docker container. Use `pip install -e .` or copy `src/` into the image and set `PYTHONPATH`.

### Pattern 2: Two-Version Prediction Storage

**What:** Store both pre-lineup and post-lineup predictions for each game, never overwrite.

**Why:** The pre-lineup prediction is the team-only baseline. The post-lineup prediction shows the SP impact. Displaying both side-by-side is a key differentiator (DASH-02).

**Schema:**
```sql
CREATE TABLE predictions (
    id SERIAL PRIMARY KEY,
    game_id INTEGER NOT NULL,        -- MLB game PK
    game_date DATE NOT NULL,
    home_team VARCHAR(3) NOT NULL,
    away_team VARCHAR(3) NOT NULL,
    home_sp_name VARCHAR(100),       -- NULL for pre-lineup
    away_sp_name VARCHAR(100),       -- NULL for pre-lineup
    pipeline_version VARCHAR(20) NOT NULL,  -- 'pre-lineup' or 'post-lineup'
    model_type VARCHAR(10) NOT NULL, -- 'lr', 'rf', 'xgb'
    home_win_prob FLOAT NOT NULL,
    kalshi_home_price FLOAT,         -- NULL if no Kalshi market
    edge_signal VARCHAR(10),         -- 'BUY_YES', 'BUY_NO', 'NO_EDGE', NULL
    uncertainty_flag BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(game_id, pipeline_version, model_type)
);

CREATE INDEX idx_predictions_date ON predictions(game_date);
CREATE INDEX idx_predictions_game ON predictions(game_id);
```

### Pattern 3: Client-Side Polling for Updates

**What:** React dashboard polls `/api/predictions/today` on a fixed interval (e.g., every 60 seconds). If the response includes a newer `last_updated` timestamp than the client has seen, show a browser notification.

**Why:** DASH-04 specifies "client-side timestamp polling, no push/email." This avoids WebSocket complexity, server-sent events, or push notification infrastructure.

**Implementation:**
```typescript
// React polling hook
const [lastSeen, setLastSeen] = useState<string | null>(null);

useEffect(() => {
  const interval = setInterval(async () => {
    const res = await fetch('/api/predictions/today');
    const data = await res.json();
    if (lastSeen && data.last_updated > lastSeen) {
      new Notification('MLB Forecaster', {
        body: 'Post-lineup predictions are ready!'
      });
    }
    setLastSeen(data.last_updated);
  }, 60_000);
  return () => clearInterval(interval);
}, [lastSeen]);
```

### Pattern 4: Graceful SP Uncertainty Handling

**What:** When a probable starter is not confirmed (or is scratched after lineup announcement), the pipeline stores the prediction with `uncertainty_flag=true` and falls back to team-only features.

**Why:** PIPE-03 requires this. Starting pitchers are sometimes scratched after announcement. The dashboard must never show stale/wrong SP data without a visual indicator.

**Implementation:**
```python
if sp_confirmed:
    features = builder.build_full_features(game, sp_home, sp_away)
    uncertainty = False
else:
    features = builder.build_team_only_features(game)
    uncertainty = True

prediction = predict(model, features)
store_prediction(game_id, prediction, uncertainty_flag=uncertainty)
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Separate Feature Code for Live vs Backtest

**What:** Writing new feature engineering code in the FastAPI app that duplicates or diverges from `src/features/`.
**Why bad:** Feature drift between backtest and live prediction invalidates all model performance metrics. This is the #1 failure mode in production ML systems.
**Instead:** Import directly from `src/`. If a feature needs modification, change it in `src/` and verify it still passes backtest.

### Anti-Pattern 2: Storing Predictions Without Pipeline Version

**What:** Overwriting the pre-lineup prediction when the post-lineup prediction arrives.
**Why bad:** Loses the ability to show prediction delta (how much the SP changed the prediction), which is a key differentiator.
**Instead:** Use `UNIQUE(game_id, pipeline_version, model_type)` constraint. Both versions coexist.

### Anti-Pattern 3: Running Model Training in the Daily Pipeline

**What:** Re-training models every day as part of the pipeline.
**Why bad:** Walk-forward training on 10 years of data takes minutes to hours. The daily pipeline must complete in seconds.
**Instead:** Train models offline (notebook or one-time script). Daily pipeline loads pre-trained model artifacts (`.joblib` files) and calls `predict()` only.

### Anti-Pattern 4: Complex State Management in React

**What:** Using Redux, Zustand, or other state management libraries for the dashboard.
**Why bad:** The dashboard displays a single day's predictions. There are ~15 games per day. This is a simple read-only display with one API fetch.
**Instead:** Use React's built-in `useState` + `useEffect` + `fetch()`. No state management library needed.

### Anti-Pattern 5: Putting Secrets in Docker Compose YAML

**What:** Hardcoding database passwords, Kalshi API keys, etc. in `docker-compose.yml`.
**Why bad:** Secrets end up in version control.
**Instead:** Use `.env` file (excluded from git) referenced via `env_file:` or Docker secrets for sensitive values.

---

## Scalability Considerations

| Concern | Current (1 user) | At 100 users | At 1000 users |
|---------|-------------------|--------------|---------------|
| API response time | <50ms (single Postgres query) | <50ms (same) | Add connection pooling, consider read replica |
| Database size | ~5000 rows/season (15 games x 3 models x 2 versions x ~180 days) | Same data, more reads | Same -- prediction data is tiny |
| Pipeline execution | 30-60 seconds per run | Same (pipeline is independent of users) | Same |
| Static frontend | Served by nginx, <1MB | Same | Add CDN if needed |
| Concurrent connections | uvicorn 2 workers, ~50 concurrent easily | Sufficient | Increase workers to 4, add connection pooling |

**Bottom line:** This is a personal tool. Scalability is not a concern. The architecture supports hundreds of concurrent users without changes, which is far beyond the actual use case.

---

## Deployment Topology

### Host Nginx Configuration (already on VPS)

```nginx
server {
    listen 443 ssl;
    server_name mlbforecaster.silverreyes.net;

    ssl_certificate /etc/letsencrypt/live/mlbforecaster.silverreyes.net/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mlbforecaster.silverreyes.net/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8082;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### App Nginx Configuration (inside Docker)

```nginx
server {
    listen 80;

    location /api/ {
        proxy_pass http://api:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;  # SPA fallback
    }
}
```

---

## Sources

- [FastAPI + SQLAlchemy + asyncpg integration pattern](https://github.com/grillazz/fastapi-sqlalchemy-asyncpg)
- [SQLAlchemy 2.0 async documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [APScheduler AsyncIOScheduler](https://apscheduler.readthedocs.io/en/3.x/modules/schedulers/asyncio.html)
- [project_constraints.md](C:/Users/silve/.claude/projects/E--ClaudeCodeProjects-MLB-WinForecaster/memory/project_constraints.md) -- FeatureBuilder shared requirement
- PROJECT.md requirements: PIPE-01/02/03, DASH-01/02/03/04, INFRA-01/02
