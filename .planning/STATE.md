---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Live Platform
status: in-progress
stopped_at: Completed 09-01 (Docker and deployment artifacts)
last_updated: "2026-03-30T06:26:00Z"
last_activity: 2026-03-30 -- Completed 09-01 (Dockerfile, Docker Compose, memory audit, backup scripts)
progress:
  total_phases: 5
  completed_phases: 4
  total_plans: 16
  completed_plans: 14
  percent: 88
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-29 -- v2.0 milestone started)

**Core value:** Produce well-calibrated win probability estimates that can be rigorously compared against Kalshi market prices, surfacing where models agree, disagree, and where edges may exist.
**Current focus:** Phase 9 in progress -- Infrastructure and Go-Live (1 of 3 plans done).

## Current Position

Phase: 9 of 9 (Infrastructure and Go-Live)
Plan: 2 of 3 in current phase (09-01 complete, 09-02 next)
Status: Executing Phase 9
Last activity: 2026-03-30 -- Completed 09-01 (Dockerfile, Docker Compose, memory audit, backup scripts)

Progress: [█████████░] 88%

## Performance Metrics

**Velocity (v1.0):**
- Total plans completed: 10
- Average duration: 14min
- Total execution time: 2.3 hours

**By Phase (v2.0):**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 5 (SP Feature Integration) | 4/4 | 32min | 8min |

**Recent Trend (v1.0):**
- Last 5 plans: 34min, 5min, 10min, 5min, 5min
- Trend: Stable

