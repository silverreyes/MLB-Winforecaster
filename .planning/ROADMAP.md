# Roadmap: MLB Win Probability Model

## Milestones

- ✅ **v1.0 MVP** -- Phases 1-4 (shipped 2026-03-29) -- [Archive](.planning/milestones/v1.0-ROADMAP.md)
- 🚧 **v2.0 Live Platform** -- Phases 5-9 (in progress)

## Phases

<details>
<summary>v1.0 MVP (Phases 1-4) -- SHIPPED 2026-03-29</summary>

- [x] Phase 1: Data Ingestion and Raw Cache (3/3 plans) -- completed 2026-03-28
- [x] Phase 2: Feature Engineering and Feature Store (3/3 plans) -- completed 2026-03-29
- [x] Phase 3: Model Training and Backtesting (2/2 plans) -- completed 2026-03-29
- [x] Phase 4: Kalshi Market Comparison and Edge Analysis (2/2 plans) -- completed 2026-03-29

</details>

### v2.0 Live Platform (In Progress)

- [x] **Phase 5: SP Feature Integration** - Fix data bugs, convert SP stats to rolling season-to-date, add new SP features, produce v2 feature store (completed 2026-03-29)
- [x] **Phase 6: Model Retrain and Calibration** - Train 6 model artifacts (3 models x 2 feature sets), calibrate, validate, persist (completed 2026-03-30)
- [x] **Phase 7: Live Pipeline and Database** - Postgres schema, three-run daily pipeline (10am/1pm/5pm), Kalshi edge computation at insert time (completed 2026-03-30)
- [x] **Phase 8: API and Dashboard** - FastAPI read layer over Postgres, React frontend with dark/amber aesthetic, client-side polling, error states (completed 2026-03-30)
- [ ] **Phase 9: Infrastructure and Go-Live** - Docker Compose on VPS with memory limits, Nginx + SSL, Postgres backups, portfolio page

## Phase Details

### Phase 5: SP Feature Integration
**Goal**: All starting pitcher features are correctly engineered with temporal safety, producing a verified v2 feature store that models can train on without data leakage
**Depends on**: Phase 4 (v1.0 complete)
**Requirements**: SP-01, SP-02, SP-03, SP-04, SP-05, SP-06, SP-07, SP-08, SP-09, SP-10, SP-11, SP-12
**Success Criteria** (what must be TRUE):
  1. `xwoba_diff` column is non-NaN for games where both starters have Statcast data (the v1 100% NaN bug is fixed via correct `est_woba` column name and `"last_name, first_name"` split-and-reverse join)
  2. Every SP stat column changes game-to-game within a season per pitcher (temporal safety tests pass, confirming season-to-date rolling via cumsum+shift(1) instead of season-aggregate lookups)
  3. `feature_store_v2.parquet` exists with all new SP columns (`sp_k_bb_pct_diff`, `sp_whip_diff`, `sp_era_diff`, `sp_recent_fip_diff`, `sp_pitch_count_last_diff`, `sp_days_rest_diff`) and the v1 feature store is preserved unchanged
  4. `feature_sets.py` exports three named constants (`TEAM_ONLY_FEATURE_COLS`, `SP_ENHANCED_FEATURE_COLS`, `V1_FULL_FEATURE_COLS`) and models can load either feature set from the v2 feature store without KeyError
  5. Cold-start pitchers (first start of season, rookies, mid-season call-ups) have imputed values -- no NaN rows propagate to model input for any game with a resolved starting pitcher
**Plans:** 4/4 plans complete

Plans:
- [ ] 05-01-PLAN.md -- Fix xwOBA bug and build ID-based SP name matching cross-reference (SP-01, SP-02)
- [ ] 05-02-PLAN.md -- Extend pitcher game log extraction and add FIP/pitch-count/days-rest computation (SP-07, SP-08)
- [ ] 05-03-PLAN.md -- Convert SP stats to season-to-date rolling, add K-BB%/WHIP/ERA differentials, cold-start handling (SP-03, SP-04, SP-05, SP-06, SP-10)
- [ ] 05-04-PLAN.md -- Wire remaining features, define feature set constants, build v2 store, complete temporal safety tests (SP-07, SP-08, SP-09, SP-11, SP-12)

