# Architecture Research

**Domain:** MLB Pre-Game Win Probability Modeling & Prediction Market Comparison
**Researched:** 2026-03-28
**Confidence:** HIGH (core ML pipeline patterns well-documented; MEDIUM on Kalshi-specific integration due to evolving API)

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                     DATA INGESTION LAYER                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ MLB Stats API│  │  pybaseball  │  │  Kalshi API  │              │
│  │ (schedules,  │  │ (FanGraphs,  │  │ (market      │              │
│  │  starters)   │  │  Statcast,   │  │  prices,     │              │
│  │              │  │  B-Ref)      │  │  history)    │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                  │                      │
├─────────┴─────────────────┴──────────────────┴──────────────────────┤
│                     RAW DATA CACHE (Parquet/CSV)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ game_logs/   │  │ player_stats/│  │ market_data/ │              │
│  │ schedules/   │  │ statcast/    │  │ prices/      │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                  │                      │
├─────────┴─────────────────┴──────────────────┴──────────────────────┤
│                     FEATURE ENGINEERING LAYER                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Rolling Stats   Differential   Park Factors   Kalshi Implied│   │
│  │  (shift(1))      Features       Adjustments    Probabilities │   │
│  └──────────────────────────┬───────────────────────────────────┘   │
│                             │                                      │
├─────────────────────────────┴──────────────────────────────────────┤
│                     FEATURE STORE (Parquet)                         │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  One row per game: game_id, date, features[], outcome, kalshi│   │
│  └──────────────────────────┬───────────────────────────────────┘   │
│                             │                                      │
├──────────────┬──────────────┴───────────────┬──────────────────────┤
│  BACKTEST    │       MODEL TRAINING         │   LIVE PREDICTION    │
│  PIPELINE    │       PIPELINE               │   PIPELINE           │
│  ┌────────┐  │  ┌─────────┐  ┌──────────┐  │  ┌───────────────┐   │
│  │Walk-   │  │  │Temporal │  │  Train:  │  │  │Today's games: │   │
│  │forward │  │  │CV Split │  │  LR, RF, │  │  │fetch schedule │   │
│  │eval    │  │  │(Time    │  │  XGBoost │  │  │build features │   │
│  │over    │  │  │Series   │  │  /LGBM   │  │  │predict probs  │   │
│  │seasons │  │  │Split)   │  │          │  │  │compare Kalshi │   │
│  └───┬────┘  │  └────┬────┘  └────┬─────┘  │  └───────┬───────┘   │
│      │       │       │            │         │          │           │
├──────┴───────┴───────┴────────────┴─────────┴──────────┴──────────┤
│                     EVALUATION & REPORTING                         │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Brier Scores   Calibration Curves   Model Comparison Tables │   │
│  │  Edge Analysis (model vs Kalshi)   Feature Importance Plots  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                     OUTPUT: Jupyter Notebooks                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **MLB Stats API Client** | Fetch daily schedules, confirmed starting pitchers, roster data | `MLB-StatsAPI` package (`statsapi`); `schedule()` and game endpoint calls |
| **pybaseball Ingestor** | Pull season-level batting/pitching stats, team game logs, Statcast data | `pybaseball` functions: `batting_stats()`, `pitching_stats()`, `team_game_logs()`, `schedule_and_record()` |
| **Kalshi API Client** | Fetch current and historical MLB game market prices (implied probabilities) | `requests` against `https://api.elections.kalshi.com/trade-api/v2`; no auth needed for market data |
| **Raw Data Cache** | Store fetched data locally to avoid redundant API calls and rate limiting | Parquet files organized by data type and season; pybaseball's `cache.enable()` for its own calls |
| **Feature Engineering** | Transform raw stats into model-ready features with strict temporal ordering | pandas transformations with `shift(1)` on all rolling features; differential features (team A - team B) |
| **Feature Store** | Single consolidated table: one row per game with all features and the outcome label | Parquet file(s) keyed by `game_id` and `date`; includes both model features and Kalshi implied prob |
| **Model Training Pipeline** | Train and tune three models (LR, RF, GBM) with temporal cross-validation | scikit-learn `LogisticRegression`, `RandomForestClassifier`; XGBoost or LightGBM; `TimeSeriesSplit` for CV |
| **Backtest Pipeline** | Walk-forward evaluation over 3-5 historical seasons | Season-by-season expanding window: train on seasons 1..N, predict season N+1 |
| **Live Prediction Pipeline** | Daily workflow: fetch today's games, build features, output predictions | Reuses same feature engineering code as backtest; adds Kalshi price fetch for comparison |
| **Evaluation & Reporting** | Compute Brier scores, calibration curves, model vs. market comparisons | `sklearn.metrics.brier_score_loss`, `sklearn.calibration.calibration_curve`, matplotlib/seaborn |

