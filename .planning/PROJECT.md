# MLB Win Probability Model

## What This Is

A live MLB win probability forecasting platform that predicts game outcomes day-of (pre-lineup at 10am ET with team stats, post-lineup at 1pm ET with confirmed starting pitcher features), evaluates three model approaches (logistic regression, random forest, XGBoost) against Kalshi prediction market prices using Brier score, and surfaces edge signals (BUY_YES/BUY_NO) on a real-time dashboard. Deployed at mlbforecaster.silverreyes.net with a three-run daily pipeline, Postgres persistence, and client-side polling.

**Shipped v1.0** (2026-03-29): full Jupyter pipeline from raw ingestion to fee-adjusted edge identification.
**Shipped v2.0** (2026-03-30): live prediction dashboard, SP-enhanced models, daily automated pipeline.

## Core Value

Produce well-calibrated win probability estimates that can be rigorously compared against Kalshi market prices, surfacing where models agree, disagree, and where edges may exist.

## Requirements

### Validated

- ✓ Fetch game schedules and starting pitcher assignments from MLB Stats API — v1.0
- ✓ Ingest historical team batting statistics (wOBA, OPS, OBP, SLG) via pybaseball/FanGraphs — v1.0
- ✓ Ingest historical SP statistics (FIP, xFIP, K%, BB%, WHIP) via pybaseball/FanGraphs — v1.0
- ✓ Ingest Statcast metrics (xwOBA, pitch velocity, whiff rate) via pybaseball/Baseball Savant — v1.0
- ✓ Cache all raw data locally as Parquet files (no repeated scraping) — v1.0
- ✓ Fetch Kalshi settled game-winner market prices (KXMLBGAME, 2025 season, ticker-parsed) — v1.0
- ✓ FeatureBuilder: SP differential (FIP, xFIP, K%, 30-day ERA), offense differential (wOBA, OPS, Pythagorean), rolling 10-game OPS, bullpen ERA, park factors, Log5, advanced — v1.0
- ✓ Temporal safety: all rolling features use shift(1), leakage tests confirm no look-ahead — v1.0
- ✓ Feature store: single Parquet file, one row per game, all features + outcome label + Kalshi implied prob — v1.0
- ✓ Train and calibrate LR, RF, XGBoost with isotonic regression per fold — v1.0
- ✓ Walk-forward backtest (train 1..N, predict N+1; no random splits; 2020 excluded as test year) — v1.0
- ✓ Brier scores per model, per season, and aggregate — v1.0
- ✓ Calibration curves (reliability diagrams) per model — v1.0
- ✓ Model comparison notebook: LR vs RF vs XGBoost side-by-side — v1.0
- ✓ Kalshi opening prices via candlestick API (pre-game, not settlement); fallback to NaN where unavailable — v1.0
- ✓ 2025 Brier score benchmark: each model vs Kalshi market implied prob on same games — v1.0
- ✓ Edge analysis: |model_prob - kalshi_open_price| > configurable threshold → BUY_YES/BUY_NO signal — v1.0
- ✓ Fee-adjusted P&L: KALSHI_FEE_RATE=0.07 on profits only; no edge reported without fee adjustment — v1.0
- ✓ xwOBA column fixed (est_woba + last_name,first_name join) and included in SP_ENHANCED feature set — v2.0
- ✓ MLB→FanGraphs ID bridge (Chadwick Register) for SP name resolution; 5-tier matching chain — v2.0
- ✓ SP stats converted to season-to-date rolling (cumsum+shift(1)); full temporal safety on all new SP columns — v2.0
- ✓ 8 new SP differential features: sp_k_bb_pct_diff, sp_whip_diff, sp_era_diff, sp_recent_fip_diff, sp_pitch_count_last_diff, sp_days_rest_diff, sp_xfip_diff (all temporally safe) — v2.0
- ✓ SP cold-start cascade: rolling → prev-season FanGraphs → league-average constants — v2.0
- ✓ Three named feature set constants: TEAM_ONLY_FEATURE_COLS (9), SP_ENHANCED_PRUNED_COLS (17), V1_FULL_FEATURE_COLS (14) — v2.0
- ✓ VIF pruning (is_home, team_woba_diff, sp_siera_diff removed); SHAP validation; 17-feature pruned SP_ENHANCED set — v2.0
- ✓ 6 model artifacts (LR/RF/XGB × TEAM_ONLY/SP_ENHANCED) trained, calibrated, and persisted as joblib — v2.0
- ✓ v2 SP_ENHANCED beats v2 TEAM_ONLY by 0.004–0.005 Brier; v2 RF SP_ENHANCED beats Kalshi market (0.2371 vs 0.2434) — v2.0
- ✓ Postgres schema with prediction_version/prediction_status ENUMs and CHECK constraints for PIPE-07 invariant — v2.0
- ✓ Three-run daily pipeline (10am/1pm/5pm ET) via APScheduler with Kalshi edge signal at insert time — v2.0
- ✓ LiveFeatureBuilder with NaN imputation for early-season missing data; OOM-resistant retry logic — v2.0
- ✓ FastAPI read layer with lifespan model loading, 5 prediction endpoints, health endpoint — v2.0
- ✓ React 19 + Vite dashboard: dark/amber aesthetic, pre/post-lineup side-by-side, SP confirmation status — v2.0
- ✓ Client-side polling (60s interval, visibilityState-gated) with new-predictions banner — v2.0
- ✓ Docker Compose stack (api 512M, worker 1536M, db 512M) on Hostinger KVM2 with Nginx + SSL — v2.0
- ✓ Daily pg_dump backups to /opt/backups/mlb/ with 7-day retention — v2.0