### Phase 6: Model Retrain and Calibration
**Goal**: Six validated model artifacts (LR/RF/XGBoost x team-only/SP-enhanced) exist with verified calibration and documented Brier score improvements over v1
**Depends on**: Phase 5 (v2 feature store must exist)
**Requirements**: MDL-01, MDL-02, MDL-03, MDL-04, MDL-05, MDL-06, MDL-07
**Success Criteria** (what must be TRUE):
  1. All 6 model artifacts exist as joblib files in `models/artifacts/` alongside a `model_metadata.json` recording training date, feature column list, per-fold Brier scores, and calibration method (IsotonicRegression; temperature scaling evaluated only if reliability diagrams show problems)
  2. Brier score comparison table shows v2 SP_ENHANCED vs v2 TEAM_ONLY vs v1 vs Kalshi market on identical 2025 out-of-sample games -- the comparison is apples-to-apples on the same game set
  3. Reliability diagrams (calibration curves) for all 6 model/feature-set combinations have been generated and visually inspected; no model is declared production-ready without this step
  4. VIF analysis confirms no feature in the final SP_ENHANCED set has VIF > 10, and SHAP TreeExplainer confirms no XGBoost feature has near-zero gain -- redundant/useless features have been dropped before final training
**Plans:** 3/3 plans complete

Plans:
- [ ] 06-01-PLAN.md -- VIF and SHAP analysis modules + build v2 feature store + feature selection (MDL-05, MDL-06)
- [ ] 06-02-PLAN.md -- Walk-forward v2 backtest, 2025 predictions, artifact persistence (MDL-01, MDL-02, MDL-07)
- [ ] 06-03-PLAN.md -- Brier comparison table, reliability diagrams, visual inspection checkpoint (MDL-03, MDL-04)

### Phase 7: Live Pipeline and Database
**Goal**: A three-run daily pipeline (pre-lineup, post-lineup, confirmation) populates Postgres with predictions, Kalshi edges, and SP metadata that downstream API endpoints can query
**Depends on**: Phase 6 (model artifacts must exist for pipeline to produce predictions)
**Requirements**: PIPE-01, PIPE-02, PIPE-03, PIPE-04, PIPE-05, PIPE-06, PIPE-07, PIPE-08
**Success Criteria** (what must be TRUE):
  1. Postgres `predictions` table contains rows for today's games with `prediction_version` values of `pre_lineup` (from 10am ET run) and `post_lineup` (from 1pm ET run), each storing LR/RF/XGB probabilities, Kalshi price, edge signal, SP names, and `is_latest` flag
  2. The 5pm ET confirmation run is a full pipeline re-run (not just a flag update) that re-fetches current SP assignments; if a starter differs from the 1pm prediction, the old row is marked `is_latest = FALSE`, an updated row is inserted, and `sp_may_have_changed = TRUE` is set on the new row
  3. When starters are TBD or unresolvable, the pipeline stores a `TEAM_ONLY` prediction with `sp_uncertainty = TRUE` and does not insert a `post_lineup` version until starters are confirmed; the `predictions` table schema enforces this at the database level — either via a `prediction_status` enum (e.g., `confirmed`, `pending_sp`, `tbd`) with a CHECK constraint, or a nullable `sp_confirmed_at` timestamp column — so that the "no post_lineup without confirmed starters" invariant cannot be violated by application bugs
  4. `GET /api/v1/health` returns `last_pipeline_run` timestamp and status for each version (pre_lineup, post_lineup, confirmation); pipeline runs are logged to a persistent file
**Plans:** 3/3 plans complete

Plans:
- [ ] 07-01-PLAN.md -- Postgres schema, DB access layer, and test infrastructure (PIPE-01, PIPE-07)
- [ ] 07-02-PLAN.md -- LiveFeatureBuilder, inference module, live data adapters (PIPE-02, PIPE-03, PIPE-05)
- [ ] 07-03-PLAN.md -- Pipeline runner, scheduler, health endpoint, entry point (PIPE-02, PIPE-03, PIPE-04, PIPE-05, PIPE-06, PIPE-07, PIPE-08)