## Recommended Project Structure

```
MLB-WinForcater/
├── notebooks/                    # Jupyter notebooks (the user interface)
│   ├── 01_data_exploration.ipynb     # Explore raw data, sanity checks
│   ├── 02_feature_engineering.ipynb  # Develop and validate features
│   ├── 03_model_training.ipynb       # Train, tune, compare models
│   ├── 04_backtesting.ipynb          # Walk-forward historical eval
│   ├── 05_live_predictions.ipynb     # Daily prediction workflow
│   └── 06_analysis_report.ipynb      # Brier scores, calibration, edge analysis
│
├── src/                          # Shared Python modules (imported by notebooks)
│   ├── __init__.py
│   ├── data/                     # Data acquisition
│   │   ├── __init__.py
│   │   ├── mlb_api.py                # MLB Stats API wrapper (schedules, starters)
│   │   ├── pybaseball_client.py      # pybaseball convenience functions
│   │   └── kalshi_client.py          # Kalshi market data fetcher
│   │
│   ├── features/                 # Feature engineering
│   │   ├── __init__.py
│   │   ├── pitching.py               # SP stats: ERA, FIP, xFIP, K%, recent form
│   │   ├── batting.py                # Team offense: wOBA, OPS, run diff, recent
│   │   ├── bullpen.py                # Bullpen: ERA, rest days, usage flags
│   │   ├── context.py                # Home/away, park factors
│   │   └── builder.py                # Assembles all features into game-level rows
│   │
│   ├── models/                   # Model definitions and training
│   │   ├── __init__.py
│   │   ├── logistic.py               # Logistic regression config
│   │   ├── random_forest.py          # Random forest config
│   │   ├── gradient_boost.py         # XGBoost/LightGBM config
│   │   └── trainer.py                # Shared train/predict/evaluate interface
│   │
│   ├── evaluation/               # Scoring and comparison
│   │   ├── __init__.py
│   │   ├── brier.py                  # Brier score computation and decomposition
│   │   ├── calibration.py            # Calibration curve generation
│   │   └── comparison.py             # Model-vs-model and model-vs-Kalshi analysis
│   │
│   └── pipelines/                # Orchestration
│       ├── __init__.py
│       ├── backtest.py               # Walk-forward backtest runner
│       └── live.py                   # Today's predictions runner
│
├── data/                         # Local data cache (gitignored except structure)
│   ├── raw/                      # Direct API/scrape outputs
│   │   ├── schedules/
│   │   ├── game_logs/
│   │   ├── player_stats/
│   │   └── market_data/
│   ├── processed/                # Feature-engineered datasets
│   │   └── features/
│   └── models/                   # Saved model artifacts
│
├── .planning/                    # Project planning docs
├── requirements.txt              # Python dependencies
├── .gitignore
└── pyproject.toml                # Project config
```

### Structure Rationale

- **`notebooks/` numbered sequentially:** Mirrors the natural workflow. Numbered prefixes enforce the logical order that newcomers should follow. Each notebook imports from `src/` and stays thin -- orchestration and visualization, not business logic.
- **`src/` as importable package:** All reusable logic lives here so that both backtest and live prediction pipelines use identical feature engineering and model code. This is the single most important architectural decision -- it prevents drift between backtesting and live prediction.
- **`src/features/` split by domain:** Pitching, batting, bullpen, and context features each get their own module. `builder.py` composes them into the final feature matrix. This makes it easy to add or modify feature groups independently.
- **`src/models/` with shared trainer:** Each model type has its own config module (hyperparameter ranges, preprocessing), but `trainer.py` provides a uniform interface for train/predict/score. This enables clean model comparison loops.
- **`data/raw/` vs `data/processed/`:** Raw data is immutable after fetch. Processed data can always be regenerated from raw. This separation enables reproducibility and makes it safe to nuke `processed/` and rebuild.

## Architectural Patterns

### Pattern 1: Shared Feature Builder (Backtest/Live Code Reuse)