### Active

*(No active requirements — next milestone not yet defined. Run `/gsd:new-milestone` to begin.)*

### Out of Scope

| Feature | Reason |
|---------|--------|
| In-game / live win probability | Pre-game only; mid-game state modeling is a separate problem domain |
| Player prop markets | Game outcome (win/loss) only; props require per-player modeling |
| Automated trade execution on Kalshi | Analysis tool only; no order placement |
| Batter vs pitcher matchup features | Confirmed anti-feature — pure noise at typical career PA sample sizes |
| WebSocket / push notifications | Client-side timestamp polling is sufficient; no infrastructure overhead |
| LightGBM as a primary model | scikit-learn/XGBoost sufficient for tabular game data |
| TensorFlow / PyTorch | Overkill for ~12K-row tabular data |
| Streamlit / Dash frontend | React only; aesthetic requirement rules out generic data-tool frameworks |
| Pandas 3.0 migration | pybaseball incompatible with PyArrow string dtypes; hard pin at 2.2.x |
| Weather features (ADVF-02) | Deferred to v3+ |
| Bullpen fatigue tracking (ADVF-03) | Deferred to v3+ |
| Travel distance penalty (ADVF-04) | Deferred to v3+ |
| Elo rating system (ADVF-05) | Deferred to v3+ |

## Context

**Current state (v2.0 — shipped 2026-03-30):**
- ~5,322 Python LOC across `src/` (data loaders, feature builder, models, pipeline, API) + ~1,087 TypeScript/CSS
- 6 model artifacts: LR/RF/XGB × TEAM_ONLY/SP_ENHANCED, all joblib with IsotonicRegression calibrators
- Live dashboard at mlbforecaster.silverreyes.net — deployed Opening Day 2026
- Three-run daily pipeline (10am/1pm/5pm ET) automated via APScheduler in Docker worker
- 45 requirements shipped, all 16 v2.0 plans complete across 5 phases

**Tech stack:** Python 3.11 · pandas 2.2.x (pinned) · pyarrow · pybaseball · statsapi · scikit-learn · XGBoost · FastAPI · psycopg3 · psycopg_pool · APScheduler · React 19 · Vite · TypeScript · TanStack Query · Docker · Nginx · Postgres 16

**Known tech debt:**
- LiveFeatureBuilder calls FeatureBuilder private methods (_add_sp_features, _add_offense_features, etc.) — accepted coupling for v2; refactor to stable adapter if FeatureBuilder internals change
- Early-season NaN features (xwoba_diff, sp_recent_era/fip diffs) imputed to 0.0 in live predictions until game log data accumulates (~1 week into season)
- Kalshi comparison limited to 2025 season (data available from 2025-04-16); grows with each season

## Constraints