### Phase 8: API and Dashboard
**Goal**: Users visit mlbforecaster.silverreyes.net and see today's MLB game predictions with model probabilities, Kalshi edge signals, and SP confirmation status -- updated automatically via client-side polling
**Depends on**: Phase 7 (Postgres must be populated before API serves meaningful data)
**Requirements**: API-01, API-02, API-03, API-04, API-05, API-06, DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, DASH-06, DASH-07
**Note**: DASH-01 specifies the `frontend-design` skill must be invoked before this phase's planning begins. This is a plan-time gate, not a roadmap-time gate -- `/gsd:plan-phase 8` must apply the frontend-design skill to produce the design system before any implementation plans are written.
**Success Criteria** (what must be TRUE):
  1. Visiting the dashboard shows today's games with pre-lineup and post-lineup predictions side-by-side, including LR/RF/XGB probabilities per version, Kalshi price, edge signal (BUY_YES/BUY_NO/NO_EDGE), and confirmed starter names (or "TBD" with visual flag)
  2. The page shows "Last updated: [timestamp]" prominently; prediction cards are grayed out with a staleness indicator when the most recent prediction is older than 3 hours; `sp_may_have_changed` is surfaced as a warning indicator
  3. Client-side polling fires every 60 seconds against `/api/v1/predictions/latest-timestamp` when `document.visibilityState === 'visible'`, suspends on `visibilitychange` to `'hidden'`, and resumes on return to `'visible'`; a "New predictions available -- refresh" banner appears when the polled timestamp is newer than displayed data
  4. When the API is unreachable, the dashboard renders an explicit error state (not a blank page or infinite spinner) showing last-known data with a "Dashboard offline" indicator and timestamp of last successful fetch
  5. All 6 model artifacts are loaded at FastAPI startup via lifespan context manager; no model loading inside request handlers; API fails to start (not silently) if any artifact is missing
**Plans:** 3/3 plans complete

Plans:
- [x] 08-01-PLAN.md -- FastAPI app scaffold, all 5 API endpoints, test suite (API-01, API-02, API-03, API-04, API-05, API-06)
- [x] 08-02-PLAN.md -- React 19 frontend scaffold, all dashboard UI components, game cards (DASH-01, DASH-02, DASH-03, DASH-04)
- [x] 08-03-PLAN.md -- Polling, staleness, error states, visual verification checkpoint (DASH-05, DASH-06, DASH-07)

### Phase 9: Infrastructure and Go-Live
**Goal**: The complete stack is deployed to the Hostinger KVM 2 VPS with verified memory headroom, SSL, backups, and a portfolio page linking to the live dashboard
**Depends on**: Phase 8 (all components validated locally before touching production VPS)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, PORT-01
**Success Criteria** (what must be TRUE):
  1. Docker Compose stack runs on port 8082 with explicit memory limits (`api: 512M`, `worker: 1G`, `db: 512M`); `docker stats --no-stream` confirms remaining headroom is sufficient on the shared 8GB VPS (Ghost CMS + GamePredictor + OS baseline already consuming ~2.4GB) -- this memory audit is a hard gate completed BEFORE the first VPS deploy, not after
  2. `https://mlbforecaster.silverreyes.net` serves the dashboard over SSL; Nginx server block is validated with `nginx -t` before reload; Certbot renewal dry-run (`certbot renew --dry-run`) passes
  3. Postgres data persists in named Docker volume `mlb_pgdata` (verified by stop/start cycle before go-live); daily `pg_dump` backup cron writes to `/opt/backups/mlb/` with 7-day retention
  4. Portfolio page at `silverreyes.net/mlb-winforecaster` displays methodology overview, Brier score comparison table (v1 vs v2 TEAM_ONLY vs v2 SP_ENHANCED vs Kalshi), calibration curve images, and links to the live dashboard -- no backend API calls from the portfolio page
**Plans**: TBD

Plans:
- [ ] 09-01: TBD
- [ ] 09-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 5 -> 6 -> 7 -> 8 -> 9

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|---------------|--------|-----------|
| 1. Data Ingestion and Raw Cache | v1.0 | 3/3 | Complete | 2026-03-28 |
| 2. Feature Engineering and Feature Store | v1.0 | 3/3 | Complete | 2026-03-29 |
| 3. Model Training and Backtesting | v1.0 | 2/2 | Complete | 2026-03-29 |
| 4. Kalshi Market Comparison and Edge Analysis | v1.0 | 2/2 | Complete | 2026-03-29 |
| 5. SP Feature Integration | v2.0 | 4/4 | Complete | 2026-03-29 |
| 6. Model Retrain and Calibration | v2.0 | 3/3 | Complete | 2026-03-30 |
| 7. Live Pipeline and Database | v2.0 | 3/3 | Complete | 2026-03-30 |
| 8. API and Dashboard | v2.0 | 3/3 | Complete | 2026-03-30 |
| 9. Infrastructure and Go-Live | v2.0 | 0/? | Not started | - |
