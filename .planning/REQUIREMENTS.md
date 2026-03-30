# Requirements: MLB Win Probability Model

**Defined:** 2026-03-29
**Milestone:** v2.0 — Live Platform
**Core Value:** Produce well-calibrated win probability estimates that can be rigorously compared against Kalshi market prices, surfacing where models agree, disagree, and where edges may exist.

## v2.0 Requirements

### SP Feature Engineering (Track 1)

- [x] **SP-01**: FeatureBuilder fixes two bugs in `_add_advanced_features()`: (1) pybaseball statcast returns `'last_name, first_name'` as a single merged column — the join must split on `", "` and reverse to "First Last"; (2) xwOBA column in Baseball Savant output is `'est_woba'` not `'xwoba'`. Both bugs caused 100% NaN for `xwoba_diff` in v1.
- [x] **SP-02**: System builds `mlb_player_id → fangraphs_id` cross-reference (via pybaseball `playerid_lookup()` or Chadwick Bureau register) for ID-based SP name matching; eliminates ~17% NaN rate from MLB Stats API vs FanGraphs name format mismatches.
- [x] **SP-03**: FeatureBuilder converts all season-aggregate SP stats to season-to-date rolling (cumsum + shift(1) per pitcher per season); v1 used full-season FanGraphs totals as game-level features, meaning a June game saw September stats — temporal leakage that must be eliminated before any retraining.
- [x] **SP-04**: FeatureBuilder computes `sp_k_bb_pct_diff` (K-BB% differential) and removes `sp_k_pct_diff`; K-BB% explains 17.92% of future RA9 variance vs under 10% for K% alone.
- [x] **SP-05**: FeatureBuilder computes `sp_whip_diff` differential; WHIP provides independent signal from the FIP family.
- [x] **SP-06**: FeatureBuilder computes `sp_era_diff` (season-to-date ERA differential, sourced from per-game rolling after SP-03 conversion).
- [x] **SP-07**: FeatureBuilder computes `sp_recent_fip_diff` (30-day rolling FIP from MLB Stats API game logs; K/BB/HR/IP per start aggregated over trailing 30 calendar days with shift(1)).
- [x] **SP-08**: FeatureBuilder computes `sp_pitch_count_last_diff` (pitch count in SP's most recent start; impute NaN first start with league-average 93 pitches) and `sp_days_rest_diff` (integer days rest, capped at 7).
- [x] **SP-09**: `feature_sets.py` defines three named constants: `TEAM_ONLY_FEATURE_COLS` (pre-lineup feature set, team stats only), `SP_ENHANCED_FEATURE_COLS` (full set including all new SP columns), and `V1_FULL_FEATURE_COLS` (v1 feature set preserved for apples-to-apples backtest comparison).
- [x] **SP-10**: FeatureBuilder handles SP cold-start: uses previous-season aggregate stats as prior for first start of season; imputes league-average values for rookies and mid-season call-ups.
- [x] **SP-11**: Feature store saved as `feature_store_v2.parquet` (versioned separately from `feature_store_v1.parquet`; v1 file preserved unchanged).
- [x] **SP-12**: Temporal safety test suite extended to all new SP columns; each column must change game-to-game within a season per pitcher (no constant values that would indicate a season-level lookup instead of a rolling one).

### Model Retrain & Calibration (Track 1)

- [ ] **MDL-01**: Six model artifacts trained: LR/RF/XGBoost × TEAM\_ONLY\_FEATURE\_COLS/SP\_ENHANCED\_FEATURE\_COLS via walk-forward backtest on 2015–2024 data (same FOLD\_MAP as v1, 2020 excluded as test year).
- [ ] **MDL-02**: All 6 models calibrated using `IsotonicRegression` directly (the settled v1 approach after `CalibratedClassifierCV(cv='prefit')` was deprecated in sklearn 1.8.0). Temperature scaling evaluated as an alternative only if reliability diagrams show poor calibration on small folds (e.g., the 2020 fold with ~891 games).
- [ ] **MDL-03**: Brier score comparison table generated: v2 SP_ENHANCED vs v2 TEAM_ONLY vs v1 vs Kalshi market, on identical 2025 out-of-sample games.
- [ ] **MDL-04**: Reliability diagrams (calibration curves) generated and visually inspected for all 6 model/feature-set combinations before declaring any model production-ready.
- [x] **MDL-05**: VIF analysis run on the expanded SP feature set; features with VIF > 10 dropped before final model training.
- [x] **MDL-06**: SHAP `TreeExplainer` feature importance ranking computed for XGBoost models; features with near-zero gain removed before final models.
- [ ] **MDL-07**: All 6 model artifacts persisted as joblib files in `models/artifacts/`; `model_metadata.json` records training date, feature column list, fold Brier scores, and calibration method used.

### Live Pipeline & Database (Track 2)

- [ ] **PIPE-01**: Postgres schema created: `games` table (one row per MLB game), `predictions` table (one row per game per version with `is_latest` flag), `pipeline_runs` audit table; appropriate indexes on `game_date`, `is_latest`, and `(game_date, prediction_version)`.
- [ ] **PIPE-02**: Pre-lineup pipeline runs at 10am ET daily using `TEAM_ONLY_FEATURE_COLS`; SP fields stored as null/unconfirmed; `prediction_version = 'pre_lineup'`.
- [ ] **PIPE-03**: Post-lineup pipeline runs at 1pm ET daily using `SP_ENHANCED_FEATURE_COLS` with confirmed starting pitcher names; `prediction_version = 'post_lineup'`.
- [ ] **PIPE-04**: Confirmation pipeline runs at 5pm ET daily; re-fetches current SP assignments; if starter differs from 1pm prediction, marks old row `is_latest = FALSE`, inserts updated row, and sets `sp_may_have_changed = TRUE` on the new row.
- [ ] **PIPE-05**: Kalshi live opening price fetched and `edge_signal` (BUY_YES/BUY_NO/NO_EDGE) computed at insert time per prediction row; stored in `predictions` table (not computed at query time).
- [ ] **PIPE-06**: SP name stored in each `predictions` row; `sp_may_have_changed` boolean flag set by 5pm confirmation run when starter differs from 1pm run.
- [ ] **PIPE-07**: Pipeline falls back to `TEAM_ONLY_FEATURE_COLS` with `sp_uncertainty = TRUE` flag when starters are TBD or unresolvable at run time; does not insert a `post_lineup` prediction until starters are confirmed. The `predictions` table schema enforces this at the database level — either a `prediction_status` enum (`confirmed`, `pending_sp`, `tbd`) with a CHECK constraint, or a nullable `sp_confirmed_at` timestamp — so the invariant cannot be violated by application-level bugs.
- [ ] **PIPE-08**: All pipeline runs log to a persistent file; `GET /api/v1/health` returns `last_pipeline_run` timestamp and run status for each version.

### API Layer (Track 2)

- [ ] **API-01**: `GET /api/v1/predictions/today` — returns all games for current date with both prediction versions (pre and post lineup where available), model probabilities (LR/RF/XGB), Kalshi price, edge signal, SP names, and staleness flags.
- [ ] **API-02**: `GET /api/v1/predictions/{date}` — same shape as today endpoint; returns historical predictions for a given date.
- [ ] **API-03**: `GET /api/v1/predictions/latest-timestamp` — lightweight endpoint returning only the most recent `created_at` timestamp; used by client-side polling to detect new predictions without fetching full payload.
- [ ] **API-04**: `GET /api/v1/results/accuracy` — historical Brier scores and model accuracy metrics aggregated by date range.
- [ ] **API-05**: `GET /api/v1/health` — returns pipeline status, `last_pipeline_run` per version, and service uptime.
- [ ] **API-06**: All 6 model artifacts loaded at FastAPI startup via lifespan context manager; no model loading occurs inside request handlers; API fails to start (not silently) if any artifact is missing.

### Dashboard Frontend (Track 2)

- [ ] **DASH-01**: React 19 + Vite 8 dashboard at `mlbforecaster.silverreyes.net` with dark cinematic + amber aesthetic — near-black background, high-contrast typography, amber highlights for probabilities and edge values; design produced using the frontend-design skill before Phase 4 planning begins.
- [ ] **DASH-02**: Today's games displayed with pre-lineup and post-lineup prediction versions side-by-side; LR/RF/XGB probabilities shown per version; visual distinction between confirmed and TBD lineup states.
- [ ] **DASH-03**: Kalshi live price and edge signal (BUY_YES/BUY_NO/NO_EDGE) displayed per game with fee-adjusted framing consistent with v1.
- [ ] **DASH-04**: SP confirmation status per game — confirmed starter name shown; "TBD" flagged visually; `sp_may_have_changed` flag surfaced as a warning indicator.
- [ ] **DASH-05**: "Last updated: [timestamp]" shown prominently on the page; prediction cards grayed out with a staleness indicator when the most recent prediction is older than 3 hours.
- [ ] **DASH-06**: Client-side timestamp polling implemented with `document.visibilityState` check — polling fires every 60 seconds when `document.visibilityState === 'visible'` and is suspended on `visibilitychange` to `'hidden'`; resumes on `visibilitychange` back to `'visible'`; shows a "New predictions available — refresh" banner when the polled timestamp is newer than the currently displayed data.
- [ ] **DASH-07**: Explicit error state rendered when the API is unreachable — not a blank page, not an infinite spinner; shows last-known data with a "Dashboard offline" indicator and timestamp of last successful fetch.

### Infrastructure & Deployment (Track 2)

- [ ] **INFRA-01**: Docker Compose stack (services: `api`, `worker`, `db`) deployed on port 8082; explicit memory limits set in `docker-compose.yml` before first VPS deploy (`api: 512M`, `worker: 1G`, `db: 512M`); before deploying, audit GamePredictor container memory consumption via `docker stats --no-stream` to confirm remaining headroom is sufficient (shared VPS: 8GB total, Ghost CMS + GamePredictor + OS baseline already consuming ~2.4GB).
- [ ] **INFRA-02**: Host Nginx server block for `mlbforecaster.silverreyes.net` proxying to port 8082; config validated with `nginx -t` and tested in a staging pass before `nginx -s reload` on production.
- [ ] **INFRA-03**: Certbot SSL certificate issued for `mlbforecaster.silverreyes.net`; renewal dry-run tested (`certbot renew --dry-run`) before go-live.
- [ ] **INFRA-04**: Postgres data in a named Docker volume (`mlb_pgdata`); volume persistence verified by stop/start cycle before go-live; daily `pg_dump` backup cron to `/opt/backups/mlb/` with 7-day retention.

### Portfolio Page (Track 2)

- [ ] **PORT-01**: Static Astro page at `silverreyes.net/mlb-winforecaster` — methodology overview, Brier score comparison table (v1 vs v2 TEAM\_ONLY vs v2 SP\_ENHANCED vs Kalshi), calibration curve images, link to live dashboard at `mlbforecaster.silverreyes.net`; no backend API calls from the portfolio page.

---

## v3 Requirements

Deferred to future milestones. Not in current roadmap.

### Advanced Features

- **ADVF-02**: Weather features (temperature, wind direction/speed) as predictors
- **ADVF-03**: Bullpen fatigue tracking (per-pitcher game log; flags heavy usage in prior 2 days)
- **ADVF-04**: Travel distance penalty (distance traveled for away team in prior 24 hours)
- **ADVF-05**: Elo rating system for team strength tracking (updated after each game)
- **ADVF-06**: Steamer/ZiPS projection blending for early-season predictions
- **SP-H/A**: Home/away SP splits per pitcher — sample size insufficient for v2 (BABIP needs 2000 BIP to stabilize; single-season H/A provides ~200-250 BIP per split)
- **SP-xERA**: xERA from Statcast — redundant with xwOBA; same batted-ball signal

### Dashboard Extensions

- **DASH-HIST**: Full historical results browser with prediction accuracy over time
- **DASH-HOT**: Model hot-reload without API container restart
- **DASH-MONITOR**: Pipeline failure email/webhook alert (UptimeRobot or equivalent)

---

## Out of Scope

| Feature | Reason |
|---------|--------|
| In-game / live win probability | Pre-game only; mid-game state modeling is a separate problem domain |
| Player prop markets | Game outcome (win/loss) only; props require per-player modeling |
| Automated trade execution on Kalshi | Analysis tool only; no order placement |
| Batter vs pitcher matchup features | Confirmed anti-feature — pure noise at typical career PA sample sizes |
| WebSocket / push notifications | Client-side timestamp polling is sufficient; no infrastructure overhead |
| LightGBM as a primary model | scikit-learn/XGBoost sufficient for tabular game data; LightGBM benchmarking only |
| TensorFlow / PyTorch | Overkill for ~12K-row tabular data |
| Streamlit / Dash frontend | React only; aesthetic requirement rules out generic data-tool frameworks |
| Pandas 3.0 migration | pybaseball incompatible with PyArrow string dtypes; hard pin at 2.2.x |

---

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SP-01 | Phase 5 | Complete |
| SP-02 | Phase 5 | Complete |
| SP-03 | Phase 5 | Complete |
| SP-04 | Phase 5 | Complete |
| SP-05 | Phase 5 | Complete |
| SP-06 | Phase 5 | Complete |
| SP-07 | Phase 5 | Complete |
| SP-08 | Phase 5 | Complete |
| SP-09 | Phase 5 | Complete |
| SP-10 | Phase 5 | Complete |
| SP-11 | Phase 5 | Complete |
| SP-12 | Phase 5 | Complete |
| MDL-01 | Phase 6 | Pending |
| MDL-02 | Phase 6 | Pending |
| MDL-03 | Phase 6 | Pending |
| MDL-04 | Phase 6 | Pending |
| MDL-05 | Phase 6 | Complete |
| MDL-06 | Phase 6 | Complete |
| MDL-07 | Phase 6 | Pending |
| PIPE-01 | Phase 7 | Pending |
| PIPE-02 | Phase 7 | Pending |
| PIPE-03 | Phase 7 | Pending |
| PIPE-04 | Phase 7 | Pending |
| PIPE-05 | Phase 7 | Pending |
| PIPE-06 | Phase 7 | Pending |
| PIPE-07 | Phase 7 | Pending |
| PIPE-08 | Phase 7 | Pending |
| API-01 | Phase 8 | Pending |
| API-02 | Phase 8 | Pending |
| API-03 | Phase 8 | Pending |
| API-04 | Phase 8 | Pending |
| API-05 | Phase 8 | Pending |
| API-06 | Phase 8 | Pending |
| DASH-01 | Phase 8 | Pending |
| DASH-02 | Phase 8 | Pending |
| DASH-03 | Phase 8 | Pending |
| DASH-04 | Phase 8 | Pending |
| DASH-05 | Phase 8 | Pending |
| DASH-06 | Phase 8 | Pending |
| DASH-07 | Phase 8 | Pending |
| INFRA-01 | Phase 9 | Pending |
| INFRA-02 | Phase 9 | Pending |
| INFRA-03 | Phase 9 | Pending |
| INFRA-04 | Phase 9 | Pending |
| PORT-01 | Phase 9 | Pending |

**Coverage:**
- v2.0 requirements: 45 total
- Mapped to phases: 45/45
- Unmapped: 0

---
*Requirements defined: 2026-03-29*
*Last updated: 2026-03-29 -- roadmap phase mappings applied*
