# Requirements: MLB Win Probability Model

**Defined:** 2026-03-28
**Core Value:** Produce well-calibrated win probability estimates that can be rigorously compared against Kalshi market prices, surfacing where models agree, disagree, and where edges may exist.

## v1 Requirements

Requirements for initial release. Each maps to a roadmap phase.

### Data Ingestion

- [ ] **DATA-01**: User can fetch MLB game schedules and confirmed starting pitcher assignments from MLB Stats API
- [ ] **DATA-02**: User can ingest historical team batting statistics (wOBA, OPS, OBP, SLG) from pybaseball / FanGraphs
- [ ] **DATA-03**: User can ingest historical starting pitcher statistics (FIP, xFIP, K%, BB%, WHIP) from pybaseball / FanGraphs
- [ ] **DATA-04**: User can ingest Statcast metrics (xwOBA, pitch velocity, whiff rate) from pybaseball / Baseball Savant
- [ ] **DATA-05**: All raw data is cached locally as Parquet files to prevent repeated scraping across development sessions
- [ ] **DATA-06**: User can fetch historical resolved MLB game-winner market prices from Kalshi API for backtesting evaluation

### Feature Engineering

- [ ] **FEAT-01**: FeatureBuilder computes starting pitcher differential (FIP, xFIP, K%) between confirmed home and away SPs
- [ ] **FEAT-02**: FeatureBuilder computes team offensive differential (wOBA, OPS, Pythagorean win percentage) between home and away teams
- [ ] **FEAT-03**: FeatureBuilder computes rolling 10-game team OPS differential to capture recent form
- [ ] **FEAT-04**: FeatureBuilder computes bullpen ERA differential between home and away bullpens
- [ ] **FEAT-05**: FeatureBuilder includes home/away indicator and 3-year rolling park run factor
- [ ] **FEAT-06**: FeatureBuilder computes differentiator features: SIERA differential, xwOBA differential, SP recent form (last 3 starts), Log5 win probability, bullpen FIP differential
- [ ] **FEAT-07**: All rolling features enforce temporal safety via `shift(1)` and `as_of_date` parameter; unit tests verify no look-ahead leakage
- [ ] **FEAT-08**: Feature store outputs a single Parquet file with one row per historical game (all features, outcome label, Kalshi implied probability where available)

### Modeling

- [ ] **MODEL-01**: Logistic regression model trains on the feature matrix as an interpretable baseline and calibration anchor
- [ ] **MODEL-02**: Random forest model trains on the feature matrix as an ensemble comparison benchmark
- [ ] **MODEL-03**: XGBoost gradient boosting model trains with aggressive regularization (max_depth 3-5, early stopping on temporal validation) to prevent overfitting on ~12K game dataset
- [ ] **MODEL-04**: All three models are probability-calibrated using temperature scaling via scikit-learn `CalibratedClassifierCV`

### Backtesting & Evaluation

- [ ] **EVAL-01**: All three models are evaluated via walk-forward backtesting (train on seasons 1..N, predict season N+1; no random splits)
- [ ] **EVAL-02**: Brier score is computed per model, per season, and in aggregate across all backtest seasons
- [ ] **EVAL-03**: Calibration curves (reliability diagrams) are generated per model to visualize over/underconfidence
- [ ] **EVAL-04**: Model comparison notebook presents LR vs RF vs XGBoost side-by-side on Brier score, calibration, and per-season accuracy

### Kalshi Market Integration

- [ ] **MARKET-01**: Kalshi historical resolved prices are joined to the feature matrix for all games within the backtesting window where Kalshi data is available, enabling model-vs-market comparison
- [ ] **MARKET-02**: Each model's Brier score is benchmarked against the Kalshi implied probability Brier score on the same games within the backtesting window
- [ ] **MARKET-03**: Edge analysis identifies individual games where model probability diverges from Kalshi opening price by a meaningful margin
- [ ] **MARKET-04**: Profitability analysis is fee-adjusted (Kalshi fee structure applied) before any model edge is reported

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Live Prediction Pipeline

- **LIVE-01**: Daily prediction notebook fetches today's schedule, builds features, and outputs win probabilities for all games
- **LIVE-02**: Daily notebook shows model probability vs current Kalshi live price side-by-side for today's games
- **LIVE-03**: Pipeline handles SP uncertainty gracefully (fallback logic when starters are TBD or scratched last-minute)

### Advanced Features

- **ADVF-01**: Cold-start blending applies regression-to-mean for early-season stats (prior season weighted with current season using FanGraphs stabilization points)
- **ADVF-02**: Weather features (temperature, wind direction/speed) integrated as additional predictors
- **ADVF-03**: Bullpen fatigue tracking (per-pitcher game log pipeline; flags heavy usage in prior 2 days)
- **ADVF-04**: Travel distance penalty feature (distance traveled for away team in prior 24 hours)
- **ADVF-05**: Elo rating system for team strength tracking (updated after each game outcome)
- **ADVF-06**: Steamer/ZiPS projection blending for early-season predictions before stats stabilize

## Out of Scope

| Feature | Reason |
|---------|--------|
| In-game / live win probability | Pre-game only; real-time mid-game state is a different problem domain |
| Player prop markets | Game outcome (win/loss) only; props require per-player modeling |
| Automated trade execution on Kalshi | Analysis tool only; no order placement |
| Mobile or web dashboard | Jupyter notebooks are the interface; dashboards deferred indefinitely |
| TensorFlow / PyTorch | Overkill for ~12K-row tabular game data; scikit-learn/XGBoost sufficient |
| Individual batter-vs-pitcher matchups | Sample sizes too small; documented overfitting trap in MLB prediction literature |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 1 | Pending |
| DATA-02 | Phase 1 | Pending |
| DATA-03 | Phase 1 | Pending |
| DATA-04 | Phase 1 | Pending |
| DATA-05 | Phase 1 | Pending |
| DATA-06 | Phase 1 | Pending |
| FEAT-01 | Phase 2 | Pending |
| FEAT-02 | Phase 2 | Pending |
| FEAT-03 | Phase 2 | Pending |
| FEAT-04 | Phase 2 | Pending |
| FEAT-05 | Phase 2 | Pending |
| FEAT-06 | Phase 2 | Pending |
| FEAT-07 | Phase 2 | Pending |
| FEAT-08 | Phase 2 | Pending |
| MODEL-01 | Phase 3 | Pending |
| MODEL-02 | Phase 3 | Pending |
| MODEL-03 | Phase 3 | Pending |
| MODEL-04 | Phase 3 | Pending |
| EVAL-01 | Phase 3 | Pending |
| EVAL-02 | Phase 3 | Pending |
| EVAL-03 | Phase 3 | Pending |
| EVAL-04 | Phase 3 | Pending |
| MARKET-01 | Phase 4 | Pending |
| MARKET-02 | Phase 4 | Pending |
| MARKET-03 | Phase 4 | Pending |
| MARKET-04 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 22 total
- Mapped to phases: 22
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-28*
*Last updated: 2026-03-28 after initial definition*
