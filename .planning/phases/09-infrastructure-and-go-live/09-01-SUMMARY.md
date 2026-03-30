---
phase: 09-infrastructure-and-go-live
plan: 01
subsystem: infra
tags: [docker, docker-compose, postgres, gunicorn, multi-stage-build, backup, memory-audit]

# Dependency graph
requires:
  - phase: 08-api-and-dashboard
    provides: FastAPI app (api/main.py), SPA frontend (frontend/dist), pipeline scripts
provides:
  - Multi-stage Dockerfile for containerized deployment
  - Docker Compose stack with 3 memory-limited services (api, worker, db)
  - .dockerignore for clean build contexts
  - VPS memory audit gate script
  - Postgres backup script with 7-day retention
affects: [09-02-nginx-portfolio, 09-03-deployment]

# Tech tracking
tech-stack:
  added: [docker, docker-compose, gunicorn, postgres:16-bookworm, node:20-slim]
  patterns: [multi-stage-dockerfile, mem_limit-not-deploy-resources, bind-mount-ro-artifacts, named-volumes]

key-files:
  created:
    - Dockerfile
    - docker-compose.yml
    - .dockerignore
    - scripts/memory_audit.sh
    - scripts/backup_postgres.sh
  modified: []

key-decisions:
  - "mem_limit (not deploy.resources.limits.memory) for non-swarm Docker Compose compatibility"
  - "Model artifacts bind-mounted read-only at runtime, not copied into image"
  - "API exposed on port 8082 (host) mapped to 8000 (container)"
  - "Worker gets 1024MB limit (double api/db) for ML inference memory needs"

patterns-established:
  - "Multi-stage build: frontend-build -> python-deps -> runtime (3 FROM stages)"
  - "Named volume mlb_pgdata for Postgres data persistence across container restarts"
  - "Service healthcheck with depends_on condition for startup ordering"

requirements-completed: [INFRA-01, INFRA-04]

# Metrics
duration: 2min
completed: 2026-03-30
---

# Phase 9 Plan 1: Docker and Deployment Artifacts Summary

**Multi-stage Dockerfile with frontend+Python build, Docker Compose stack (api/worker/db) with explicit memory limits, and VPS operations scripts (memory audit gate, pg_dump backup with 7-day retention)**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-30T06:22:49Z
- **Completed:** 2026-03-30T06:25:45Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Multi-stage Dockerfile producing slim runtime image with built frontend SPA and Python packages
- Docker Compose defining 3 services with explicit memory limits (db 512MB, api 512MB, worker 1024MB)
- Pre-deploy memory audit script that gates deployment on >= 1GB headroom after projected stack usage
- Postgres backup script with gzip compression and automatic 7-day retention cleanup

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Dockerfile and docker-compose.yml with memory limits** - `4abdc2e` (feat)
2. **Task 2: Create memory audit and Postgres backup scripts** - `7159ee8` (feat)

## Files Created/Modified
- `Dockerfile` - Multi-stage build: node:20-slim frontend, python:3.11-slim-bookworm deps and runtime
- `docker-compose.yml` - 3-service stack (db, api, worker) with mem_limit, healthcheck, named volume
- `.dockerignore` - Excludes .venv, data, notebooks, .git, models/artifacts, frontend/node_modules
- `scripts/memory_audit.sh` - VPS pre-deploy gate: checks RAM headroom, exits 1 if < 1GB remaining
- `scripts/backup_postgres.sh` - Daily pg_dump from Docker container, gzip, 7-day retention cleanup

## Decisions Made
- Used `mem_limit` instead of `deploy.resources.limits.memory` because `deploy` is ignored by `docker compose up` in non-swarm mode
- Model artifacts are bind-mounted read-only (`:ro`) rather than baked into the image, since they are in .gitignore and must be present on the VPS filesystem
- API exposed on host port 8082 to avoid conflicts with other services on the VPS
- Worker service gets 1024MB (double the api/db limit) to accommodate ML model inference memory requirements
- Container name `mlb-winforecaster-db-1` used in backup script follows Docker Compose default naming convention

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Dockerfile and Compose config ready for Nginx reverse proxy configuration (09-02)
- Memory audit script ready to run on target VPS before first deployment
- Backup script ready for cron scheduling on VPS
- All artifacts validated: `docker compose config` passes, both shell scripts pass `bash -n` syntax check

## Self-Check: PASSED

All 5 created files exist on disk. Both task commits (4abdc2e, 7159ee8) verified in git log.

---
*Phase: 09-infrastructure-and-go-live*
*Completed: 2026-03-30*
