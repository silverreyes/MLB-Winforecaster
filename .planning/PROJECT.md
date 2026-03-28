# MLB Win Probability Model

## What This Is

A pre-game MLB win probability forecasting system that predicts game outcomes day-of (with starting pitchers known), evaluates model calibration against Kalshi prediction market prices using Brier score, and benchmarks three model approaches — logistic regression, random forest, and gradient boosting — against each other. Built in Jupyter notebooks, with both a historical backtesting framework and a live pipeline for current-season predictions.

## Core Value

Produce well-calibrated win probability estimates that can be rigorously compared against Kalshi market prices, surfacing where models agree, disagree, and where edges may exist.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Fetch game schedules and starting pitcher assignments from MLB Stats API
- [ ] Ingest historical game data from Baseball Reference / Retrosheet
- [ ] Ingest Statcast / Baseball Savant metrics via pybaseball
- [ ] Pull Kalshi market prices via Kalshi API (historical and live)
- [ ] Engineer features: starting pitcher stats (ERA, FIP, xFIP, K%, recent form)
- [ ] Engineer features: team offense metrics (wOBA, OPS, run differential, recent scoring)
- [ ] Engineer features: bullpen depth and usage (ERA, days of rest, heavy usage flags)
- [ ] Engineer features: home/away indicator and ballpark run factors
- [ ] Train and evaluate logistic regression model
- [ ] Train and evaluate random forest model
- [ ] Train and evaluate gradient boosting model (XGBoost or LightGBM)
- [ ] Backtest all models on 3–5 seasons of historical data
- [ ] Compute Brier scores per model and compare against Kalshi implied probabilities
- [ ] Build live prediction pipeline: pull today's schedule → output game probabilities
- [ ] Notebook-based reporting: model comparison, calibration curves, Brier score breakdowns

### Out of Scope

- In-game / live win probability (mid-game state) — pre-game only
- Player prop markets — game outcome only
- Automated trade execution on Kalshi — analysis tool, not a bot
- Mobile or web dashboard — Jupyter notebooks are the interface

## Context

- Data sources: MLB Stats API (schedules, rosters, starters), pybaseball/Baseball Savant (Statcast), Baseball Reference/Retrosheet (historical game logs), Kalshi API (prediction market prices)
- Prediction timing: day-of, after starting pitchers are confirmed — the most actionable pre-game window
- Evaluation metric: Brier score (lower = better calibrated) compared across models and vs. Kalshi market implied probabilities
- Dual purpose: rigorous analytical research into MLB outcome predictability, with potential to inform real position-taking on Kalshi
- Output environment: Jupyter notebooks for exploratory analysis, visualization, and model comparison

## Constraints

- **Data**: Kalshi historical market data availability may be limited — scope of backtest depends on how far back Kalshi data goes
- **Timing**: Predictions require confirmed starting pitchers, which are sometimes posted late or changed
- **Tech Stack**: Python-based (pandas, scikit-learn, XGBoost/LightGBM, pybaseball, Jupyter)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Day-of prediction window | Starting pitcher is the single largest pre-game predictor; waiting for confirmation maximizes signal | — Pending |
| Three-model comparison (LR, RF, GBM) | Spans complexity spectrum — interpretable baseline to ensemble to boosting | — Pending |
| Brier score as primary metric | Proper scoring rule that penalizes miscalibration, directly comparable to market implied probs | — Pending |
| Jupyter notebooks as interface | Exploratory first; dashboards can follow once models are validated | — Pending |

---
*Last updated: 2026-03-28 after initialization*
