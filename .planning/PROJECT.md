# MLB Win Probability Model

## What This Is

A pre-game MLB win probability forecasting system that predicts game outcomes day-of (with confirmed starting pitchers), evaluates model calibration against Kalshi prediction market prices using Brier score, and benchmarks three model approaches — logistic regression, random forest, and XGBoost — against each other and against Kalshi market implied probabilities. Built as a 12-notebook Jupyter pipeline covering data ingestion, feature engineering, walk-forward backtesting, and Kalshi edge analysis.

**Shipped v1.0** (2026-03-29): full pipeline from raw ingestion to fee-adjusted edge identification.

## Core Value

Produce well-calibrated win probability estimates that can be rigorously compared against Kalshi market prices, surfacing where models agree, disagree, and where edges may exist.

## Current Milestone: v2.0 — Live Platform

**Goal:** Integrate starting pitcher features into all three models and deploy a live prediction dashboard with twice-daily pipeline, Kalshi edge display, and browser change notifications.

**Target features:**
- Track 1: SP feature matrix (ERA, FIP, xFIP, K/BB, workload, splits) + full model retrain (2015–2024)
- Track 2: Live dashboard at mlbforecaster.silverreyes.net (React + FastAPI + Postgres + Docker, dark/amber aesthetic)
- Twice-daily pipeline — pre-lineup (10am ET, team-only) + post-lineup (1pm ET, with pitcher features)
- Portfolio page at silverreyes.net/mlb-winforecaster (Astro SSR integration)
- Kalshi edge comparison and browser change notifications on dashboard

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
- ✓ 2025 Brier score benchmark: each model vs Kalshi market implied prob on same games (partial benchmark, labeled separately) — v1.0
- ✓ Edge analysis: |model_prob - kalshi_open_price| > configurable threshold → BUY_YES/BUY_NO signal — v1.0
- ✓ Fee-adjusted P&L: KALSHI_FEE_RATE=0.07 on profits only; no edge reported without fee adjustment — v1.0

### Active (v2.0)