- **Data**: Kalshi historical market data only available from 2025-04-16 onward
- **Timing**: Predictions require confirmed starting pitchers (posted same-day, sometimes changed late)
- **Tech Stack**: pandas 2.2.x pinned due to pybaseball/PyArrow incompatibility with pandas 3.0
- **Scope**: Pre-game prediction only; no in-game state modeling
- **Memory**: Hostinger KVM2 (8GB shared) — worker capped at 1536M, api/db at 512M each

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Day-of prediction window | Starting pitcher is the single largest pre-game predictor; waiting for confirmation maximizes signal | ✓ Good — confirmed in backtest |
| Three-model comparison (LR, RF, XGBoost) | Spans complexity spectrum — interpretable baseline to ensemble to boosting | ✓ Good — clear Brier score differentiation |
| Brier score as primary metric | Proper scoring rule that penalizes miscalibration, directly comparable to market implied probs | ✓ Good — enables direct Kalshi comparison |
| Walk-forward only (no random splits) | Temporal integrity — models must never train on future data | ✓ Good — no leakage, realistic evaluation |
| Pandas 2.2.x pin | pybaseball incompatible with PyArrow string dtypes in pandas 3.0 | ✓ Good — avoids silent data corruption |
| KXMLBGAME series (not KXMLB) | KXMLB is championship futures; KXMLBGAME is per-game winners | ✓ Good — discovered via web UI URL inspection |
| Candlestick API for opening prices | last_price_dollars is settlement (look-ahead bias); candlestick period=1440 gives daily open | ✓ Good — pre-game prices for valid edge analysis |
| IsotonicRegression (not CalibratedClassifierCV) | CalibratedClassifierCV(cv='prefit') deprecated in sklearn 1.8.0 | ✓ Good — direct calibration, no deprecation warnings |
| 2020 excluded as test year | 60-game COVID season; sample too small and era too different | ✓ Good — excluded from FOLD_MAP, included in training |
| BRef game logs → MLB Stats API | BRef returns HTTP 403 (Cloudflare JS-challenge) for pybaseball scraper | ✓ Good — statsapi is official, reliable, faster |
| Fee-on-profits-only formula | Kalshi charges 7% fee on winning trades, not on the stake | ✓ Good — accurately reflects Kalshi fee structure |
| 5-tier SP name resolution | Exact → override → accent-strip → ID bridge → FG name lookup; eliminates ~17% NaN rate | ✓ Good — all Opening Day 2026 pitchers resolved |
| Chadwick Register for ID bridge | MLB ID → FanGraphs ID cross-reference; cached to avoid re-download | ✓ Good — reliable, pre-warmed in Dockerfile |
| cumsum+shift(1) for rolling SP stats | Temporally safe season-to-date rolling; prevents future-data leakage | ✓ Good — temporal safety tests pass |
| VIF pruning (is_home, team_woba_diff, sp_siera_diff) | VIF > 10 / constant → multicollinearity; drop before training | ✓ Good — 17-feature set, SHAP validated |
| SP_ENHANCED consistently beats TEAM_ONLY by 0.004–0.005 Brier | SP features add predictive signal beyond team-level stats | ✓ Good — justifies 1pm post-lineup run cost |
| psycopg3 (not psycopg2) | Async-ready, modern Python type support, connection pool | ✓ Good — simpler integration with FastAPI |
| UPSERT (ON CONFLICT DO UPDATE) | Re-run safety; idempotent pipeline runs | ✓ Good — no duplicate rows on retry |
| prediction_version/status ENUMs + CHECK constraint | DB-level invariant for PIPE-07 (no post_lineup without confirmed SP) | ✓ Good — cannot be bypassed by application bugs |
| Sync def handlers (not async) in FastAPI | psycopg3 sync connections block event loop if called from async | ✓ Good — runs in thread pool, correct behavior |
| NaN diff imputation with 0.0 in build_features_for_game | Early-season data missing; 0.0 = neutral prior (no differential advantage) | ✓ Good — prevents silent model skip on Opening Day |
| APScheduler BlockingScheduler (not BackgroundScheduler) | Simpler in container; no daemon thread complexity | ✓ Good — clean shutdown behavior |
| mem_limit (not deploy.resources) in docker-compose | Non-swarm Docker Compose compatibility | ✓ Good — works on single-host VPS |
| Model artifacts bind-mounted read-only | Artifacts not baked into image; updated without rebuild | ✓ Good — flexible for model updates |
| CSS custom properties for design tokens | Hex values never hard-coded in component CSS | ✓ Good — consistent theming |
| No retry button in ErrorState | React Query auto-recovers when API responds | ✓ Good — less UI complexity |

---
*Last updated: 2026-03-30 — v2.0 milestone complete*
