# Roadmap: MLB Win Probability Model

## Overview

This roadmap delivers a pre-game MLB win probability forecasting system through four phases that follow the data pipeline's natural dependency chain. Phase 1 establishes the data foundation by ingesting historical game data, pitcher/team statistics, and Kalshi market prices into a local Parquet cache. Phase 2 transforms raw data into a temporally-safe feature matrix with strict look-ahead leakage prevention. Phase 3 trains three model types (logistic regression, random forest, XGBoost), evaluates them via walk-forward backtesting, and produces calibration and Brier score analysis. Phase 4 integrates Kalshi implied probabilities as an independent benchmark, enabling model-vs-market comparison and fee-adjusted edge analysis.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Data Ingestion and Raw Cache** - Fetch MLB schedules, historical stats, Statcast metrics, and Kalshi prices into local Parquet storage
- [ ] **Phase 2: Feature Engineering and Feature Store** - Build temporally-safe differential features from raw data into a single game-level feature matrix
- [ ] **Phase 3: Model Training and Backtesting** - Train three calibrated models and evaluate via walk-forward backtesting with Brier score and calibration analysis
- [ ] **Phase 4: Kalshi Market Comparison and Edge Analysis** - Benchmark model predictions against Kalshi implied probabilities and identify fee-adjusted edges

## Phase Details

### Phase 1: Data Ingestion and Raw Cache
**Goal**: User can retrieve all raw data sources needed for the forecasting system, stored locally so development never re-scrapes
**Depends on**: Nothing (first phase)
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06
**Pre-flight**: DATA-06 (Kalshi historical ingestion) depends on Kalshi having sufficient resolved MLB game-winner markets. Manually verify via the Kalshi API that historical MLB game-winner contracts exist at adequate volume before Phase 1 begins. If coverage is thin, scope or defer DATA-06 before building the ingestion module around it.
**Success Criteria** (what must be TRUE):
  1. User can run a notebook cell to fetch the current MLB schedule with confirmed starting pitchers for any given date
  2. User can run a notebook cell to retrieve historical team batting stats (wOBA, OPS, OBP, SLG) and starting pitcher stats (FIP, xFIP, K%, BB%, WHIP) for any season in the backtest window
  3. User can run a notebook cell to retrieve Statcast metrics (xwOBA, pitch velocity, whiff rate) for any season in the backtest window
  4. User can run a notebook cell to fetch historical resolved Kalshi MLB game-winner market prices
  5. All fetched data persists as local Parquet files -- re-running any ingestion notebook loads from cache instead of re-scraping
  6. Raw cache contains complete season data for 2015 through 2024 with coverage validated across all data sources (game results, confirmed starters, team batting stats, SP stats, Statcast metrics)
**Plans**: TBD

Plans:
- [ ] 01-01: TBD
- [ ] 01-02: TBD

### Phase 2: Feature Engineering and Feature Store
**Goal**: User has a single, trusted feature matrix where every game is one row with all differential features, outcome label, and Kalshi implied probability -- with verified temporal safety
**Depends on**: Phase 1
**Requirements**: FEAT-01, FEAT-02, FEAT-03, FEAT-04, FEAT-05, FEAT-06, FEAT-07, FEAT-08
**Success Criteria** (what must be TRUE):
  1. User can generate a feature matrix Parquet file containing one row per historical game with all differential features (SP, offense, bullpen, park, rolling form, advanced), outcome label, and Kalshi implied probability where available
  2. User can inspect the FeatureBuilder and confirm that all rolling features use `shift(1)` and accept an `as_of_date` parameter, preventing look-ahead leakage
  3. Unit tests exist that verify removing a game's outcome does not change that game's feature values (leakage detection)
  4. User can run a feature exploration notebook showing feature distributions, correlations, and coverage across seasons
**Plans**: TBD

Plans:
- [ ] 02-01: TBD
- [ ] 02-02: TBD

### Phase 3: Model Training and Backtesting
**Goal**: User can compare three trained, calibrated models on Brier score and calibration quality across multiple seasons of walk-forward backtesting
**Depends on**: Phase 2
**Requirements**: MODEL-01, MODEL-02, MODEL-03, MODEL-04, EVAL-01, EVAL-02, EVAL-03, EVAL-04
**Success Criteria** (what must be TRUE):
  1. User can train logistic regression, random forest, and XGBoost models on the feature matrix and obtain probability-calibrated outputs from all three
  2. User can view walk-forward backtest results (train on seasons 1..N, predict season N+1) for each model -- no random splits used anywhere
  3. User can view per-model, per-season, and aggregate Brier scores in a comparison notebook
  4. User can view calibration curves (reliability diagrams) for each model showing where they are over- or underconfident
  5. User can view a side-by-side model comparison notebook presenting LR vs RF vs XGBoost on Brier score, calibration, and per-season accuracy
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD

### Phase 4: Kalshi Market Comparison and Edge Analysis
**Goal**: User can evaluate whether any model outperforms Kalshi market prices on calibration, and identify specific games where meaningful model-vs-market edges exist after fees
**Depends on**: Phase 3
**Requirements**: MARKET-01, MARKET-02, MARKET-03, MARKET-04
**Success Criteria** (what must be TRUE):
  1. User can view the feature matrix with Kalshi historical implied probabilities joined for all games where Kalshi data is available within the backtest window
  2. User can compare each model's Brier score against the Kalshi implied probability Brier score on the same subset of games
  3. User can view an edge analysis identifying individual games where model probability diverges from Kalshi opening price by a meaningful margin
  4. User can view profitability analysis with Kalshi fee structure applied -- no edge is reported without fee adjustment
**Plans**: TBD

Plans:
- [ ] 04-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Data Ingestion and Raw Cache | 0/TBD | Not started | - |
| 2. Feature Engineering and Feature Store | 0/TBD | Not started | - |
| 3. Model Training and Backtesting | 0/TBD | Not started | - |
| 4. Kalshi Market Comparison and Edge Analysis | 0/TBD | Not started | - |