**Track 1 — Pitcher Features & Model Retrain**
- [ ] **SP-01**: Historical SP stats acquired for 2015–2024 (ERA, FIP, xFIP, K%, BB%, WHIP, home/away splits) — data source TBD (pybaseball reliability is an open investigation)
- [ ] **SP-02**: SP feature matrix integrated into FeatureBuilder and feature store (one row per game, both teams' starters)
- [ ] **SP-03**: All three models (LR, RF, XGBoost) retrained with SP features; walk-forward backtest regenerated
- [ ] **SP-04**: ADVF-07 fixed — xwOBA column pipeline corrected (est_woba, last_name,first_name join)

**Track 2 — Live Dashboard & Deployment**
- [ ] **PIPE-01**: Daily prediction pipeline runs twice daily (10am ET pre-lineup, team-only; 1pm ET post-lineup, with SP features)
- [ ] **PIPE-02**: Pipeline stores both prediction versions per game in Postgres with timestamps
- [ ] **PIPE-03**: SP uncertainty handled gracefully — fallback to team-only prediction with uncertainty flag when starters unconfirmed or scratched
- [ ] **DASH-01**: Live dashboard at mlbforecaster.silverreyes.net — React frontend, dark cinematic + amber aesthetic
- [ ] **DASH-02**: Dashboard displays today's games with pre-lineup and post-lineup prediction versions side-by-side
- [ ] **DASH-03**: Kalshi live price comparison and edge signal displayed per game
- [ ] **DASH-04**: Browser change notifications — client-side timestamp polling, no push/email
- [ ] **INFRA-01**: Docker Compose stack deployed on Hostinger KVM 2 (FastAPI + worker + Postgres on port 8082)
- [ ] **INFRA-02**: Host Nginx reverse proxy config for mlbforecaster.silverreyes.net + Certbot SSL cert
- [ ] **PORT-01**: Portfolio page at silverreyes.net/mlb-winforecaster integrated into Astro SSR site

### Out of Scope

| Feature | Reason |
|---------|--------|
| In-game / live win probability | Pre-game only; real-time mid-game state is a different problem domain |
| Player prop markets | Game outcome (win/loss) only; props require per-player modeling |
| Automated trade execution on Kalshi | Analysis tool only; no order placement |
| Mobile or web dashboard | Jupyter notebooks are the interface; dashboards deferred indefinitely |
| TensorFlow / PyTorch | Overkill for ~12K-row tabular game data; scikit-learn/XGBoost sufficient |
| Individual batter-vs-pitcher matchups | Sample sizes too small; documented overfitting trap in MLB prediction literature |

## Context

**Current state (v1.0):**
- ~40,800 Python LOC across `src/` (data loaders, feature builder, models, edge analysis)
- 12 Jupyter notebooks (01–12) covering full pipeline end-to-end
- 120 passing tests
- Primary backtest: 2015–2024 (pybaseball data, walk-forward)
- Secondary/Kalshi track: 2025 season only (Kalshi coverage from 2025-04-16 onward)
- Two-track evaluation enforced throughout — never conflated

**Tech stack:** Python 3.x · pandas 2.2.x (pinned; pybaseball incompatible with 3.0) · pyarrow · pybaseball · statsapi · scikit-learn 1.8 · XGBoost 2.x · requests · Jupyter

**Known issues / tech debt:**
- xwOBA column excluded from all feature sets (100% NaN) — two bugs in `_add_advanced_features()`: pybaseball statcast returns `'last_name, first_name'` as a merged column, and xwOBA column name is `'est_woba'` not `'xwoba'`; fix deferred to v2 (ADVF-07)
- Kalshi comparison limited to 2025 season (data available from 2025-04-16); live prediction pipeline requires v2 daily runner

## Constraints

- **Data**: Kalshi historical market data only available from 2025-04-16 onward. Primary backtest (2015–2024) uses pybaseball only; Kalshi comparison is a separate secondary track.
- **Timing**: Predictions require confirmed starting pitchers (posted same-day, sometimes changed late)
- **Tech Stack**: Python-based — pandas 2.2.x pinned due to pybaseball/PyArrow string dtype incompatibility with pandas 3.0
- **Scope**: Pre-game prediction only; no in-game state modeling

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Day-of prediction window | Starting pitcher is the single largest pre-game predictor; waiting for confirmation maximizes signal | ✓ Good — confirmed in backtest |
| Three-model comparison (LR, RF, XGBoost) | Spans complexity spectrum — interpretable baseline to ensemble to boosting | ✓ Good — clear Brier score differentiation |
| Brier score as primary metric | Proper scoring rule that penalizes miscalibration, directly comparable to market implied probs | ✓ Good — enables direct Kalshi comparison |
| Jupyter notebooks as interface | Exploratory first; dashboards can follow once models are validated | ✓ Good — 12-notebook pipeline works well |
| Walk-forward only (no random splits) | Temporal integrity — models must never train on future data | ✓ Good — no leakage, realistic evaluation |
| Pandas 2.2.x pin | pybaseball incompatible with PyArrow string dtypes in pandas 3.0 | ✓ Good — avoids silent data corruption |
| KXMLBGAME series (not KXMLB) | KXMLB is championship futures (30 markets); KXMLBGAME is per-game winners (4,474 markets) | ✓ Good — discovered via web UI URL inspection |
| Disable Kalshi historical endpoint | No server-side series_ticker filter → unbounded pagination across all categories (19+ min) | ✓ Good — live endpoint with series_ticker returns all 2025 MLB markets in seconds |
| Ticker-based team parsing | Both sides of a game share identical title text; team only unambiguous from ticker suffix | ✓ Good — home-YES dedup gives one row per game with correct home/away assignment |
| Candlestick API for opening prices | last_price_dollars is settlement closing price (look-ahead bias); candlestick period_interval=1440 gives daily open | ✓ Good — pre-game prices for valid edge analysis |
| IsotonicRegression (not CalibratedClassifierCV) | CalibratedClassifierCV(cv='prefit') deprecated in sklearn 1.8.0 | ✓ Good — direct calibration, no deprecation warnings |
| 2020 excluded as test year | 60-game COVID season; sample too small and era too different for valid fold | ✓ Good — excluded from FOLD_MAP, included in training data |
| xwOBA excluded from feature sets | 100% NaN due to column name mismatch in statcast loader; fix would create Phase 3/4 inconsistency | ⚠ Revisit — ADVF-07 for v2 |
| BRef game logs replaced with MLB Stats API | BRef now returns HTTP 403 (Cloudflare JS-challenge) for pybaseball scraper | ✓ Good — statsapi is official, reliable, faster |
| Two-track evaluation language | 2025 Kalshi comparison is a partial benchmark (limited data), not a full backtest replacement | ✓ Good — "partial benchmark" framing prevents misleading comparisons |
| Fee-on-profits-only formula | Kalshi charges 7% fee on winning trades, not on the stake; losses are full stake with no fee | ✓ Good — accurately reflects Kalshi fee structure |

---
*Last updated: 2026-03-29 — v2.0 milestone started*