*Updated after each plan completion*
| Phase 05 P04 | 12min | 2 tasks | 4 files |
| Phase 06 P01 | 6min | 2 tasks | 6 files |
| Phase 06 P02 | 9min | 2 tasks | 14 files |
| Phase 06 P03 | 12min | 2 tasks | 6 files |
| Phase 07 P01 | 4min | 2 tasks | 7 files |
| Phase 07 P02 | 4min | 2 tasks | 6 files |
| Phase 07 P03 | 4min | 2 tasks | 6 files |
| Phase 08 P01 | 7min | 3 tasks | 17 files |
| Phase 08 P02 | 7min | 2 tasks | 39 files |
| Phase 08 P03 | 8min | 2 tasks | 6 files |
| Phase 09 P01 | 2min | 2 tasks | 5 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [v2.0 Roadmap]: 5-phase structure (5-9) following strict dependency chain: SP features -> model retrain -> pipeline -> API+dashboard -> infrastructure
- [v2.0 Roadmap]: API and Dashboard combined into Phase 8 (developed and tested together)
- [v2.0 Roadmap]: Infrastructure and Portfolio combined into Phase 9 (deploy last after local validation)
- [v2.0 Roadmap]: 5pm ET confirmation run is a third daily cron job (full pipeline re-run, not just flag update)
- [v2.0 Roadmap]: IsotonicRegression is the settled calibration method; temperature scaling only if reliability diagrams show problems
- [v2.0 Roadmap]: Memory limit audit (INFRA-01) is a hard gate BEFORE first VPS deploy
- [05-01]: 5-tier SP name resolution chain (exact -> override -> accent-strip -> ID bridge -> FG name lookup)
- [05-01]: Chadwick register cached via existing cache infrastructure for ID bridge Tier 1
- [05-02]: Versioned cache key (pitcher_game_log_v2_) prevents stale 3-column cache reuse
- [05-02]: Raw FIP formula (no cFIP constant) -- cancels in home-away differentials
- [05-02]: Cold-start imputation: 93 pitches (league avg), 7 days rest cap
- [05-03]: Season-to-date ERA and K-BB rate use cumsum+shift(1) from v2 game logs (temporally safe)
- [05-03]: WHIP/SIERA kept from FanGraphs season-level (hits not in game log v2)
- [05-03]: Cold-start cascade: rolling -> prev-season FanGraphs -> league-average constants
- [05-03]: K-BB rate per 9 IP: ((cumK - cumBB) * 9) / cumIP -- scale cancels in differentials
- [05-04]: Three named feature set constants: TEAM_ONLY (9 cols), SP_ENHANCED (20 cols), V1_FULL (14 cols, backward compat)
- [05-04]: xwoba_diff included in SP_ENHANCED despite v1 NaN bug -- fixed in v2 via corrected Statcast schema
- [05-04]: sp_k_pct_diff replaced by sp_k_bb_pct_diff in v2 SP_ENHANCED set
- [05-04]: build_and_save_v2 is a FeatureBuilder method (not standalone) for consistency
- [Phase 05]: Three named feature set constants: TEAM_ONLY (9 cols), SP_ENHANCED (20 cols), V1_FULL (14 cols)
- [06-01]: VIF pruned 3 features: is_home (constant=inf), team_woba_diff (VIF=163, redundant), sp_siera_diff (VIF=18, redundant FIP-family)
- [06-01]: SHAP kept all 17 post-VIF features (none below 0.1% importance threshold)
- [06-01]: Final v2 pruned set: 17 features (from 20 SP_ENHANCED); top SHAP: pyth_win_pct_diff (27%), sp_whip_diff (27%)
- [06-02]: SP_ENHANCED_PRUNED_COLS (17 features) used for v2 training; TEAM_ONLY kept at 9 features
- [06-02]: Artifact dict bundles model + IsotonicRegression calibrator + feature_cols for Phase 7 pipeline consumption
- [06-02]: SP_ENHANCED consistently beats TEAM_ONLY by 0.004-0.005 Brier across all model types
- [06-02]: Best model: LR sp_enhanced (0.2331 aggregate Brier); worst: XGB team_only (0.2397)
- [06-03]: v2 SP_ENHANCED RF is best on 2,128-game common set (Brier 0.2371), beats Kalshi market (0.2434) by 0.0063
- [06-03]: All 6 v2 models declared production-ready after human visual inspection of reliability diagrams
- [06-03]: IsotonicRegression calibration confirmed sufficient -- no temperature scaling needed
- [07-01]: psycopg3 (not psycopg2) for async-ready connection pool and modern Python type support
- [07-01]: ENUM types for prediction_version and prediction_status enforce domain values at DB level
- [07-01]: UPSERT pattern (ON CONFLICT DO UPDATE) for re-run safety instead of failing on duplicates
- [07-01]: apply_schema handles DuplicateObject for ENUMs to allow idempotent re-runs
- [07-02]: LiveFeatureBuilder delegates to FeatureBuilder private methods (accepted coupling risk for v1)
- [07-02]: fetch_kalshi_live_prices returns empty dict on API failure (graceful degradation, not exception)
- [07-02]: predict_game clips probabilities to [0.01, 0.99] for numerical safety
- [07-02]: Inference module fails hard on missing artifacts at startup (not at prediction time)
- [07-03]: Edge threshold 0.05 (5pp) for BUY_YES/BUY_NO signals
- [07-03]: TBD starters skip post_lineup entirely (PIPE-07); no fallback insertion as post_lineup
- [07-03]: Confirmation run marks old post_lineup rows is_latest=FALSE on SP change
- [07-03]: APScheduler BlockingScheduler (3.x) with 5-minute misfire_grace_time per job
- [08-01]: Sync def handlers (not async def) for all API routes -- psycopg3 sync connections run in FastAPI thread pool
- [08-01]: Ensemble prob and edge magnitude computed per-request in route handler, not stored in DB
- [08-01]: Route ordering enforced: /latest-timestamp before /{date} to prevent path parameter capture
- [08-02]: CSS custom properties reference UI-SPEC tokens; hex values never hard-coded in component CSS
- [08-02]: Game grouping (pre+post lineup) done client-side in usePredictions hook via Map aggregation
- [08-02]: Kalshi price formatted as cents (Math.round(price * 100)) matching API float response
- [08-02]: Self-hosted woff2 fonts committed to repo (no external CDN dependency)
- [08-03]: No additional visibilitychange listener needed -- TanStack React Query refetchIntervalInBackground: false handles pause/resume
- [08-03]: Error state with cached data shows grayed cards + offline badge, not full ErrorState replacement
- [08-03]: No retry button in ErrorState -- React Query auto-recovers when API responds
- [09-01]: mem_limit (not deploy.resources) for non-swarm Docker Compose compatibility
- [09-01]: Model artifacts bind-mounted read-only at runtime, not baked into Docker image
- [09-01]: API on host port 8082, worker gets 1024MB (double api/db) for ML inference
- [09-01]: Container name mlb-winforecaster-db-1 follows Docker Compose default naming convention

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 07, Tech Debt]: LiveFeatureBuilder.build_features_for_game() calls private methods on FeatureBuilder (_add_sp_features, _add_offense_features, etc.). Any rename or signature change to FeatureBuilder internals silently breaks the live pipeline at runtime. Acceptable for v1 pipeline; refactor to a stable adapter interface in a future phase if FeatureBuilder internals change.
- [Carry-forward]: pandas must stay at 2.2.x (not 3.0) due to pybaseball incompatibility
- [Carry-forward]: Kalshi historical data only available from 2025 -- edge comparison limited to ~1 season
- [Research]: pybaseball curl_cffi fix may not be in pinned v2.2.7 -- test before Phase 5 begins
- [Research]: MLB Stats API game log field coverage needs inspection for K/BB/HR per game and numberOfPitches

## Session Continuity

Last session: 2026-03-30T06:25:45Z
Stopped at: Completed 09-01 (Docker and deployment artifacts)
Resume file: None
