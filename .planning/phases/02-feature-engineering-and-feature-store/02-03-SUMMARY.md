---
phase: 02-feature-engineering-and-feature-store
plan: 03
subsystem: features
tags: [notebooks, jupyter, parquet, feature-matrix, leakage-detection, seaborn, matplotlib, statsapi, mlb-stats-api]

# Dependency graph
requires:
  - phase: 01-data-ingestion-and-raw-cache
    provides: Cached Parquet files for schedule, SP stats, team batting, Statcast, Kalshi
  - phase: 02-01
    provides: formulas.py (Log5, Pythagorean, park factors), game_logs.py (per-game team batting loader)
  - phase: 02-02
    provides: FeatureBuilder class with build() method, sp_recent_form.py with 30-day ERA caching
provides:
  - Notebook 06: Per-game team batting log ingestion for 30 teams x 10 seasons
  - Notebook 07: Feature matrix build via FeatureBuilder, saved to data/features/feature_matrix.parquet
  - Notebook 08: Feature exploration with coverage heatmaps, correlation/leakage analysis, temporal safety checks
  - data/features/feature_matrix.parquet consumed by Phase 3
affects: [03-model-training, 04-kalshi-comparison]

# Tech tracking
tech-stack:
  added: [statsapi (MLB Stats API), seaborn, matplotlib]
  patterns: [notebook-ingestion-pattern (title/imports/config/ingest/summary/validation), standalone-parquet-exploration]

key-files:
  created:
    - notebooks/06_team_game_logs.ipynb
    - notebooks/07_feature_matrix.ipynb
    - notebooks/08_feature_exploration.ipynb
  modified:
    - src/features/game_logs.py
    - src/features/feature_builder.py

key-decisions:
  - "Replaced pybaseball BRef scraper with MLB Stats API (statsapi) for team game logs due to Cloudflare 403 blocking"
  - "OPS column resolution in _add_rolling_features() uses lowercase 'ops' with fallback to uppercase and obp+slg computation"

patterns-established:
  - "Notebook triplet pattern: ingestion (06) -> build (07) -> explore (08) with Parquet as handoff artifact"
  - "Exploration notebook reads saved Parquet (standalone), does not re-run FeatureBuilder"

requirements-completed: [FEAT-03, FEAT-06, FEAT-07, FEAT-08]

# Metrics
duration: 34min
completed: 2026-03-29
---

# Phase 2 Plan 03: Notebooks and Feature Matrix Summary

**Three Jupyter notebooks (ingestion, build, exploration) producing feature_matrix.parquet with coverage heatmaps, 0.7-threshold leakage detection, and temporal safety verification -- BRef scraper replaced with MLB Stats API after Cloudflare 403 block**

## Performance

- **Duration:** 34 min (including checkpoint wait for BRef fix diagnosis)
- **Started:** 2026-03-28T21:56:00Z
- **Completed:** 2026-03-29T04:30:00Z
- **Tasks:** 3 (2 auto + 1 human-verify checkpoint)
- **Files modified:** 5

## Accomplishments
- Created notebook 06 for per-game batting log ingestion across 30 teams x 10 seasons with rate-limited caching
- Created notebook 07 for building the feature matrix via FeatureBuilder and saving to data/features/feature_matrix.parquet
- Created notebook 08 for standalone feature exploration: coverage heatmaps, correlation analysis with 0.7 leakage threshold, temporal spot-check
- Resolved Baseball Reference Cloudflare 403 blocking by replacing pybaseball with MLB Stats API (statsapi)
- All 84 tests pass after the data source migration

## Task Commits

Each task was committed atomically:

1. **Task 1: Per-game batting log notebook (06) and feature matrix build notebook (07)** - `352cf1f` (feat)
2. **Task 2: Feature exploration notebook (08) with leakage detection** - `ee52f91` (feat)
3. **Task 3: Verify feature matrix and exploration notebook outputs** - Checkpoint approved by user after BRef fix

**BRef fix (deviation):** `e63deec` (fix) - replaced pybaseball BRef scraper with MLB Stats API

## Files Created/Modified
- `notebooks/06_team_game_logs.ipynb` - Per-game team batting log ingestion with rate-limited caching for 300 team-seasons
- `notebooks/07_feature_matrix.ipynb` - Feature matrix build via FeatureBuilder, saves to data/features/feature_matrix.parquet
- `notebooks/08_feature_exploration.ipynb` - Standalone exploration: coverage heatmap, correlation/leakage analysis, temporal spot-check, feature distributions
- `src/features/game_logs.py` - Replaced pybaseball.team_game_logs() with statsapi.get() using CANONICAL_TO_STATSAPI_ID mapping for all 30 teams
- `src/features/feature_builder.py` - Updated _add_rolling_features() OPS resolution with lowercase fallback for new statsapi schema

## Decisions Made
- Replaced pybaseball BRef scraper with MLB Stats API (statsapi) for team game logs after Baseball Reference deployed Cloudflare JS-challenge blocking (HTTP 403). The official MLB Stats API returns identical per-game batting data in one call per team-season.
- OPS column resolution updated to check lowercase "ops" first (new statsapi schema), with fallback to uppercase "OPS" and obp+slg computation for backward compatibility.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Baseball Reference Cloudflare 403 blocking**
- **Found during:** Task 3 checkpoint (user ran notebooks and discovered BRef scraping failure)
- **Issue:** Baseball Reference deployed Cloudflare JS-challenge protection, causing all pybaseball.team_game_logs() calls to return HTTP 403. Notebook 06 could not fetch any game logs.
- **Fix:** Replaced pybaseball BRef scraper with MLB Stats API (statsapi.get('team_stats', {'stats': 'gameLog'})). Added CANONICAL_TO_STATSAPI_ID mapping for all 30 teams. Updated _add_rolling_features() OPS column resolution for new lowercase schema.
- **Files modified:** src/features/game_logs.py, src/features/feature_builder.py, notebooks/06_team_game_logs.ipynb
- **Verification:** fetch_team_game_log(2024, 'NYY') returns 162 games; fetch_team_game_log(2015, 'OAK') returns 162 games; fetch_team_game_log(2020, 'CHW') returns 60 games; all 84 tests pass
- **Committed in:** e63deec

---

**Total deviations:** 1 auto-fixed (1 blocking -- Rule 3)
**Impact on plan:** Essential fix for data source availability. No scope creep. MLB Stats API provides identical data with better reliability.

## Issues Encountered
- Baseball Reference Cloudflare blocking was the primary issue. Diagnosed during checkpoint verification when user ran notebook 06. Root cause: BRef deployed JS-challenge protection making all programmatic requests fail with 403. Resolution: migrated to MLB Stats API which is the official, stable data source.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 2 is complete: feature_matrix.parquet contains one row per game with all differential features, outcome label, Kalshi implied probability, and sp_recent_era_diff (30-day pitching_stats_range ERA)
- All temporal safety verified: shift(1) working, early-season NaN confirmed, no leakage detected (no feature with |corr| > 0.7)
- Phase 3 can read data/features/feature_matrix.parquet directly for model training
- Blocker carried forward: Kalshi last_price_dollars is settlement price, not pre-game opening price (Phase 4 concern)

## Self-Check: PASSED

- All 5 files exist on disk (3 notebooks, game_logs.py, feature_builder.py)
- All 3 task commits found in git log (352cf1f, ee52f91, e63deec)
- 84 tests pass in full suite

---
*Phase: 02-feature-engineering-and-feature-store*
*Completed: 2026-03-29*
