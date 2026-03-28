# Project Research Summary

**Project:** MLB Win Probability Model
**Domain:** Sports analytics -- pre-game binary outcome prediction with probability calibration
**Researched:** 2026-03-28
**Confidence:** HIGH

## Executive Summary

This project is an MLB pre-game win probability forecasting system -- a well-studied problem in sports analytics with a practical ceiling of approximately 58-62% accuracy due to baseball's inherent randomness. Experts build these systems as data pipelines that ingest team and pitcher statistics, engineer temporally-safe differential features, train calibrated probabilistic classifiers, and evaluate them using proper scoring rules (Brier score). The key differentiator for this project is the head-to-head comparison against Kalshi prediction market implied probabilities, which provides a real-world benchmark but also introduces comparison pitfalls (favorite-longshot bias, fee structure, limited historical data starting only from 2025).

The recommended approach is a five-phase pipeline: (1) data ingestion with aggressive local caching to Parquet, (2) feature engineering with strict temporal guard rails to prevent the single most dangerous failure mode -- look-ahead bias, (3) model training with walk-forward backtesting across three model types (logistic regression, random forest, XGBoost), (4) Kalshi integration as an independent benchmark, and (5) a live daily prediction pipeline that reuses all prior code. The technology stack centers on Python 3.12, pandas 2.2.x (explicitly not 3.0 due to breaking string dtype changes with pybaseball), scikit-learn 1.8 (for temperature scaling calibration), and XGBoost 3.2 as the primary gradient boosting model. The architecture enforces a shared `FeatureBuilder` class used identically by both backtest and live pipelines -- this single design decision prevents the most common source of production failures in sports prediction projects.

The dominant risks are all forms of data leakage: using future game data in features, using end-of-season stats for mid-season games, and random train/test splits instead of temporal splits. These are not theoretical -- published MLB prediction projects have reported accuracy inflations of 5-15% from leakage that collapsed entirely in live deployment. Secondary risks include overfitting gradient boosting models to the small dataset (~12K games over 5 seasons), ignoring MLB rule changes that created structural breaks in 2023, and the cold-start problem where early-season predictions lack stable statistics. All of these are preventable with upfront architectural decisions.

## Key Findings

### Recommended Stack

The stack is anchored by a critical version constraint: **pandas 2.2.x paired with numpy 2.2.x**. Pandas 3.0 introduced PyArrow-backed string dtypes that break compatibility with pybaseball's object-dtype DataFrames -- this is a hard blocker, not a preference. Python 3.12 is the recommended runtime. Three data ingestion libraries cover all sources: pybaseball (FanGraphs, Statcast, Baseball Reference), MLB-StatsAPI (schedules, confirmed starters), and kalshi-python (market prices with RSA-PSS auth).

**Core technologies:**
- **Python 3.12 + pandas 2.2.x + numpy 2.2.x**: Foundation runtime and data processing -- pandas 3.0 explicitly avoided due to pybaseball incompatibility
- **pybaseball 2.2.7**: De facto standard for baseball data ingestion (Statcast, FanGraphs, Baseball Reference)
- **MLB-StatsAPI 1.9.0**: Game schedules and confirmed starting pitcher lookups
- **kalshi-python 2.1.4**: Official Kalshi SDK for prediction market price data
- **scikit-learn 1.8.0**: Model training, evaluation, and calibration -- includes new temperature scaling in `CalibratedClassifierCV`
- **XGBoost 3.2.0**: Primary gradient boosting model with strong scikit-learn API compatibility
- **Optuna 4.8.0**: Hyperparameter tuning with XGBoost pruning callbacks
- **SHAP 0.51.0**: Feature importance visualization to verify models learn generalizable patterns
- **JupyterLab 4.5.6**: Primary interface per project requirements

**What to avoid:** TensorFlow/PyTorch (overkill for 12K-row tabular data), Streamlit/Dash (out of scope), Apache Spark (dataset is trivially small), pandas 3.0 (breaking changes).

### Expected Features

Research identifies 10-15 differential features as the target feature count. Diminishing returns and overfitting risk escalate above 15 features for game-level binary classification.

**Must have (table stakes) -- V1 target achieving 58-62% accuracy:**
- Home/away indicator (binary, 53.9% baseline)
- Starting pitcher differential (FIP or xFIP -- single strongest per-game predictor)
- Team wOBA or OPS differential (season-to-date -- best single offensive summary)
- Pythagorean win percentage differential (run-differential-based team quality)
- Park factor (3-year rolling average, runs)
- Rolling 10-game team OPS differential (captures hot/cold streaks)
- Bullpen ERA or FIP differential (second-tier pitching signal)
- SP strikeout rate differential (dominance indicator, low multicollinearity with FIP)

