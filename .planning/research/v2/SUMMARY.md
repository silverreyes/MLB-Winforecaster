# Research Summary: v2.0 — SP Features + Live Dashboard

**Domain:** MLB pre-game win probability model deployment with starting pitcher feature expansion
**Researched:** 2026-03-29
**Overall confidence:** MEDIUM (pybaseball FanGraphs reliability is the primary uncertainty)

---

## Executive Summary

The v2.0 milestone adds two parallel tracks to the validated v1 pipeline: (1) starting pitcher feature integration into the existing three-model ensemble, and (2) a live prediction dashboard with twice-daily automated pipeline.

The most significant research finding is that **pybaseball is effectively dead**. The last PyPI release was September 2023, the maintainer is unresponsive, and FanGraphs scraping is intermittently broken due to Cloudflare protection (403 errors). However, pybaseball's Statcast/Baseball Savant functions remain fully reliable because they hit MLB's official CSV endpoints directly -- no scraping involved. The recommended strategy is a two-source approach: use pybaseball's FanGraphs `pitching_stats()` (from master branch, not PyPI) for the initial 10-season historical pull with aggressive caching, and use the MLB Stats API + Baseball Savant for all ongoing/live data needs.

The deployment stack is straightforward and well-proven. FastAPI + uvicorn + Postgres + APScheduler follows the exact pattern already running on the VPS with GamePredictor. React + Vite for the frontend is the standard choice for a single-page dashboard. All library versions have been verified as current stable releases with no pandas 2.2.x compatibility issues.

The critical architectural constraint carries forward from v1: the `src/` package must be the single source of truth for all feature engineering, shared between the Jupyter backtest pipeline and the live FastAPI/scheduler pipeline. Feature drift between backtest and production is the #1 failure mode in deployed ML systems.

---

## Key Findings

**Stack:** pybaseball master (FanGraphs) + Baseball Savant CSV (Statcast) + MLB Stats API (game logs, splits) for SP data. FastAPI 0.135.2 + React 19.2.4 + Postgres 17.5 + APScheduler 3.11.2 for deployment.

**Architecture:** Docker Compose with 4 services (api, scheduler, db, nginx) on port 8082. Host nginx proxies from SSL. Shared `src/` package between backtest and live. Two-version prediction storage (pre-lineup + post-lineup).

**Critical pitfall:** pybaseball FanGraphs intermittent 403s. Mitigated by one-season-at-a-time fetching with Parquet caching. Once historical data is cached, never re-fetched. Compute-FIP-from-raw-stats fallback available if FanGraphs is permanently blocked.

---

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: SP Data Acquisition & Feature Engineering (Track 1)
**Rationale:** Must come first because the model retrain depends on having SP features, and the live pipeline depends on retrained models.

- Addresses: SP-01 (historical SP stats), SP-02 (feature matrix integration), ADVF-07 (xwOBA fix)
- Avoids: Pitfall #2 (FanGraphs 403) by implementing retry + cache strategy upfront
- Avoids: Pitfall #3 (temporal leakage) by using prior-season stats for early games
- Avoids: Pitfall #4 (name matching) by building robust normalization early

**Key risk:** FanGraphs data acquisition may take multiple attempts over days if Cloudflare is actively blocking. Budget time for this. Once cached, it's a one-time cost.

### Phase 2: Model Retrain & Validation (Track 1)
**Rationale:** With SP features available, retrain all three models and validate that SP features improve Brier scores.

- Addresses: SP-03 (model retrain with SP features)
- Avoids: Pitfall #1 (feature drift) by keeping all feature logic in `src/`
- Avoids: Pitfall #10 (model artifact sync) by versioning model files with metadata

**Important validation gate:** If SP features do NOT improve model performance (Brier score), the v2 models should still ship (with SP features included) but the finding should be documented. Do not cherry-pick feature subsets based on backtest performance -- that's overfitting.

### Phase 3: Infrastructure & Pipeline (Track 2)
**Rationale:** Docker Compose, database schema, and daily pipeline must be working before the dashboard.

- Addresses: INFRA-01 (Docker Compose), PIPE-01/02/03 (daily pipeline)
- Avoids: Pitfall #5 (timezone) by setting TZ explicitly in Docker
- Avoids: Pitfall #6 (connection pool) by proper pool sizing
- Avoids: Pitfall #9 (secrets) by .env + .gitignore from the start

### Phase 4: Dashboard & Polish (Track 2)
**Rationale:** Frontend is the last piece -- it consumes the API built in Phase 3.

- Addresses: DASH-01/02/03/04 (dashboard features), INFRA-02 (host nginx config)
- Avoids: Pitfall #7 (cache) by configuring no-cache for index.html
- Avoids: Pitfall #11 (notification permissions) by user-initiated permission flow

### Phase 5: Portfolio Integration
**Rationale:** Portfolio page at silverreyes.net/mlb-winforecaster is cosmetic and depends on the live dashboard being deployed.

- Addresses: PORT-01

