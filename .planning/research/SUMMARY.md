# Project Research Summary

**Project:** MLB Win Forecaster v2.0
**Domain:** Sports analytics — pre-game MLB win probability modeling with SP feature expansion and live dashboard deployment
**Researched:** 2026-03-29
**Confidence:** HIGH

## Executive Summary

The MLB Win Forecaster v2.0 is an evolution of an existing, working v1 system. The v1 model trains three classifiers (Logistic Regression, Random Forest, XGBoost) on a 14-feature matrix covering team-level offense, bullpen quality, starting pitcher season aggregates, and park factors. Research confirms the right approach for v2 is iterative and surgical: fix the known xwOBA bug (ADVF-07), expand SP features using per-game rolling window computation to eliminate temporal leakage, retrain and recalibrate all six model/feature-set combinations, then deploy a FastAPI + Postgres + React stack to a Hostinger KVM 2 VPS that already hosts Ghost CMS and GamePredictor. The recommended stack is stable and fully pinned — Python 3.12, pandas 2.2.x (explicitly not 3.0 due to breaking PyArrow string dtype changes with pybaseball), scikit-learn 1.8 (for temperature scaling calibration), XGBoost 3.2 as the primary model, and supercronic for twice-daily cron scheduling inside Docker.

The single most critical design decision is converting season-aggregate SP features to proper season-to-date rolling window computation using per-game logs with shift(1)-on-cumsum. The existing v1 code uses full-season FanGraphs totals as game-level features, which means a game on June 15 uses pitcher statistics that include starts from July through September — a form of temporal leakage that inflates backtest Brier scores and will not hold in live prediction. Fixing this is more important than adding any new SP feature. The second structural risk is the FanGraphs/pybaseball data source: Cloudflare protection has been blocking scraping since mid-2025 (GitHub issue #479, still open March 2026), and while a curl_cffi fix exists in pybaseball master, it may not be in the pinned version. The historical data cache (2015–2024) is already on disk and must be treated as immutable; all new feature development should route through MLB Stats API game logs wherever possible.

The deployment pattern is well-understood because GamePredictor on the same VPS already follows it: Docker Compose with FastAPI + Postgres + worker + Nginx frontend exposed on port 8082 via host-level Nginx reverse proxy with Certbot SSL. The new constraints are shared-RAM risk (8 GB across four services) and the requirement to set explicit memory limits before first deploy. All infrastructure pitfalls have known, documented mitigations and are low-recovery-cost if they occur. The research flags temporal leakage and pybaseball reliability as the high-cost risks that must be addressed before any retraining occurs.

---

## Key Findings

### Recommended Stack

The stack is anchored by a critical version constraint: pandas 2.2.x paired with numpy 2.2.x. Pandas 3.0 (Jan 2026) introduced PyArrow-backed string dtypes that break compatibility with pybaseball's object-dtype DataFrames — this is a hard blocker, not a preference. Python 3.12 is the recommended runtime. The ML layer uses scikit-learn 1.8 (temperature scaling now available in CalibratedClassifierCV), XGBoost 3.2 as the primary gradient boosting model (better sports analytics documentation and examples than LightGBM), and SHAP 0.51 for feature importance validation.

**Core technologies:**
- Python 3.12: runtime — minimum for the full dependency graph; avoid 3.14 (pybaseball not tested)
- pandas 2.2.3 + numpy 2.2.x: data processing — hard pin below pandas 3.0 to avoid PyArrow dtype breaking changes
- scikit-learn 1.8.0: modeling and calibration — temperature scaling (new in 1.8) is a better calibration option than isotonic for small calibration sets
- XGBoost 3.2.0: primary gradient boosting — full sklearn API; better documentation for sports analytics than LightGBM
- LightGBM 4.6.0: benchmarking only — keep for comparison; do not make it the primary model
- SHAP 0.51.0: explainability — TreeExplainer works natively with XGBoost; required for feature importance validation
- Optuna 4.8.0: hyperparameter search — pruning callbacks for XGBoost are dramatically faster than GridSearchCV
- pybaseball 2.2.7: historical data ingestion — treat 2015-2024 cache as immutable; watch for 403s on new season data
- MLB-StatsAPI 1.9.0: schedules, rosters, pitcher game logs — more reliable than FanGraphs for live data
- kalshi-python 2.1.4: prediction market prices — official SDK with RSA-PSS auth
- FastAPI + SQLAlchemy 2.0 async + asyncpg: API layer — same proven pattern as GamePredictor on same VPS
- Postgres 16 (Docker): persistence — ACID, trivially handles 2,430 rows/season
- supercronic: cron in Docker — purpose-built for containers; avoids every cron-in-Docker failure mode

**Do not use:** pandas 3.0, numpy 2.4, TensorFlow/PyTorch (overkill for 12K-row tabular data), Spark/Dask (dataset is trivially small), Streamlit/Dash (out of scope), Celery (overkill for 2 cron jobs/day).

### Expected Features

Research identifies a specific set of SP features to add, fix, and drop relative to the v1 feature matrix. The v1 baseline (14 features, including the broken `xwoba_diff`) is the starting point.

**Must have (fix existing or add with high evidence):**
- xwOBA differential fix (ADVF-07) — column is `est_woba` not `xwoba`; join column is `"last_name, first_name"` as a single merged string (verified against live Baseball Savant CSV 2026-03-29)
- Season-to-date SP features — convert all season-aggregate FanGraphs stats to rolling window (cumsum + shift(1)) to eliminate temporal leakage; this is the highest-priority engineering task
- K-BB% differential (`sp_k_bb_pct_diff`) — replace `sp_k_pct_diff`; K-BB% explains 17.92% of future RA9 variance vs. under 10% for K/BB; computed as K% minus BB% from existing `pitching_stats()` data
- WHIP differential (`sp_whip_diff`) — already in FanGraphs data, just not used; top-tier run prevention predictor with independent signal from FIP-family

**Should have (differentiators with moderate evidence):**
- SP ERA differential season-to-date (`sp_era_diff`) — captures BABIP/sequencing signal that FIP strips out; comes naturally from season-to-date conversion
- Recent form FIP differential (`sp_recent_fip_diff`) — 30-day rolling FIP from game log K/BB/HR/IP; more stable than recent ERA at small samples
- SP workload: pitch count last start (`sp_pitch_count_last_diff`) — each pitch increases next-game ERA by 0.007 (peer-reviewed); impute NaN first start with league-average 93 pitches
- SP days rest differential (`sp_days_rest_diff`) — encode as integer [3,7] capped; cheap to compute; mixed evidence but not harmful

**Drop from v1 feature set (redundancy pruning):**
- `sp_fip_diff` — redundant with SIERA; SIERA RMSE 0.964 vs FIP 1.010 for year-to-year prediction; SIERA strictly dominates
- `sp_xfip_diff` — nearly identical to SIERA for predictive purposes; pick one, keep SIERA
- `sp_k_pct_diff` — replaced by `sp_k_bb_pct_diff` which is strictly more informative

**Defer to v2+:**
- Home/away splits per SP — sample size insufficient (BABIP needs 2000 BIP; single-season H/A split provides ~200-250 BIP)
- Batter vs. pitcher matchups — confirmed anti-feature; pure noise at typical career PA sample sizes
- xERA from Statcast — redundant with xwOBA; same batted-ball signal; adds noise not signal

**Two-model architecture:** `TEAM_ONLY_FEATURE_COLS` (pre-lineup, 10am run) and `SP_ENHANCED_FEATURE_COLS` (post-lineup, 1pm run). Three model types times two feature sets equals six model artifacts total.

### Architecture Approach

The v2 architecture extends the existing v1 codebase without a rewrite. All new SP features are added inside the existing `_add_sp_features()` method (not a new method) to preserve the single-pass lookup pattern. The `feature_sets.py` contract between FeatureBuilder and model input defines two named feature set constants; the v1 constants are preserved (renamed `V1_*`) for apples-to-apples backtest comparison. The deployment follows GamePredictor's proven pattern: Docker Compose on port 8082, host-level Nginx reverse proxy with Certbot SSL at `mlbforecaster.silverreyes.net`.

**Major components:**
1. FeatureBuilder (`src/features/feature_builder.py`) — ingests raw data, computes all features, outputs feature matrix Parquet; single source of truth for feature engineering; both backtest and live pipeline use identical code path
2. Six model artifacts (joblib files) — LR/RF/XGBoost x team_only/sp_enhanced, each paired with IsotonicRegression calibrator; stored in Docker named volume shared between worker and API containers
3. Postgres schema (`games`, `predictions`, `pipeline_runs`) — `predictions` stores both prediction versions as separate rows with `is_latest` flag; edge values computed at insert time by the worker, not at query time by the API
4. FastAPI service (6 endpoints) — read-only API backed by async SQLAlchemy; loads all 6 model artifacts at startup via lifespan event; no computation in request handlers
5. Pipeline worker (supercronic) — twice-daily execution (10am pre-lineup using team-only features, 1pm post-lineup using SP-enhanced features); writes to Postgres, marks old predictions `is_latest=FALSE`
6. React frontend + host Nginx — static build served via Docker-internal Nginx; host Nginx reverse-proxies all traffic from port 8082

**Feature data flow:**
```
MLB Stats API game logs (per-pitcher, per-game)
  -> cumsum + shift(1) per season -> season-to-date SP stats
  -> 30-day calendar window -> recent form SP stats
  -> shift(1) on sorted log -> workload (pitch count, days rest)

FanGraphs via pybaseball (season aggregate, cached 2015-2024)
  -> cold-start fallback for first start of season

Baseball Savant via pybaseball (est_woba from "last_name, first_name" column)
  -> xwoba_diff after ADVF-07 fix
```

### Critical Pitfalls

1. **Temporal leakage in season-aggregate SP features** — v1 uses full-season FanGraphs totals as game-level features; a June game sees September stats. Convert to per-game rolling aggregates with `shift(1)` on cumulative sums before adding or expanding any SP feature. Getting this wrong invalidates the entire retrained model. Recovery cost: HIGH (full pipeline rebuild, 4-8 hours).

2. **pybaseball FanGraphs endpoints return HTTP 403** — Cloudflare protection active since mid-2025 (issue #479, still open March 2026); treat the existing 2015-2024 historical Parquet cache as immutable; add `try/except` with specific `HTTPError` catch around every pybaseball call; fall back to MLB Stats API game logs for current-season data if FanGraphs fails.

3. **Feature matrix shape change breaks model pipeline** — adding SP columns requires a strict sequence: (a) update FeatureBuilder, (b) regenerate feature store Parquet (version it as `feature_store_v2.parquet`), (c) verify new columns are non-NaN, (d) update `feature_sets.py`, (e) retrain all 6 models. Out-of-order steps cause `KeyError` crashes or silent NaN imputation of new columns. Add a schema validation assertion at the top of `run_backtest()`.

4. **Isotonic calibration invalidation after retrain** — adding features changes the raw probability distribution; the old isotonic mapping is invalid; always recalibrate from scratch after any feature set change; verify with reliability diagrams for all 6 model/feature-set combinations before declaring v2 complete.

5. **Docker OOM kills Ghost CMS and GamePredictor** — 8 GB VPS shared across four services (Ghost, GamePredictor, new MLB stack, host OS); set explicit memory limits in `docker-compose.yml` before first deploy (api: 512M, worker: 1G, postgres: 512M); budget only 60-70% of total RAM for the new stack.

6. **SP name matching silently produces NaN features** — v1 has ~17% NaN rate from name format mismatches between MLB Stats API and FanGraphs; new SP features inherit this NaN pattern; NaN is imputed to median (league average), incorrectly treating elite/terrible pitchers as average; evaluate ID-based matching via `mlb_player_id -> fangraphs_id` cross-reference before Phase 1 commits to an implementation.

---

## Implications for Roadmap

Research shows a clear dependency ordering: fix data integrity first, then add features, then retrain, then deploy. Each phase has well-defined inputs and outputs. Phases 3-5 are largely sequential; Phase 1 is where the most design decisions live and where the most re-work cost is incurred if done wrong.

### Phase 1: SP Feature Integration (Data Layer)

**Rationale:** Temporal leakage in existing SP features is the highest-priority risk. Fixing the data layer before retraining is mandatory — every model trained on leaked data produces invalid Brier scores that will not reproduce in live deployment. This phase has no external deployment dependencies and is pure data engineering.

**Delivers:**
- ADVF-07 fix: `xwoba_diff` working with correct `est_woba` column name and `"last_name, first_name"` join strategy
- Season-to-date rolling SP features replacing season-aggregate lookups (cumsum + shift(1) per season per pitcher)
- New SP feature columns: `sp_k_bb_pct_diff` (replaces `sp_k_pct_diff`), `sp_whip_diff`, `sp_era_diff`, `sp_recent_fip_diff`, `sp_pitch_count_last_diff`, `sp_days_rest_diff`
- Dropped columns: `sp_fip_diff`, `sp_xfip_diff`, `sp_k_pct_diff` (redundant with SIERA and K-BB%)
- `SP_ENHANCED_FEATURE_COLS` and `TEAM_ONLY_FEATURE_COLS` defined in `feature_sets.py`; `V1_FULL_FEATURE_COLS` preserved for comparison
- Feature store versioned as `feature_store_v2.parquet`
- Temporal safety test suite extended to cover all new SP columns (all new features must pass: feature values change game-to-game, no constant values within a season per pitcher)
- Cold-start handling: previous season aggregate as prior; league-average replacement level for rookies

**Addresses:** FEATURES.md table stakes (xwOBA fix, K-BB%, WHIP), differentiators (ERA STD, recent FIP, workload)
**Avoids:** Pitfall #2 (temporal leakage), Pitfall #1 (add pybaseball error handling), Pitfall #5 (SP name matching — decide on ID vs. name approach before writing feature code)

**Research flag:** Standard patterns. The shift(1)-on-cumsum pattern is already used in v1 for `rolling_ops_diff`. Cold-start handling edge cases deserve careful task breakdown.

### Phase 2: Model Retrain and Calibration

**Rationale:** Cannot retrain until the feature store Parquet is verified correct (Phase 1 output). This phase produces the 6 model artifacts needed by both the live pipeline and the API. The calibration step is load-bearing — isotonic regression must be re-fitted from scratch on the new probability distribution.

**Delivers:**
- 6 retrained and calibrated models: LR/RF/XGBoost x team_only/sp_enhanced
- Brier score comparison: v2 vs. v1 on identical test folds using respective feature sets (apples-to-apples, not different folds)
- Reliability diagrams for all 6 model/feature-set combinations (visual inspection required, not just Brier score)
- VIF analysis on expanded SP feature set; any feature with VIF > 10 dropped
- XGBoost feature importance (SHAP) ranking; near-zero-gain features dropped before final model
- Ablation study: retrain with and without new SP features to quantify Brier score contribution
- `model_metadata.json` with training date, feature columns, fold info, and Brier scores per fold

**Uses:** scikit-learn 1.8 temperature scaling (compare against isotonic on 2020 fold with only ~891 games), Optuna 4.8 for hyperparameter search, SHAP 0.51 for feature importance
**Avoids:** Pitfall #3 (schema change sequence — regenerate Parquet before updating feature_sets.py), Pitfall #4 (calibration invalidation — always recalibrate from scratch)

**Research flag:** Standard patterns. Walk-forward backtest with `FOLD_MAP` and isotonic calibration are already implemented in v1. The temperature scaling comparison vs. isotonic on small folds is a new decision point worth testing empirically.

### Phase 3: Live Pipeline and Database

**Rationale:** Pipeline logic builds on the trained models (Phase 2 outputs) and the database schema. This phase wires together FeatureBuilder, model artifacts, Postgres, and supercronic scheduling. Must be complete and validated locally before Phase 4 (API) can serve live data.

**Delivers:**
- Postgres schema: `games`, `predictions`, `pipeline_runs` tables with `is_latest` flag and appropriate indexes
- `pipeline/run.py`: twice-daily execution with `--version pre_lineup` / `--version post_lineup` argument
- Pre-lineup fallback: uses `TEAM_ONLY_FEATURE_COLS` for all games; SP features skipped even if accidentally available
- SP-change detection: SP name stored per prediction row; dashboard can show "SP may have changed" for predictions older than 3 hours
- Health check endpoint returning `last_pipeline_run` timestamp
- Pipeline log to persistent file; external uptime monitor (UptimeRobot) configured on `/api/v1/health`
- Kalshi price fetch and edge computation stored per prediction row at insert time

**Implements:** ARCHITECTURE.md Postgres schema, worker pipeline logic, supercronic crontab
**Avoids:** Pitfall #6 (SP scratch/stale prediction — SP name in database, timestamp on dashboard), Pitfall #10 (silent cron failure — supercronic logs to stdout, health check endpoint)

**Research flag:** Supercronic and the twice-daily pipeline pattern are well-documented. The SP-change detection between 1pm and first pitch (every 30 minutes) is the one novel component — design whether this triggers a full re-run or just a "possibly stale" flag before implementation.

### Phase 4: API and Dashboard

**Rationale:** The API is a thin read layer over Postgres. Once the database is populated by Phase 3, this phase is straightforward. The React frontend is the user-facing output of the entire project.

**Delivers:**
- FastAPI service with 6 endpoints: `/api/v1/predictions/today`, `/api/v1/predictions/{date}`, `/api/v1/predictions/latest-timestamp`, `/api/v1/results`, `/api/v1/results/accuracy`, `/api/v1/health`
- All 6 model artifacts loaded at startup via lifespan event; no model loading in request handlers
- React dashboard: today's predictions with LR/RF/XGB probabilities, Kalshi prices, edge values, SP names, and confirmation status
- "Last updated: [timestamp]" displayed prominently; predictions grayed out if older than 3 hours
- "SP TBD — team-only estimate" visual indicator for unconfirmed starters
- Explicit error state when API is unreachable (not a blank page or infinite spinner)
- Client polling every 60 seconds with `If-Modified-Since` headers; polling paused when browser tab is hidden

**Implements:** ARCHITECTURE.md FastAPI project structure, response schemas, lifespan model loading pattern
**Avoids:** PITFALLS.md UX pitfalls (stale predictions, no error state, aggressive polling at 10-second intervals, hiding uncertainty)

**Research flag:** Standard FastAPI + async SQLAlchemy + React patterns. No research-phase needed.

### Phase 5: Infrastructure and Deployment

**Rationale:** Deploy last, after all components are validated locally. The VPS hosting environment has shared resources; infrastructure mistakes can take down Ghost CMS and GamePredictor. All pitfalls here are preventable with upfront configuration but are high-impact if skipped.

**Delivers:**
- Docker Compose stack on port 8082 with explicit memory limits (api: 512M, worker: 1G, postgres: 512M)
- Named Docker volume for Postgres (`pgdata`); anonymous volumes prohibited; persistence test before go-live
- Host Nginx server block for `mlbforecaster.silverreyes.net` validated with `nginx -t` before enabling
- Certbot SSL cert issued and renewal dry-run tested
- Daily Postgres backup via `pg_dump` to `/opt/backups/`
- Deployment checklist document: "Never run `docker-compose down -v` on production"
- Memory monitoring cron: `docker stats --no-stream` every 5 minutes to log

**Implements:** ARCHITECTURE.md Docker Compose topology and host Nginx vhost config
**Avoids:** Pitfall #7 (Docker OOM), Pitfall #8 (Nginx config kills all sites), Pitfall #9 (Postgres volume loss)

**Research flag:** Follows established GamePredictor pattern on same VPS. No research-phase needed — exact Nginx config and Docker Compose structure are fully documented in ARCHITECTURE.md.

### Phase Ordering Rationale

- **Data before models:** Temporal leakage is a correctness problem, not a performance problem. Training on leaked data produces invalid results that require a full re-do when caught late.
- **Models before pipeline:** The pipeline worker loads model artifacts. Artifacts must exist before the pipeline can be deployed and tested end-to-end.
- **Pipeline before API:** The API serves data from Postgres. Postgres must be populated before the API returns meaningful responses.
- **API before infrastructure:** Validate all components working in Docker locally before touching the production VPS. One bad Nginx config takes down four services simultaneously.
- **Phase 1 is the critical path:** It is where the most design decisions live (ID matching strategy, cumsum pattern, cold-start handling) and where the most re-work cost is incurred if done wrong.

### Research Flags

**Phases needing closer attention during planning:**
- **Phase 1 (SP Feature Integration):** The season-to-date cumulative computation with shift(1) requires careful design, especially around the cold-start edge case (first start of season, rookies, mid-season call-ups). The ID-based name matching feasibility decision needs to be made before feature code is written. Recommend a detailed task breakdown.
- **Phase 3 (Live Pipeline):** The SP-change detection logic between 1pm and first pitch is the one genuinely novel component. Decide before implementation whether a "flag as possibly stale" approach is sufficient vs. a full re-run trigger for changed starters.

**Phases with standard patterns (no additional research needed):**
- **Phase 2 (Model Retrain):** Walk-forward backtest, isotonic calibration, and SHAP feature importance are all implemented in v1. Extend, do not rewrite. Temperature scaling vs. isotonic is an empirical decision, not a research gap.
- **Phase 4 (API and Dashboard):** FastAPI + async SQLAlchemy + React is thoroughly documented with established patterns.
- **Phase 5 (Infrastructure):** Follows GamePredictor's proven deployment pattern on the same VPS with exact configuration documented.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified on PyPI; pandas 2.2.x pin justified with official migration guide; scikit-learn 1.8 temperature scaling confirmed in release highlights; XGBoost 3.2 sklearn API compatibility verified |
| Features | HIGH | xwOBA bug root-cause verified against live Baseball Savant CSV endpoint 2026-03-29; SIERA RMSE advantage confirmed from Pitcher List peer analysis; K-BB% finding from multiple FanGraphs community studies; BABIP stabilization data from FanGraphs Sabermetrics Library |
| Architecture | HIGH | Based on direct analysis of v1 codebase source files; deployment pattern mirrors verified GamePredictor stack on same VPS; Postgres schema is standard and well-reasoned; FastAPI lifespan pattern from official docs |
| Pitfalls | HIGH | pybaseball 403 issue verified against open GitHub issues (March 2026); temporal leakage analysis based on direct code inspection of `feature_builder.py`; Docker OOM and Nginx pitfalls from official Docker docs and v1 VPS lessons |

**Overall confidence:** HIGH

### Gaps to Address

- **pybaseball curl_cffi fix version:** The Cloudflare bypass fix exists in pybaseball master but may not be in v2.2.7. Before Phase 1 begins, test `pitching_stats()` against a 2025 or 2026 season to determine if a version upgrade is needed. Document the exact working version.

- **MLB Stats API game log field coverage:** FEATURES.md notes that cached pitcher game logs may lack K/BB/HR per game (needed for `sp_recent_fip_diff`) and `numberOfPitches` may not be in cached logs (needed for `sp_pitch_count_last_diff`). Inspect an actual cached log file before implementing those features. A re-fetch with additional stat hydration may be required.

- **Temperature scaling vs. isotonic on small folds:** The 2020 calibration fold has only ~891 games, which is marginal for isotonic regression. During Phase 2, compare reliability diagrams for temperature scaling vs. isotonic on the smallest fold to determine which is more robust for this dataset.

- **ID-based SP name matching feasibility:** PITFALLS.md recommends building a `mlb_player_id -> fangraphs_id` cross-reference table to fix the ~17% NaN rate from name mismatches. The data source for this mapping (Chadwick Bureau register, pybaseball `playerid_lookup()`, or a hand-built table) needs to be evaluated before Phase 1 implementation begins.

- **Kalshi historical data scope:** Kalshi sports markets launched in early 2025. The edge analysis and model-vs-Kalshi comparison is limited to approximately one season. This is a hard constraint noted in v1 research that carries forward.

---

## Sources

### Primary (HIGH confidence)
- pybaseball PyPI (v2.2.7, Sep 2023) and GitHub issues #479, #492, #495 — version confirmed; Cloudflare issue verified March 2026
- MLB-StatsAPI PyPI (v1.9.0, Apr 2025) — schedule, roster, and game log functions confirmed
- kalshi-python PyPI (v2.1.4, Sep 2025) — official SDK with RSA-PSS auth
- pandas 3.0 migration guide (official) — breaking PyArrow string dtype changes documented
- scikit-learn 1.8 release highlights (official) — temperature scaling calibration confirmed
- Baseball Savant Expected Statistics CSV (verified 2026-03-29) — `est_woba` and `last_name, first_name` column names confirmed at primary source
- FanGraphs Sabermetrics Library: Sample Size — K% stabilizes at 70 BF, BB% at 170 BF, BABIP at 2000 BIP
- Pitcher List: Going Deep on FIP/xFIP/SIERA — SIERA RMSE 0.964 vs FIP 1.010 for year-to-year prediction
- v1 codebase direct analysis — `feature_builder.py`, `sp_stats.py`, `sp_recent_form.py`, `feature_sets.py`, `backtest.py`, `team_mappings.py`
- SHAP PyPI (v0.51.0, Mar 2026) — verified
- Optuna PyPI (v4.8.0) — verified
- joblib PyPI (v1.5.3, Dec 2025) — verified
- JupyterLab PyPI (v4.5.6, Mar 2026) — verified
- Docker docs: Resource constraints and volume persistence — memory limits and OOM behavior

### Secondary (MEDIUM confidence)
- FanGraphs Community: K-BB% analysis — K-BB% explains 17.92% of future RA9 variance (community study, consistent with FanGraphs main site)
- Pitcher List Part II: xFIP and SIERA most predictive forward-looking metrics
- FiveThirtyEight MLB methodology — SP adjustment worth ~1% correct-call improvement; opener handling strategy
- Journal of Strength and Conditioning Research (2012, PubMed) — pitch count effect on next-game ERA (~0.007 per pitch); peer-reviewed but effect is small
- FanGraphs Community: Days of rest analysis — no significant difference across rest categories (single study)
- PMC: Feature Selection for MLB Game Prediction — RFE feature selection methodology
- Wharton thesis: Forecasting MLB Game Outcomes — 10-day trailing differentials, cold-start handling approaches
- Beyond the Box Score: Stop using K/BB — K-BB% vs. K/BB ratio argument (well-reasoned, single article)

### Tertiary (LOW confidence)
- Baseball Prospectus: Siren Song of Expected Metrics — xwOBA not clearly better than FIP for pitcher prediction (single analysis; counters the "more Statcast = better" assumption but should be validated against current data)
- pybaseball GitHub issue #479 comment thread — curl_cffi fix details; community-reported, not confirmed by pybaseball maintainers

---
*Research completed: 2026-03-29*
*Ready for roadmap: yes*