**What:** A single `FeatureBuilder` class that produces one row of features for a given game, used identically by both the backtest pipeline (over historical games) and the live prediction pipeline (for today's games).

**When to use:** Always. This is the core pattern that prevents the most dangerous failure mode: backtest results that cannot be reproduced in live prediction because the feature code diverged.

**Trade-offs:** Slightly more upfront design to parameterize the builder (e.g., "as of date" for rolling windows), but massive reduction in bugs and maintenance.

**Example:**
```python
class FeatureBuilder:
    """Builds feature vector for a single game matchup.

    All rolling/aggregate stats are computed using only data
    available BEFORE the game date (strict temporal cutoff).
    """
    def __init__(self, stats_store: StatsStore):
        self.stats = stats_store

    def build(self, game_date: str, home_team: str, away_team: str,
              home_sp_id: int, away_sp_id: int) -> pd.Series:
        features = {}
        features.update(self._pitching_features(home_sp_id, game_date, prefix="home_sp"))
        features.update(self._pitching_features(away_sp_id, game_date, prefix="away_sp"))
        features.update(self._batting_features(home_team, game_date, prefix="home"))
        features.update(self._batting_features(away_team, game_date, prefix="away"))
        features.update(self._bullpen_features(home_team, game_date, prefix="home_bp"))
        features.update(self._bullpen_features(away_team, game_date, prefix="away_bp"))
        features.update(self._context_features(home_team, away_team))
        # Differential features: home - away
        features.update(self._differential_features(features))
        return pd.Series(features)
```

### Pattern 2: Temporal Guard Rails on Rolling Features

**What:** Every rolling statistic uses an explicit `shift(1)` or date-filtered query to guarantee that only pre-game data is included. This is enforced at the feature engineering level, not at the model level.

**When to use:** Every single rolling or aggregate feature. No exceptions.

**Trade-offs:** Slower feature computation (cannot vectorize as aggressively), but eliminates data leakage -- the single most common and devastating bug in sports prediction models.

**Example:**
```python
def rolling_era(pitcher_game_logs: pd.DataFrame, as_of_date: str,
                window: int = 10) -> float:
    """Compute rolling ERA using only starts BEFORE as_of_date."""
    prior_starts = pitcher_game_logs[
        pitcher_game_logs["date"] < as_of_date
    ].tail(window)

    if len(prior_starts) < 3:  # minimum sample threshold
        return np.nan  # insufficient data, let model handle missingness

    total_er = prior_starts["ER"].sum()
    total_ip = prior_starts["IP"].sum()
    return (total_er / total_ip) * 9.0 if total_ip > 0 else np.nan
```

### Pattern 3: Walk-Forward Backtesting with Expanding Window

**What:** Train on all available seasons up to year N, predict year N+1. Expand the training window and repeat. This mirrors real deployment where you retrain periodically with more data.

**When to use:** For the primary backtest evaluation. A secondary sliding-window backtest (fixed N-year training window) can supplement to check if older data helps or hurts.

**Trade-offs:** Computationally heavier than a single train/test split, but produces realistic performance estimates. The expanding window typically outperforms fixed windows because baseball's statistical relationships are relatively stable across eras (within a 5-year horizon).

**Example:**
```python
def walk_forward_backtest(feature_store: pd.DataFrame,
                          model_factory,
                          train_start_year: int,
                          test_end_year: int) -> pd.DataFrame:
    """
    Walk-forward evaluation: train on [train_start..year], predict year+1.

    Returns DataFrame of predictions with columns:
      game_id, date, predicted_prob, actual_outcome, kalshi_implied_prob
    """
    results = []
    seasons = sorted(feature_store["season"].unique())

    for i, test_season in enumerate(seasons):
        if test_season <= train_start_year:
            continue
        if test_season > test_end_year:
            break

        train = feature_store[feature_store["season"] < test_season]
        test = feature_store[feature_store["season"] == test_season]

        model = model_factory()
        model.fit(train[FEATURE_COLS], train["home_win"])

        preds = model.predict_proba(test[FEATURE_COLS])[:, 1]
        test_results = test[["game_id", "date", "home_win", "kalshi_implied"]].copy()
        test_results["predicted_prob"] = preds
        results.append(test_results)

    return pd.concat(results, ignore_index=True)
```

## Data Flow

### Historical Data Collection Flow

```
pybaseball.batting_stats(2019, 2025)  ──→  data/raw/player_stats/batting_YYYY.parquet
pybaseball.pitching_stats(2019, 2025) ──→  data/raw/player_stats/pitching_YYYY.parquet
pybaseball.team_game_logs(YYYY, team) ──→  data/raw/game_logs/TEAM_YYYY.parquet
pybaseball.schedule_and_record(YYYY, team) ──→  data/raw/schedules/TEAM_YYYY.parquet
Kalshi API /markets?series_ticker=... ──→  data/raw/market_data/kalshi_YYYY.parquet
```

### Feature Engineering Flow

```
raw/player_stats/ + raw/game_logs/ + raw/schedules/
    │
    ▼
FeatureBuilder.build() per game
    │
    ├── pitching.py: rolling ERA, FIP, xFIP, K%, WHIP (10-start & 30-start windows)
    ├── batting.py:  rolling wOBA, OPS, runs/game, K% (14-game & 30-game windows)
    ├── bullpen.py:  team bullpen ERA, recent usage, rest days
    ├── context.py:  home/away flag, park run factor, day/night
    └── builder.py:  differential features (home_metric - away_metric)
    │
    ▼
data/processed/features/feature_matrix.parquet
    (one row per game: game_id, date, season, 40-80 features, home_win, kalshi_implied)
```

### Model Training Flow

```
feature_matrix.parquet
    │
    ▼
TimeSeriesSplit or walk-forward split
    │
    ├── Train: LogisticRegression       ──→  models/logistic_vN.joblib
    ├── Train: RandomForestClassifier   ──→  models/rf_vN.joblib
    └── Train: XGBClassifier / LGBMClassifier ──→  models/gbm_vN.joblib
    │
    ▼
Per-model: predictions on test folds
    │
    ▼
evaluation/brier.py: Brier score per model
evaluation/calibration.py: calibration curve per model
evaluation/comparison.py: model vs. Kalshi Brier score comparison
```

### Live Prediction Flow (Daily)

```
MLB Stats API: today's schedule + confirmed starters
    │
    ▼
FeatureBuilder.build() for each game  [SAME code as backtest]
    │
    ▼
Loaded models predict_proba()
    │
    ▼
Kalshi API: current market prices for today's games
    │
    ▼
Side-by-side table in notebook:
  Game | Model LR | Model RF | Model GBM | Kalshi | Largest Edge
```

### Key Data Flows

1. **Ingestion-to-Cache:** All external API calls write to `data/raw/` as Parquet files. Subsequent pipeline steps read from cache, never directly from APIs. This decouples data freshness from pipeline execution and respects rate limits.

2. **Cache-to-Features:** The `FeatureBuilder` reads from the raw cache and produces the feature matrix. This is a pure transformation -- deterministic given the same inputs. The feature matrix is the contract boundary between data acquisition and modeling.

3. **Features-to-Predictions:** Models consume only the feature matrix. They never touch raw data. This means swapping data sources (e.g., replacing pybaseball with a different Statcast source) requires changes only in the ingestion layer.

4. **Kalshi-as-Benchmark:** Kalshi implied probabilities flow through as a column in the feature matrix (for backtesting comparison) but are NOT used as model input features. They are the benchmark, not a signal. Using them as features would be circular and defeat the purpose.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| **Single user, Jupyter** (this project) | Local Parquet files, in-memory pandas, models saved as joblib. No database needed. |
| **Daily automation** | Add a cron/scheduled script that runs `pipelines/live.py`, saves predictions, and optionally sends a notification. Still no database. |
| **Multi-season data growth** | After ~5 seasons of game-level data (~12,000 games), everything fits in memory. Statcast pitch-level data is larger but should be pre-aggregated to pitcher/game level during ingestion. |
| **Adding more models** | The `trainer.py` interface makes this trivial. Add a new model config module and register it. |

### Scaling Priorities

1. **First bottleneck: pybaseball rate limiting.** pybaseball scrapes websites and can be throttled. Use `cache.enable()`, batch historical pulls by season, and cache aggressively to Parquet. Do not re-fetch data that has not changed.
2. **Second bottleneck: Feature computation time.** If building features for 5 seasons x 2,430 games = ~12,000 games, naive row-by-row computation may be slow. Vectorize where possible (e.g., compute rolling stats for all pitchers at once via groupby + rolling, then join). Reserve row-by-row `FeatureBuilder.build()` for live prediction where only 15 games need features.

## Anti-Patterns

### Anti-Pattern 1: Data Leakage Through Season Averages

**What people do:** Use a pitcher's full-season ERA as a feature for predicting games within that season. This means each game's prediction includes information from games that have not happened yet.

**Why it's wrong:** Artificially inflates backtest accuracy by 5-15%. Models look great in backtest, fail completely in live prediction where you only have data up to "now."

**Do this instead:** Use strictly rolling statistics with `shift(1)` or date-filtered lookback windows. Accept that early-season predictions will have thin data -- handle this with minimum-sample thresholds and fallback to prior-season stats.

### Anti-Pattern 2: Using Kalshi Prices as Model Features

**What people do:** Include the Kalshi implied probability as an input feature to the ML model, then claim the model "beats the market."

**Why it's wrong:** The model is just learning to copy the market price with minor adjustments. Any apparent edge is an artifact. The purpose of this project is to build an independent model and compare it to market prices, not to predict market prices.

**Do this instead:** Keep Kalshi implied probabilities as a benchmark column only. Compare model Brier score vs. Kalshi Brier score. Analyze games where model and market disagree -- those are the interesting cases.

### Anti-Pattern 3: Splitting Train/Test Randomly Instead of Temporally

**What people do:** Use `train_test_split(test_size=0.2, random_state=42)` which shuffles games randomly across the train and test sets.

**Why it's wrong:** A 2023 game could be in the test set while a 2024 game is in the training set. The model trains on future data to predict the past. This inflates accuracy and completely misrepresents real-world performance.

**Do this instead:** Always split by time. Use `TimeSeriesSplit` for cross-validation or season-boundary splits for walk-forward backtesting. The test set must always be temporally after the training set.

### Anti-Pattern 4: Monolithic Notebooks with No Shared Code

**What people do:** Write all data fetching, feature engineering, model training, and evaluation in a single enormous notebook, with copy-pasted functions between the backtest notebook and the live prediction notebook.

**Why it's wrong:** When you fix a bug in feature engineering, you must remember to fix it in every notebook. Inevitably, the backtest and live pipelines diverge, and backtest results no longer reflect what the live pipeline actually does.

**Do this instead:** All reusable logic lives in `src/`. Notebooks are thin orchestration and visualization layers that import from `src/`. One source of truth for feature engineering code.

### Anti-Pattern 5: Not Handling Missing Starters

**What people do:** Assume starting pitcher data is always available and crash when it is not.

**Why it's wrong:** Starting pitchers are sometimes announced late, changed last-minute (scratched), or are callups with minimal MLB stats. Bullpen games (openers) have no traditional starter.

**Do this instead:** Build graceful degradation: if starter is unknown, fall back to team-level pitching stats. If starter has fewer than N MLB starts, blend their minor-league or spring-training indicators with league-average priors. Flag predictions with missing-starter data so you can filter them in analysis.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| **MLB Stats API** | REST via `MLB-StatsAPI` package (`pip install MLB-StatsAPI`) | Free, no auth. Use `statsapi.schedule()` for daily games, `statsapi.get()` for game detail. Rate limits are generous but cache anyway. |
| **pybaseball / Baseball Savant** | Python package scraping FanGraphs + Baseball Reference + Statcast | Use `cache.enable()` to avoid re-scraping. Statcast queries can be slow for large date ranges -- batch by month. FanGraphs functions return season-level aggregates. |
| **Kalshi API** | REST via `requests`; base URL: `https://api.elections.kalshi.com/trade-api/v2` | Market data endpoints are public (no auth). Series > Events > Markets hierarchy. Filter `/markets` by series_ticker for MLB games. Prices are 0-100 cents (divide by 100 for probability). |
| **FanGraphs (direct)** | Via pybaseball's `batting_stats()` / `pitching_stats()` | Advanced metrics (wOBA, FIP, xFIP, wRC+) come from here. More reliable than scraping FanGraphs directly. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| **Ingestion -> Raw Cache** | Function returns DataFrame, caller writes to Parquet | Ingestion functions are pure data fetchers. They do not transform. |
| **Raw Cache -> Feature Builder** | Feature Builder reads Parquet, returns feature DataFrame | Feature Builder never calls APIs. It only reads from cache. This makes it testable and deterministic. |
| **Feature Store -> Models** | Models receive numpy arrays (X, y) from the feature DataFrame | Models have no knowledge of data sources. They only see numeric features. |
| **Models -> Evaluation** | Evaluation receives (predicted_probs, actual_outcomes, kalshi_probs) | Evaluation is model-agnostic. It works with any array of probabilities. |
| **Pipelines -> Notebooks** | Pipelines are importable functions. Notebooks call them and display results. | Notebooks add visualization and narrative. They do not contain business logic. |

## Build Order (Dependency-Driven)

The following order reflects hard dependencies: each phase requires the outputs of the previous phase.

### Phase 1: Data Ingestion + Raw Cache

**Build first because:** Everything else depends on having data. You cannot engineer features, train models, or backtest without historical game data, player stats, and (later) market prices.

**Delivers:**
- MLB Stats API client (schedules, game results, starting pitchers)
- pybaseball wrappers (batting stats, pitching stats, team game logs)
- Raw data cached to Parquet, organized by season
- Data exploration notebook proving data quality

**Does NOT require:** Feature engineering, models, Kalshi integration

### Phase 2: Feature Engineering + Feature Store

**Build second because:** Features are the contract between raw data and models. Getting this right (especially temporal safety) determines whether backtest results are trustworthy.

**Delivers:**
- Feature modules (pitching, batting, bullpen, context)
- FeatureBuilder that composes all features for a game
- Feature matrix Parquet file (one row per historical game)
- Feature exploration notebook with distributions and correlations

**Depends on:** Phase 1 (raw cached data)

### Phase 3: Model Training + Backtesting

**Build third because:** Now you have features and can train models. Backtesting validates that the features and models produce useful predictions over historical data.

**Delivers:**
- Three trained models (LR, RF, GBM) with tuned hyperparameters
- Walk-forward backtest results over 3-5 seasons
- Brier score evaluation per model
- Calibration curves per model
- Model comparison notebook

**Depends on:** Phase 2 (feature matrix)

### Phase 4: Kalshi Integration + Market Comparison

**Build fourth because:** Kalshi comparison is the project's key differentiator but is not needed for model development. Adding it after models are trained means you can compare immediately.

**Delivers:**
- Kalshi API client (market discovery, price history)
- Historical Kalshi implied probabilities joined to feature matrix
- Brier score: models vs. Kalshi
- Edge analysis: where models and markets disagree
- Market comparison notebook

**Depends on:** Phase 3 (model predictions to compare against)

**Note on Kalshi historical data:** Kalshi only launched sports markets in January 2025. Historical MLB game market data may only cover the 2025 season. For seasons before that, backtest evaluation will compare models against each other but not against market prices. This is a hard data constraint, not a bug.

### Phase 5: Live Prediction Pipeline

**Build last because:** It reuses everything from Phases 1-4 in a "today" context. It is the thinnest layer -- just orchestrating existing code for the current day.

**Delivers:**
- Daily prediction notebook: fetch today's schedule, build features, predict, compare to Kalshi
- Side-by-side output table
- Potentially a lightweight script for daily automation

**Depends on:** All previous phases (data clients, feature builder, trained models, Kalshi client)

## Sources

- [pybaseball GitHub repository and documentation](https://github.com/jldbc/pybaseball)
- [MLB-StatsAPI Python wrapper](https://github.com/toddrob99/MLB-StatsAPI)
- [Kalshi API documentation - Quick Start Market Data](https://docs.kalshi.com/getting_started/quick_start_market_data)
- [Kalshi API reference - Get Event](https://docs.kalshi.com/api-reference/events/get-event)
- [scikit-learn TimeSeriesSplit documentation](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)
- [scikit-learn brier_score_loss documentation](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.brier_score_loss.html)
- [Wharton thesis: Forecasting Outcomes of MLB Games Using ML](https://fisher.wharton.upenn.edu/wp-content/uploads/2020/09/Thesis_Andrew-Cui.pdf)
- [PMC: Exploring and Selecting Features to Predict MLB Game Outcomes](https://pmc.ncbi.nlm.nih.gov/articles/PMC8871522/)
- [arXiv: The Impacts of Increasingly Complex Matchup Models on Baseball Win Probability](https://arxiv.org/html/2511.17733v1)
- [Medium: How I Beat the Sportsbook in Baseball with ML](https://medium.com/@40alexz.40/how-i-beat-the-sportsbook-in-baseball-with-machine-learning-0387f25fbdd8) (rolling window and shift(1) patterns)
- [Kalshi MLB market launch coverage](https://www.covers.com/industry/kalshi-launches-mlb-game-markets-despite-scrutiny-over-sports-contracts-april-17-2025)

---
*Architecture research for: MLB Pre-Game Win Probability Modeling*
*Researched: 2026-03-28*