**Phase ordering rationale:**
- Track 1 (Phases 1-2) and Track 2 (Phases 3-4) can overlap. SP data acquisition (Phase 1) is the longest-lead-time item due to FanGraphs reliability. Infrastructure setup (Phase 3) can proceed in parallel.
- Phase 2 (model retrain) blocks Phase 3 (pipeline) because the pipeline needs trained model artifacts.
- Phase 4 (dashboard) blocks Phase 5 (portfolio) because the portfolio page links to the live dashboard.

**Research flags for phases:**
- Phase 1: NEEDS deeper research during implementation -- pybaseball FanGraphs reliability cannot be fully validated until actually attempting the 10-season pull. Have fallback plan (compute FIP manually) ready.
- Phase 2: Standard patterns, unlikely to need research. Walk-forward retrain is well-understood from v1.
- Phase 3: LOW research risk. Docker Compose + FastAPI + Postgres is a well-trodden path with GamePredictor as a working template.
- Phase 4: LOW research risk. React SPA with polling is straightforward. Browser Notification API is simple.
- Phase 5: MINIMAL research. Astro SSR integration is outside the ML domain.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| SP Data (FanGraphs) | LOW-MEDIUM | pybaseball FanGraphs functions are intermittently broken. Cache-once strategy mitigates but does not eliminate risk. Fallback available. |
| SP Data (Statcast) | HIGH | Baseball Savant CSV endpoint confirmed working. pybaseball wrapper is reliable for this source. |
| SP Data (MLB Stats API) | HIGH | Already proven in v1 for game logs and player resolution. |
| Backend Stack | HIGH | All versions verified on PyPI (March 2026). FastAPI + SQLAlchemy + asyncpg is the canonical async Python web stack. |
| Frontend Stack | HIGH | React 19 + Vite 8 is the standard greenfield React setup in 2026. |
| Docker/Deployment | HIGH | Follows proven GamePredictor template. All image tags verified on Docker Hub. |
| Architecture | HIGH | Patterns follow v1 constraints (shared src/, temporal safety). Standard SPA + API + DB pattern. |
| Pitfalls | MEDIUM | Known pitfalls are well-documented. Unknown unknowns around FanGraphs long-term availability. |

---

## Gaps to Address

1. **FanGraphs long-term viability:** If FanGraphs permanently blocks scraping, we need the manual FIP/xFIP computation path. This should be designed as a clean fallback in the FeatureBuilder, not a last-minute hack.

2. **Kalshi API authentication for live pipeline:** v1 uses RSA-PSS authentication with `kalshi-python`. The live pipeline needs API credentials stored securely. Need to verify the API key works from the VPS (IP restrictions, rate limits).

3. **Model artifact deployment strategy:** How do retrained `.joblib` files get from the development machine into the Docker container? Options: bake into image, volume mount, or artifact registry. Volume mount is simplest for a personal project.

4. **React component library choice:** The "dark cinematic + amber aesthetic" is specified but no UI library is chosen. Options: Tailwind CSS (recommended -- utility-first, easy dark mode), shadcn/ui, or plain CSS. Needs decision during Phase 4 planning.

5. **Monitoring and alerting:** If the daily pipeline fails silently, predictions go stale. Need at minimum: pipeline_runs table with status tracking + a dashboard indicator showing "last pipeline run: X hours ago" with a warning if stale.

---

## Files Created

| File | Purpose |
|------|---------|
| `.planning/research/v2/SUMMARY.md` | This file -- executive summary with roadmap implications |
| `.planning/research/v2/STACK.md` | Technology recommendations with pinned versions |
| `.planning/research/v2/FEATURES.md` | Feature landscape (SP stats, dashboard features, anti-features) |
| `.planning/research/v2/ARCHITECTURE.md` | System architecture, deployment topology, patterns |
| `.planning/research/v2/PITFALLS.md` | 13 pitfalls with prevention strategies |

---

## Sources (Key References)

- [pybaseball GitHub Issues #495](https://github.com/jldbc/pybaseball/issues/495) -- Project maintenance status
- [pybaseball GitHub Issues #479](https://github.com/jldbc/pybaseball/issues/479) -- FanGraphs 403 errors
- [Baseball Savant Expected Stats](https://baseballsavant.mlb.com/leaderboard/expected_statistics?type=pitcher) -- Confirmed accessible CSV endpoint
- [FastAPI PyPI](https://pypi.org/project/fastapi/) -- v0.135.2
- [SQLAlchemy Async Docs](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) -- asyncpg integration
- [APScheduler PyPI](https://pypi.org/project/APScheduler/) -- v3.11.2 stable
- [React Versions](https://react.dev/versions) -- v19.2.4
- [Vite Releases](https://vite.dev/releases) -- v8.0.3
- [FanGraphs FIP Formula](https://library.fangraphs.com/pitching/fip/) -- Manual computation fallback
- [MLB Stats API Docs](https://appac.github.io/mlb-data-api-docs/) -- Pitcher stat fields
