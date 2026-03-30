# Phase 9: Infrastructure and Go-Live - Research

**Researched:** 2026-03-29
**Domain:** Docker Compose deployment, Nginx reverse proxy, SSL, Postgres backups, Astro static portfolio
**Confidence:** HIGH

## Summary

Phase 9 deploys the completed MLB Win Forecaster stack (FastAPI API + React SPA + APScheduler worker + Postgres) to a Hostinger KVM 2 VPS that already hosts Ghost CMS and GamePredictor. The primary challenge is not the deployment itself -- the patterns are well-established -- but the memory-constrained environment (8GB total, ~2.4GB already consumed) and the requirement to coexist with existing services without disruption.

The stack maps cleanly to three Docker Compose services: `api` (FastAPI serving the built React SPA), `worker` (APScheduler pipeline runner), and `db` (Postgres 16). All share a single `docker-compose.yml` with explicit `mem_limit` values. Nginx on the host (not in Docker) proxies HTTPS traffic from `mlbforecaster.silverreyes.net` to port 8082. Certbot issues a single-domain SSL cert using the `--nginx` plugin. A separate Astro static page at `silverreyes.net/mlb-winforecaster` serves the portfolio content with no backend dependency.

**Primary recommendation:** Use Docker Compose with `mem_limit` at the service level (not `deploy.resources` which is swarm-oriented), host-level Nginx (matching existing Ghost/GamePredictor pattern), and Certbot `--nginx` plugin for single-subdomain SSL. The portfolio page should use Astro 5.x (not 6.x which requires Node 22) for maximum compatibility with the VPS environment.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-01 | Docker Compose stack on port 8082 with memory limits (api: 512M, worker: 1G, db: 512M); memory audit before deploy | Docker Compose `mem_limit` syntax verified; three-service architecture; `docker stats --no-stream` for audit |
| INFRA-02 | Nginx server block for mlbforecaster.silverreyes.net proxying to 8082; validated with `nginx -t` | Host-level Nginx reverse proxy pattern; server block template; validation before reload |
| INFRA-03 | Certbot SSL for mlbforecaster.silverreyes.net; renewal dry-run passes | Certbot `--nginx` plugin for single subdomain; `certbot renew --dry-run` verification |
| INFRA-04 | Postgres named volume `mlb_pgdata`; persistence verified by stop/start; daily pg_dump backup cron with 7-day retention | Named volume configuration; pg_dump via `docker exec`; `find -mtime +7 -delete` retention |
| PORT-01 | Static Astro page at silverreyes.net/mlb-winforecaster with methodology, Brier table, calibration curves, dashboard link | Astro 5.x with `base` config for subdirectory; static output mode; no backend calls |
</phase_requirements>

## Standard Stack

### Core

| Component | Version | Purpose | Why Standard |
|-----------|---------|---------|--------------|
| Docker Compose | Latest (Compose Spec, no `version` key) | Multi-service orchestration | Industry standard for single-host multi-container deployments |
| python:3.11-slim-bookworm | 3.11.x | Base image for api + worker | Matches project Python version; slim reduces image size; bookworm is current Debian stable |
| postgres:16-bookworm | 16.x | Database container | Stable LTS PostgreSQL; matches psycopg3 compatibility |
| Nginx | Host-installed (existing) | Reverse proxy + SSL termination | Already running on VPS for Ghost CMS and GamePredictor |
| Certbot | Host-installed (existing) | SSL certificate management | Already configured on VPS; `--nginx` plugin for single subdomain |
| Astro | 5.x (latest 5.x, NOT 6.x) | Portfolio static site generator | PORT-01 specifies Astro; 5.x supports Node 20 which is more broadly available |

### Supporting