**Should have (differentiators) -- V1.5:**
- SIERA (most predictive forward-looking ERA estimator)
- Log5 win probability (Bill James head-to-head formula using Pythagorean W%)
- SP recent form (last 3 starts rolling metrics)
- xwOBA differential (Statcast-based true contact quality)
- Bullpen FIP differential

**Defer (V2+):**
- Weather features (temperature, wind) -- requires external API, marginal gain
- Bullpen fatigue tracking -- requires per-pitcher game log pipeline
- Travel distance penalty -- small effect (~3.5% home advantage reduction)
- Elo rating system -- powerful but significant architectural complexity
- Steamer/ZiPS projection blending -- most valuable early season, complex to implement

**Anti-features (avoid entirely):**
- Batting average (wOBA strictly dominates)
- Individual batter-vs-pitcher matchups (sample size too small, overfitting trap)
- Fielding percentage (consistently reduces accuracy)
- Lineup batting order position (marginal effect, high complexity)

### Architecture Approach

The architecture is a five-layer pipeline: data ingestion, raw cache, feature engineering, model training, and evaluation/reporting. The most important architectural decision is a shared `FeatureBuilder` class that produces one row of features per game, used identically by both the backtest pipeline (over historical games) and the live prediction pipeline (for today's games). All reusable logic lives in a `src/` package imported by thin Jupyter notebooks. Data flows through Parquet files organized as raw (immutable after fetch) and processed (regenerable from raw). Kalshi implied probabilities are carried as a benchmark column -- never as a model input feature.

**Major components:**
1. **Data Ingestion Layer** -- Three API clients (MLB Stats API, pybaseball, Kalshi) writing to local Parquet cache
2. **Feature Engineering Layer** -- Domain-specific modules (pitching, batting, bullpen, context) composed by a `FeatureBuilder` with strict temporal guard rails (`as_of_date` parameter, `shift(1)` on all rolling features)
3. **Feature Store** -- Single Parquet file with one row per game, all features, outcome label, and Kalshi implied probability
4. **Model Training/Backtest Pipeline** -- Walk-forward expanding window evaluation (train on seasons 1..N, predict N+1) with three model types and temporal cross-validation
5. **Evaluation and Reporting** -- Brier score decomposition, calibration curves, model-vs-model and model-vs-Kalshi comparison in Jupyter notebooks

### Critical Pitfalls

1. **Look-ahead bias in feature construction** -- Every feature must use only data from completed games before the prediction date. Enforce with `as_of_date` parameters and `shift(1)` on all rolling computations. Write unit tests that verify removing a game's outcome does not change its features. Recovery cost is HIGH (full pipeline rebuild) if caught late.

2. **Temporal leakage in train/test splits** -- Never use random splits or `KFold`. Always use walk-forward validation or `TimeSeriesSplit` with data sorted by date. The test set must be strictly after the training set in time. This must be the first decision in the model training phase.

3. **End-of-season stats used for mid-season games** -- The most common shortcut in published projects. Requires building a game-log-level pipeline that computes cumulative stats incrementally. Cannot be retrofitted; must be the foundational data architecture.

4. **Treating Kalshi prices as ground truth** -- Kalshi prices contain favorite-longshot bias (empirically proven across 300K+ contracts), bid-ask spreads, and fee structure. Evaluate model calibration independently against actual outcomes, then compare model and Kalshi Brier scores side-by-side. Adjust for fees before claiming profitability.

5. **Overfitting gradient boosting to small dataset** -- 12K games with 20+ features and deep trees allows XGBoost to memorize team/pitcher patterns. Require aggressive regularization (max_depth 3-5, min_child_weight 50-100), early stopping on temporal validation, and a logistic regression calibration anchor. If GBM does not meaningfully beat LR (>0.005 Brier improvement on holdout), prefer the simpler model.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Data Ingestion and Raw Cache
**Rationale:** Hard dependency -- nothing can be built without data. pybaseball scraping is the first bottleneck (rate limiting), and establishing the Parquet cache pattern early prevents re-scraping throughout development.
**Delivers:** MLB Stats API client (schedules, starters), pybaseball wrappers (batting/pitching stats, team game logs), raw Parquet cache organized by season, data exploration notebook proving data quality and coverage.
**Addresses:** Schedule fetching, historical game data ingestion, Statcast metrics ingestion (FEATURES.md table stakes data sources).
**Avoids:** Pitfall 10 (survivorship bias) -- establish coverage tracking from the start. Pitfall 5 (rule changes) -- partition data by rule era during ingestion.

### Phase 2: Feature Engineering and Feature Store
**Rationale:** Features are the contract between raw data and models. Temporal safety (the `as_of_date` pattern and `shift(1)` guard rails) must be baked into the foundation -- retrofitting is impossible. This phase determines whether all subsequent backtest results are trustworthy.
**Delivers:** Feature modules (pitching, batting, bullpen, context), FeatureBuilder class with temporal guard rails, feature matrix Parquet (one row per historical game), feature exploration notebook with distributions and correlations, leakage unit tests.
**Addresses:** All V1 table stakes features (SP differential, team wOBA/OPS differential, Pythagorean W%, park factor, rolling stats, bullpen metrics).
**Avoids:** Pitfall 1 (look-ahead bias), Pitfall 3 (end-of-season stats), Pitfall 7 (small sample sizes via regression-to-mean blending).

### Phase 3: Model Training and Backtesting
**Rationale:** With a trusted feature matrix, models can be trained and evaluated. Walk-forward backtesting validates that features and models produce useful predictions before any market comparison is attempted.
**Delivers:** Three trained models (LR, RF, XGBoost) with tuned hyperparameters, walk-forward backtest results over 3-5 seasons, Brier score and calibration curves per model, model comparison notebook.
**Addresses:** All three model training requirements, backtesting requirement, Brier score computation.
**Avoids:** Pitfall 2 (temporal leakage in splits), Pitfall 6 (Brier score tunnel vision -- require decomposition and calibration curves), Pitfall 9 (GBM overfitting -- aggressive regularization and LR benchmark).

### Phase 4: Kalshi Integration and Market Comparison
**Rationale:** Kalshi comparison is the project's key differentiator but depends on having model predictions to compare against. Adding it after models are trained enables immediate side-by-side analysis. Also, Kalshi historical data only covers 2025+, so this phase is inherently limited in historical scope.
**Delivers:** Kalshi API client (market discovery, price history), historical Kalshi implied probabilities joined to feature matrix, model-vs-Kalshi Brier score comparison, edge analysis with fee-adjusted profitability, market comparison notebook.
**Addresses:** Kalshi market price ingestion, Brier score comparison against market implied probabilities.
**Avoids:** Pitfall 4 (treating Kalshi as ground truth -- evaluate independently against outcomes first, then compare).

### Phase 5: Live Prediction Pipeline
**Rationale:** This is the thinnest layer -- it orchestrates existing code (data clients, FeatureBuilder, trained models, Kalshi client) for today's games. Building it last ensures all components are proven.
**Delivers:** Daily prediction notebook (fetch schedule, build features, predict, compare to Kalshi), side-by-side output table, SP confirmation handling with fallback logic, optional daily automation script.
**Addresses:** Live prediction pipeline requirement, notebook-based reporting.
**Avoids:** Pitfall 8 (SP uncertainty -- graceful degradation when starters are scratched or TBD).

### Phase Ordering Rationale

- **Strict dependency chain:** Each phase consumes the output of the previous phase. Data ingestion produces raw cache; feature engineering consumes raw cache to produce the feature matrix; model training consumes the feature matrix; Kalshi comparison consumes model predictions; live prediction orchestrates all components.
- **Risk frontloading:** The two most dangerous pitfalls (look-ahead bias and temporal leakage) are addressed in Phases 2 and 3 respectively. If these are wrong, everything downstream is invalid. Addressing them early means validation is possible before significant model tuning effort.
- **Kalshi as late integration:** Kalshi data only exists from 2025. Delaying Kalshi integration to Phase 4 means the core model can be developed and validated on 2019-2025 data without any dependency on Kalshi availability. The comparison is layered on afterward.
- **Live pipeline as thin orchestration:** The live pipeline adds no new logic -- it reuses Phase 1-4 code in a "today" context. This architectural decision (shared FeatureBuilder) means the live pipeline is inherently consistent with the backtest.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2 (Feature Engineering):** The regression-to-mean blending for early-season stats, the exact rolling window implementations (SMA vs EMA), and the differential framing strategy all benefit from more detailed design research. The cold-start problem (first 2-3 weeks of a season) is well-documented but the specific blending formula needs tuning.
- **Phase 4 (Kalshi Integration):** The Kalshi API is evolving. The series-ticker discovery for MLB games, historical price data availability, and the favorite-longshot bias de-biasing methodology need hands-on validation. Kalshi fee structure may change.

Phases with standard patterns (skip deeper research):
- **Phase 1 (Data Ingestion):** pybaseball and MLB-StatsAPI are well-documented with extensive examples. The caching pattern is straightforward.
- **Phase 3 (Model Training):** Walk-forward backtesting, scikit-learn pipelines, XGBoost hyperparameter tuning, and calibration are all thoroughly documented with established best practices.
- **Phase 5 (Live Pipeline):** Thin orchestration layer with no novel patterns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All package versions verified on PyPI. Pandas 2.2.x constraint well-justified by pybaseball compatibility. scikit-learn 1.8 temperature scaling confirmed in release docs. |
| Features | HIGH | Feature recommendations backed by multiple academic sources (PMC, Wharton thesis), practitioner reports (FiveThirtyEight Elo methodology, Zheng SVM model), and FanGraphs sabermetric definitions. 10-15 feature target is consensus. |
| Architecture | HIGH | Pipeline pattern (ingest, feature, train, evaluate) is the standard for ML prediction projects. Shared FeatureBuilder pattern specifically addresses the most common failure mode. Walk-forward backtesting is well-established. |
| Pitfalls | HIGH | Multiple independent sources converge on the same pitfalls: look-ahead bias (Wharton thesis, Zheng practitioner report), temporal leakage (scikit-learn docs), Kalshi bias (Whelan 2025 empirical study of 300K contracts), GBM overfitting (XGBoost and LightGBM official tuning guides). |

**Overall confidence:** HIGH

### Gaps to Address

- **Kalshi historical data depth:** Kalshi sports markets launched in early 2025. Historical backtest comparison is limited to approximately one season. This is a hard constraint -- the project must clearly scope which evaluation is model-only (2019-2024) vs. model-vs-Kalshi (2025 only).
- **pybaseball reliability on Python 3.12:** pybaseball officially supports up to Python 3.11. It works on 3.12 but is not officially tested. May require fallback to direct requests + BeautifulSoup if scraping breaks.
- **2020 season anomaly:** The 60-game 2020 season had different dynamics. Research recommends either excluding it or flagging it as a separate era. Decision needed during Phase 1 data ingestion.
- **Exact Bayesian blending weights for cold-start:** The regression-to-mean formula for early-season stats (blending prior-season with current-season) has suggested stabilization points (60 IP for ERA, 30 IP for FIP) but optimal prior weights need empirical tuning during Phase 2.
- **Kalshi API authentication for historical data:** Public market data endpoints may not require auth, but historical price data access needs verification during Phase 4 implementation.

## Sources

### Primary (HIGH confidence)
- [pybaseball PyPI](https://pypi.org/project/pybaseball/) -- v2.2.7, data ingestion capabilities
- [MLB-StatsAPI PyPI](https://pypi.org/project/MLB-StatsAPI/) -- v1.9.0, schedule and roster access
- [kalshi-python PyPI](https://pypi.org/project/kalshi-python/) -- v2.1.4, market data SDK
- [scikit-learn 1.8 release highlights](https://scikit-learn.org/stable/auto_examples/release_highlights/plot_release_highlights_1_8_0.html) -- temperature scaling calibration
- [pandas 3.0 migration guide](https://pandas.pydata.org/docs/user_guide/migration-3-strings.html) -- breaking string dtype changes
- [PMC: Feature Selection for MLB Game Prediction](https://pmc.ncbi.nlm.nih.gov/articles/PMC8871522/) -- RFE feature selection, SVM achieving 65.75%
- [Wharton Thesis: Forecasting MLB Game Outcomes](https://fisher.wharton.upenn.edu/wp-content/uploads/2020/09/Thesis_Andrew-Cui.pdf) -- 10-day trailing differentials, feature engineering methodology
- [FiveThirtyEight MLB Elo Methodology](https://fivethirtyeight.com/methodology/how-our-mlb-predictions-work/) -- Elo adjustments, SP impact, travel/rest effects
- [Whelan (2025): Kalshi Prediction Market Analysis](https://www.karlwhelan.com/sports-betting-kalshi-prediction-market/) -- Empirical favorite-longshot bias across 300K+ contracts

### Secondary (MEDIUM confidence)
- [Zheng: Beat the Sportsbook with ML](https://medium.com/@40alexz.40/how-i-beat-the-sportsbook-in-baseball-with-machine-learning-0387f25fbdd8) -- 11-feature SVM, data leakage discovery, 13.95% ROI
- [Faddis: Predicting Win Probability for MLB Games](https://medium.com/@nfadd/predicting-win-probability-for-mlb-games-with-machine-learning-a4c2ad993496) -- XGBoost with rolling averages, 61.46% accuracy
- [arXiv:2504.04906: Misconceptions about Brier Score](https://arxiv.org/html/2504.04906v4) -- calibration vs discrimination nuances
- [Sports-AI: Model Calibration for Betting](https://www.sports-ai.dev/blog/ai-model-calibration-brier-score) -- calibration-optimized models yield 69.86% higher returns
- [Pitcher List: FIP vs xFIP vs SIERA](https://pitcherlist.com/the-relative-value-of-fip-xfip-and-siera-pt-ii/) -- SIERA most predictive forward-looking metric

### Tertiary (LOW confidence)
- [Kalshi API docs](https://docs.kalshi.com/getting_started/quick_start_market_data) -- API structure confirmed, but sports-specific endpoints may evolve
- [CEPR: Economics of the Kalshi Prediction Market](https://cepr.org/voxeu/columns/economics-kalshi-prediction-market) -- general market structure, not MLB-specific

---
*Research completed: 2026-03-28*
*Ready for roadmap: yes*