| Component | Version | Purpose | When to Use |
|-----------|---------|---------|-------------|
| Gunicorn | Latest | Process manager for uvicorn workers | API container -- manages uvicorn workers with `uvicorn.workers.UvicornWorker` |
| Node.js 20 LTS | 20.x | Build frontend + portfolio Astro page | Build stage only; not needed at runtime for API/worker |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Host Nginx | Nginx in Docker (nginx-proxy) | Adds container complexity; existing VPS already has host Nginx for Ghost |
| Astro 5.x | Astro 6.x | Astro 6 requires Node 22; 5.x is sufficient for a static portfolio page |
| Astro | Plain HTML | Astro provides component structure, `base` path support, and build optimization; plain HTML would work but is less maintainable |
| Gunicorn + Uvicorn | Uvicorn standalone | Gunicorn adds process management and auto-restart; worth it for production reliability in a 512M container |
| postgres:16 | postgres:17 or 18 | No features in 17/18 needed; 16 is battle-tested LTS |

## Architecture Patterns

### Docker Compose Service Layout

```
docker-compose.yml
  services:
    api:        # FastAPI + built React SPA (uvicorn via gunicorn)
      build: .  # Single Dockerfile, multi-stage
      port: 8082:8000
      mem_limit: 512m
      depends_on: db (healthy)
      env: DATABASE_URL, KALSHI_API_KEY
      volumes: models/artifacts/ (read-only bind mount)

    worker:     # APScheduler pipeline runner
      build: .  # Same image, different command
      mem_limit: 1g
      depends_on: db (healthy)
      env: DATABASE_URL, KALSHI_API_KEY
      volumes: models/artifacts/ (read-only bind mount)

    db:         # Postgres 16
      image: postgres:16-bookworm
      mem_limit: 512m
      volumes: mlb_pgdata:/var/lib/postgresql/data
      healthcheck: pg_isready

volumes:
  mlb_pgdata:
```

### Dockerfile (Multi-Stage)

```
Stage 1: frontend-build
  FROM node:20-slim
  COPY frontend/ .
  RUN npm ci && npm run build
  -> produces dist/

Stage 2: python-deps
  FROM python:3.11-slim-bookworm AS deps
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt gunicorn

Stage 3: runtime
  FROM python:3.11-slim-bookworm
  COPY --from=deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
  COPY --from=deps /usr/local/bin /usr/local/bin
  COPY --from=frontend-build /app/dist ./frontend/dist
  COPY src/ ./src/
  COPY api/ ./api/
  COPY scripts/ ./scripts/
  CMD ["gunicorn", "api.main:app", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--workers", "2"]
```

### Recommended Project Structure (New Files)

```
project_root/
+-- docker-compose.yml          # 3-service stack definition
+-- Dockerfile                  # Multi-stage: frontend build + Python runtime
+-- .dockerignore               # Exclude .venv, data/, notebooks/, .git, etc.
+-- nginx/
|   +-- mlbforecaster.conf      # Nginx server block template (reference only)
+-- scripts/
|   +-- backup_postgres.sh      # pg_dump + 7-day retention script
|   +-- deploy.sh               # Deploy checklist script (optional)
+-- portfolio/                  # Astro project for silverreyes.net/mlb-winforecaster
|   +-- astro.config.mjs
|   +-- src/
|   |   +-- pages/
|   |   |   +-- index.astro     # Portfolio page
|   |   +-- components/
|   |       +-- BrierTable.astro
|   |       +-- CalibrationCurves.astro
|   |       +-- MethodologySection.astro
|   +-- public/
|       +-- images/
|           +-- reliability_team_only.png
|           +-- reliability_sp_enhanced.png
```

### Pattern 1: Host-Level Nginx Reverse Proxy

**What:** Nginx runs on the host (not in Docker), with a server block per service. This is the pattern already established on the VPS for Ghost CMS and GamePredictor.

**When to use:** When Nginx is already installed and managing multiple services on the host.

**Example:**

```nginx
# /etc/nginx/sites-available/mlbforecaster.silverreyes.net
server {
    listen 80;
    server_name mlbforecaster.silverreyes.net;

    location / {
        proxy_pass http://127.0.0.1:8082;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
# Certbot will auto-modify this to add SSL directives
```

### Pattern 2: Docker Compose Memory Limits (Non-Swarm)

**What:** Use `mem_limit` at the service level in the Compose Specification. Do NOT use `deploy.resources.limits` which is designed for Docker Swarm and is ignored by `docker compose up`.

**When to use:** Always, for non-swarm single-host deployments.

**Example:**

```yaml
services:
  api:
    build: .
    mem_limit: 512m
    ports:
      - "8082:8000"
```

Source: [Docker Compose Services Reference](https://docs.docker.com/reference/compose-file/services/)

### Pattern 3: Postgres Named Volume with Healthcheck

**What:** Named Docker volume for Postgres data persistence. Healthcheck ensures dependent services wait for DB readiness.

**When to use:** Always with Dockerized Postgres.

**Example:**

```yaml
services:
  db:
    image: postgres:16-bookworm
    mem_limit: 512m
    environment:
      POSTGRES_DB: mlb_forecaster
      POSTGRES_USER: mlb
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    volumes:
      - mlb_pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "mlb", "-d", "mlb_forecaster"]
      interval: 5s
      timeout: 5s
      retries: 5
      start_period: 10s

volumes:
  mlb_pgdata:
```

### Anti-Patterns to Avoid

- **Putting Nginx inside Docker Compose:** The VPS already has host-level Nginx. Running a second Nginx in Docker creates port conflicts and SSL complexity. Use the existing host Nginx.
- **Using `deploy.resources.limits` without swarm:** This is silently ignored by `docker compose up`. Use `mem_limit` instead.
- **Bind-mounting Postgres data to a host directory:** Named volumes are managed by Docker and are more portable and less error-prone than bind mounts for database data.
- **Building frontend at runtime:** The React SPA should be built in the Docker image build stage, not when the container starts. The built `dist/` is served as static files by FastAPI's `SPAStaticFiles`.
- **Running API and worker in the same container:** They have different lifecycle requirements. The API serves HTTP; the worker runs scheduled cron jobs. Separate containers allow independent restarts and memory allocation.
- **Hardcoding DATABASE_URL in code:** The existing `db.py` already reads from `DATABASE_URL` env var with a localhost default. The Docker Compose environment section overrides this.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSL certificate management | Manual openssl cert generation | Certbot with `--nginx` plugin | Auto-renewal, trusted CA, zero-downtime renewal |
| Process management for FastAPI | Custom supervisor/init script | Gunicorn with uvicorn workers | Battle-tested process management, auto-restart on crash |
| Postgres backup rotation | Custom Python backup script | Shell script with `find -mtime +7 -delete` | Standard Unix pattern; simple, reliable, auditable |
| Container startup ordering | Sleep-based wait scripts | Docker Compose `depends_on` with `condition: service_healthy` | Native Compose feature; healthcheck-based, no polling |
| Port 80/443 management | iptables rules | Nginx server blocks + Certbot | Already established pattern on the VPS |
| Static site framework | Raw HTML with manual asset management | Astro (per PORT-01 requirement) | Component structure, build optimization, `base` path for subdirectory |

**Key insight:** This phase is almost entirely configuration and deployment -- there is very little custom code to write. The biggest risk is misconfiguration, not missing features. Every component (Docker, Nginx, Certbot, pg_dump) is a standard tool with well-documented patterns.

## Common Pitfalls

### Pitfall 1: Memory Limits Ignored in Docker Compose
**What goes wrong:** Using `deploy.resources.limits.memory` in a non-swarm environment causes limits to be silently ignored. Containers consume unlimited memory and crash the VPS.
**Why it happens:** Docker Compose v3 `deploy` section is only honored by `docker stack deploy` (swarm mode), not by `docker compose up`.
**How to avoid:** Use `mem_limit: 512m` at the service level. Verify with `docker stats --no-stream` after startup.
**Warning signs:** `docker stats` shows memory usage approaching or exceeding 8GB total on the VPS.

### Pitfall 2: DATABASE_URL Format Mismatch
**What goes wrong:** The existing `db.py` uses `DATABASE_URL` with default `postgresql://localhost:5432/mlb_forecaster`. In Docker Compose, the database host is the service name `db`, not `localhost`.
**Why it happens:** Containers run in an isolated network. `localhost` inside the `api` container refers to the api container itself, not the db container.
**How to avoid:** Set `DATABASE_URL=postgresql://mlb:password@db:5432/mlb_forecaster` in the Docker Compose environment for both `api` and `worker` services.
**Warning signs:** Connection refused errors on startup; health endpoint returns "unhealthy".

### Pitfall 3: Model Artifacts Not Available in Container
**What goes wrong:** The `inference.py` module uses `ARTIFACT_DIR = Path("models/artifacts")` with a relative path. Inside the Docker container, this path may not exist or may be empty.
**Why it happens:** Model artifacts (`.joblib` files) are in `.gitignore` and are not copied into the Docker image at build time.
**How to avoid:** Bind-mount the `models/artifacts/` directory as a read-only volume in `docker-compose.yml`. This keeps artifacts out of the image (they're ~12MB total and change infrequently) while making them available at runtime.
**Warning signs:** `FileNotFoundError: Missing model artifact` on container startup (API refuses to start per API-06).

### Pitfall 4: Frontend Build Path Mismatch
**What goes wrong:** `api/main.py` checks `Path("frontend/dist").is_dir()` and mounts the SPA. In the Docker container, the working directory must match this path expectation.
**Why it happens:** The Dockerfile may set a different `WORKDIR` or copy files to a different location than expected.
**How to avoid:** Set `WORKDIR /app` in the Dockerfile and ensure the multi-stage build copies `frontend/dist` to `/app/frontend/dist`. Verify `frontend/dist/index.html` exists in the built image.
**Warning signs:** API starts but serves 404 on `/` (no SPA mount).

### Pitfall 5: Certbot Port 80 Conflict During Issuance
**What goes wrong:** Certbot with `--nginx` plugin needs to modify the existing Nginx config and perform HTTP-01 validation on port 80. If port 80 is not open or another service is blocking, certificate issuance fails.
**Why it happens:** The VPS firewall may block port 80 or the DNS A record for the subdomain may not be configured.
**How to avoid:** Before running Certbot: (1) verify DNS A record for `mlbforecaster.silverreyes.net` points to VPS IP, (2) verify port 80 is open, (3) add the Nginx server block FIRST (HTTP-only), (4) test with `curl http://mlbforecaster.silverreyes.net`, (5) then run Certbot.
**Warning signs:** Certbot reports "Connection refused" or "DNS problem: NXDOMAIN".

### Pitfall 6: Timezone Issues in Worker Container
**What goes wrong:** The APScheduler uses `ZoneInfo("US/Eastern")` for cron triggers. The Docker container may not have timezone data installed.
**Why it happens:** `python:3.11-slim` does not include the `tzdata` package by default in all configurations.
**How to avoid:** Ensure `tzdata` is installed in the Dockerfile: `RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*`. Or set `TZ=America/New_York` environment variable.
**Warning signs:** Scheduler runs at wrong times or throws `ZoneInfoNotFoundError`.

### Pitfall 7: Astro Base Path Configuration
**What goes wrong:** The portfolio page at `silverreyes.net/mlb-winforecaster` needs Astro's `base` option set so all asset URLs are prefixed correctly. Without it, images and CSS load from the wrong path.
**Why it happens:** Astro defaults to serving from `/`, but the portfolio page lives at a subdirectory path.
**How to avoid:** Set `base: '/mlb-winforecaster'` in `astro.config.mjs`. Use `import.meta.env.BASE_URL` for any dynamic asset references.
**Warning signs:** CSS/images return 404 when browsing the portfolio page.

### Pitfall 8: pg_dump Cron Failure Silently
**What goes wrong:** The daily backup cron job fails (wrong container name, Postgres not running, disk full) but nobody notices because cron errors go to /dev/null.
**Why it happens:** Default cron jobs don't have error notification configured.
**How to avoid:** Redirect cron output to a log file. The backup script should log success/failure. Consider a simple check: if the latest backup file doesn't exist or is 0 bytes, something is wrong.
**Warning signs:** `/opt/backups/mlb/` is empty or has stale files.

## Code Examples

### Docker Compose Configuration

```yaml
# docker-compose.yml
# No 'version' key needed (Compose Specification)
services:
  db:
    image: postgres:16-bookworm
    mem_limit: 512m
    environment:
      POSTGRES_DB: mlb_forecaster
      POSTGRES_USER: mlb
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - mlb_pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "mlb", "-d", "mlb_forecaster"]
      interval: 5s
      timeout: 5s
      retries: 5
      start_period: 10s
    restart: unless-stopped

  api:
    build: .
    mem_limit: 512m
    ports:
      - "8082:8000"
    environment:
      DATABASE_URL: postgresql://mlb:${POSTGRES_PASSWORD}@db:5432/mlb_forecaster
      KALSHI_API_KEY: ${KALSHI_API_KEY:-}
    volumes:
      - ./models/artifacts:/app/models/artifacts:ro
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

  worker:
    build: .
    command: ["python", "scripts/run_pipeline.py"]
    mem_limit: 1024m
    environment:
      DATABASE_URL: postgresql://mlb:${POSTGRES_PASSWORD}@db:5432/mlb_forecaster
      KALSHI_API_KEY: ${KALSHI_API_KEY:-}
    volumes:
      - ./models/artifacts:/app/models/artifacts:ro
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

volumes:
  mlb_pgdata:
```

### Multi-Stage Dockerfile

```dockerfile
# Stage 1: Build frontend
FROM node:20-slim AS frontend-build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: Install Python dependencies
FROM python:3.11-slim-bookworm AS python-deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Stage 3: Runtime
FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python packages from deps stage
COPY --from=python-deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=python-deps /usr/local/bin /usr/local/bin

# Copy built frontend
COPY --from=frontend-build /app/dist ./frontend/dist

# Copy application code
COPY src/ ./src/
COPY api/ ./api/
COPY scripts/ ./scripts/
COPY pyproject.toml .

# Default: run API server
CMD ["gunicorn", "api.main:app", "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
```

### Nginx Server Block

```nginx
# /etc/nginx/sites-available/mlbforecaster.silverreyes.net
server {
    listen 80;
    server_name mlbforecaster.silverreyes.net;

    location / {
        proxy_pass http://127.0.0.1:8082;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }
}
# After certbot --nginx: SSL directives are auto-added
```

### Backup Script

```bash
#!/bin/bash
# /opt/scripts/backup_mlb_postgres.sh
# Called by cron: 0 3 * * * /opt/scripts/backup_mlb_postgres.sh >> /var/log/mlb_backup.log 2>&1

BACKUP_DIR="/opt/backups/mlb"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/mlb_forecaster_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

# pg_dump from the running Postgres container
docker exec mlb-winforecaster-db-1 pg_dump -U mlb mlb_forecaster | gzip > "$BACKUP_FILE"

if [ $? -eq 0 ] && [ -s "$BACKUP_FILE" ]; then
    echo "$(date): Backup successful: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"
else
    echo "$(date): ERROR: Backup failed or empty"
    exit 1
fi

# Remove backups older than 7 days
find "$BACKUP_DIR" -name "mlb_forecaster_*.sql.gz" -mtime +7 -delete
echo "$(date): Retention cleanup complete"
```

### Astro Portfolio Configuration

```javascript
// portfolio/astro.config.mjs
import { defineConfig } from 'astro/config';

export default defineConfig({
  base: '/mlb-winforecaster',
  output: 'static',
  build: {
    assets: '_assets',
  },
});
```

### Memory Audit Script (Pre-Deploy Gate)

```bash
#!/bin/bash
# Run on VPS BEFORE deploying MLB stack
# This is the INFRA-01 hard gate

echo "=== VPS Memory Audit ==="
echo "Total RAM:"
free -h | head -2

echo ""
echo "Current Docker container memory usage:"
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}"

echo ""
echo "Projected MLB stack additions:"
echo "  api:    512MB"
echo "  worker: 1024MB"
echo "  db:     512MB"
echo "  Total:  2048MB (2GB)"

echo ""
USED_MB=$(free -m | awk '/Mem:/ {print $3}')
TOTAL_MB=$(free -m | awk '/Mem:/ {print $2}')
AVAILABLE_MB=$((TOTAL_MB - USED_MB))
NEEDED_MB=2048
REMAINING_MB=$((AVAILABLE_MB - NEEDED_MB))

echo "Currently used:    ${USED_MB}MB"
echo "Available:         ${AVAILABLE_MB}MB"
echo "MLB stack needs:   ${NEEDED_MB}MB"
echo "Remaining after:   ${REMAINING_MB}MB"

if [ "$REMAINING_MB" -lt 1000 ]; then
    echo ""
    echo "WARNING: Less than 1GB headroom remaining after deploy."
    echo "DEPLOY GATE: FAIL - Insufficient memory headroom."
    exit 1
else
    echo ""
    echo "DEPLOY GATE: PASS - Sufficient memory headroom."
fi
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Docker Compose `version: '3.8'` | No `version` key (Compose Specification) | 2023+ | Compose ignores version field; omit it |
| `mem_limit` in v2 / `deploy` in v3 | Both `mem_limit` and `deploy.resources` supported at service level | Compose Spec merge | Use `mem_limit` for simplicity in non-swarm |
| Certbot standalone (stop nginx) | Certbot `--nginx` plugin (zero-downtime) | Mature since 2020+ | No need to stop Nginx during cert issuance |
| Manual Gunicorn config | `gunicorn -k uvicorn.workers.UvicornWorker` | FastAPI best practice 2024+ | Single command, Gunicorn manages worker lifecycle |
| Astro 5.x | Astro 6.x (Node 22 required) | March 2026 | Astro 5.x is the safe choice until Node 22 is standard on VPS |

**Deprecated/outdated:**
- Docker Compose `version` key: No longer needed; Compose Specification merges v2/v3
- `tiangolo/uvicorn-gunicorn-fastapi` Docker image: Deprecated by author; build your own Dockerfile
- Certbot `--standalone` for existing Nginx setups: Use `--nginx` plugin instead

## Open Questions

1. **Existing Nginx configuration pattern on VPS**
   - What we know: Ghost CMS and GamePredictor are already served via Nginx on the VPS
   - What's unclear: The exact directory structure (`/etc/nginx/sites-available/` vs `/etc/nginx/conf.d/`), whether `sites-enabled` symlinks are used, and how existing Certbot certs are structured
   - Recommendation: During deployment, inspect `ls /etc/nginx/sites-available/` or `ls /etc/nginx/conf.d/` and follow the existing pattern. The Nginx config template in this research is compatible with either approach.

2. **Python version on VPS**
   - What we know: The project uses Python 3.11 locally (based on `__pycache__` files showing `cpython-311`)
   - What's unclear: Whether Node.js 20+ is installed on the VPS for building the Astro portfolio
   - Recommendation: The Docker image handles Python; the portfolio Astro build can be done locally or in CI, then the `dist/` output copied to the VPS. No need for Node.js on the VPS at runtime.

3. **Exact memory consumption of existing services**
   - What we know: Ghost CMS + GamePredictor + OS baseline estimated at ~2.4GB
   - What's unclear: Whether this estimate is current; GamePredictor may have grown
   - Recommendation: The memory audit script (INFRA-01 hard gate) runs `docker stats --no-stream` and `free -h` on the VPS before any deployment to get actual numbers. If headroom is less than 1GB after MLB stack, deployment is blocked.

4. **DNS A record for mlbforecaster.silverreyes.net**
   - What we know: The subdomain needs to point to the VPS IP
   - What's unclear: Whether it's already configured or needs to be created in the Hostinger DNS panel
   - Recommendation: This is a pre-deployment prerequisite. Add DNS A record first, wait for propagation (check with `dig mlbforecaster.silverreyes.net`), then proceed with Nginx + Certbot.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.1.1 |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-01 | Docker Compose builds and starts with memory limits | smoke | `docker compose build && docker compose config` (validates compose syntax) | N/A -- infrastructure validation, not unit test |
| INFRA-01 | Memory audit confirms headroom | manual-only | `bash scripts/memory_audit.sh` on VPS | Wave 0: `scripts/memory_audit.sh` |
| INFRA-02 | Nginx config validates | smoke | `sudo nginx -t` on VPS | N/A -- VPS-only command |
| INFRA-03 | SSL cert issued and renewal works | smoke | `certbot renew --dry-run` on VPS | N/A -- VPS-only command |
| INFRA-04 | Postgres volume persistence | smoke | `docker compose down && docker compose up -d && docker exec ... psql -c "SELECT count(*) FROM predictions"` | N/A -- integration test on VPS |
| INFRA-04 | Backup script runs and produces file | smoke | `bash scripts/backup_mlb_postgres.sh && ls -la /opt/backups/mlb/` | Wave 0: `scripts/backup_mlb_postgres.sh` |
| PORT-01 | Astro portfolio builds without error | unit | `cd portfolio && npm run build` | Wave 0: `portfolio/` directory |

### Sampling Rate
- **Per task commit:** `docker compose config` (validates compose YAML syntax)
- **Per wave merge:** `docker compose build` (verifies images build successfully)
- **Phase gate:** Full VPS deployment checklist (memory audit, SSL dry-run, volume persistence, backup test)

### Wave 0 Gaps
- [ ] `Dockerfile` -- multi-stage build for api/worker
- [ ] `docker-compose.yml` -- three-service stack definition
- [ ] `.dockerignore` -- exclude .venv, data/, notebooks/, .git
- [ ] `scripts/memory_audit.sh` -- pre-deploy memory gate script
- [ ] `scripts/backup_mlb_postgres.sh` -- pg_dump + retention script
- [ ] `nginx/mlbforecaster.conf` -- server block reference template
- [ ] `portfolio/` -- Astro project directory with astro.config.mjs

**Note:** This phase is primarily infrastructure configuration. Most "tests" are smoke tests run on the VPS during deployment, not automated unit tests. The validation is procedural: build images, audit memory, deploy, verify SSL, verify persistence, verify backups, verify portfolio page.

## Sources

### Primary (HIGH confidence)
- [Docker Compose Services Reference](https://docs.docker.com/reference/compose-file/services/) -- `mem_limit` syntax, service-level configuration
- [Docker Compose Deploy Specification](https://docs.docker.com/reference/compose-file/deploy/) -- `deploy.resources` (swarm-only clarification)
- [FastAPI Docker Deployment](https://fastapi.tiangolo.com/deployment/docker/) -- Official FastAPI containerization guide
- [FastAPI Server Workers](https://fastapi.tiangolo.com/deployment/server-workers/) -- Gunicorn + Uvicorn worker configuration
- [Certbot User Guide](https://eff-certbot.readthedocs.io/en/stable/using.html) -- `--nginx` plugin, renewal
- [Docker Compose Startup Order](https://docs.docker.com/compose/how-tos/startup-order/) -- `depends_on` with `condition: service_healthy`
- [PostgreSQL Docker Official Image](https://hub.docker.com/_/postgres) -- Named volume, environment variables

### Secondary (MEDIUM confidence)
- [Astro Configuration Reference](https://docs.astro.build/en/reference/configuration-reference/) -- `base` path for subdirectory deployment
- [DigitalOcean: Certbot Nginx Subdomains](https://dev.to/knowbee/how-to-setup-secure-subdomains-using-nginx-and-certbot-on-a-vps-4m8h) -- Subdomain SSL pattern
- [Docker Postgres Backup Strategies](https://dev.to/piteradyson/postgresql-docker-backup-strategies-how-to-backup-postgresql-running-in-docker-containers-1bla) -- pg_dump + retention pattern
- [Slimmer FastAPI Docker Images](https://davidmuraya.com/blog/slimmer-fastapi-docker-images-multistage-builds/) -- Multi-stage Python build pattern

### Tertiary (LOW confidence)
- Astro 6 Node 22 requirement: Based on search results and blog post; verify before choosing Astro version

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Docker Compose, Nginx, Certbot, Postgres are mature tools with stable APIs; patterns verified against official documentation
- Architecture: HIGH - Three-service Docker Compose with host Nginx is a well-established pattern; codebase analysis confirms compatibility
- Pitfalls: HIGH - All pitfalls are based on known issues from codebase analysis (DATABASE_URL default, model artifact paths, mem_limit syntax) and verified deployment patterns
- Portfolio (Astro): MEDIUM - Astro 5.x `base` path configuration verified via docs; exact integration with existing Ghost/Nginx on VPS needs runtime verification

**Research date:** 2026-03-29
**Valid until:** 2026-04-28 (30 days -- stable technology domain)
