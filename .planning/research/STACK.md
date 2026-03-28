# Technology Stack

**Project:** MLB Win Probability Model
**Researched:** 2026-03-28

## Python Version

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.11+ | Runtime | 3.11 is the minimum common denominator across pandas 3.x, numpy 2.4, scikit-learn 1.8, and XGBoost 3.2. Use 3.12 for best compatibility and performance. Avoid 3.14 (too bleeding-edge for pybaseball). |

**Confidence:** HIGH -- verified against PyPI requirements for all core dependencies.

---

## Recommended Stack

### Data Ingestion

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| pybaseball | 2.2.7 | Statcast and Baseball Savant data, FanGraphs stats, Baseball Reference scraping | The de facto standard for Python baseball analytics. Provides `statcast()`, `pitching_stats()`, `batting_stats()`, `team_batting()`, `team_pitching()` and more. Last released Sep 2023, but actively maintained on GitHub and still functional against current data sources. |
| MLB-StatsAPI | 1.9.0 | Game schedules, rosters, confirmed starting pitchers, live game status | Todd Roberts' wrapper (`import statsapi`) is the most battle-tested MLB Stats API client. Provides `statsapi.schedule()` for day-of lineup confirmation and `statsapi.roster()` for active rosters. Released Apr 2025. |
| kalshi-python | 2.1.4 | Kalshi prediction market prices (historical and live) | Official Kalshi SDK, auto-generated from OpenAPI spec. Uses RSA-PSS authentication. Released Sep 2025. Provides market data endpoints for fetching event contracts and historical prices. |
| requests | 2.32+ | Direct HTTP calls to MLB Stats API or Kalshi endpoints when SDK wrappers are insufficient | Fallback for any endpoint not covered by the wrapper libraries. MLB Stats API is public and well-documented at statsapi.mlb.com. |

**Confidence:**
- pybaseball: HIGH -- verified on PyPI (2.2.7, Sep 2023). Note: version is 2+ years old but package works against current Statcast/Baseball Savant endpoints.
- MLB-StatsAPI: HIGH -- verified on PyPI (1.9.0, Apr 2025).
- kalshi-python: HIGH -- verified on PyPI (2.1.4, Sep 2025).

**Important note on pybaseball:** The package supports Python 3.8-3.11 officially. On Python 3.12+ it still works but is not officially listed. Pin to `pybaseball>=2.2.7` and test on your target Python version. If scraping breaks (Baseball Reference or FanGraphs change HTML), fall back to direct `requests` + `BeautifulSoup` for those sources.

### Data Processing & Feature Engineering

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| pandas | 2.2.3 | DataFrames, data manipulation, feature engineering pipelines | Use pandas 2.2.x (NOT 3.0.x). Pandas 3.0 (released Jan 2026) introduces breaking changes: default PyArrow-backed string dtype, stricter type enforcement, and dropped Python 3.9-3.10 support. For a data science project that heavily uses pybaseball (which returns object-dtype DataFrames), pandas 2.2.3 avoids migration headaches with zero downside. |
| numpy | 2.2.x | Numerical operations, array math | Use numpy 2.2.x for compatibility with pandas 2.2.x. Numpy 2.4.x requires Python 3.11+ and pairs with pandas 3.x. Staying on numpy 2.2 keeps the dependency graph stable. |
| scipy | 1.14+ | Statistical functions (Brier score decomposition, distributions) | Used for `scipy.stats` probability distributions, statistical tests, and potential Pythagorean exponent optimization. |

**Confidence:**
- pandas version decision: HIGH -- pandas 3.0 breaking changes are well-documented. Sticking with 2.2.x is the pragmatic choice for a project ingesting data from older libraries.
- numpy: MEDIUM -- numpy 2.2.x is the right pairing for pandas 2.2.x but verify exact compatibility.

### Machine Learning

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| scikit-learn | 1.8.0 | Logistic regression, random forest, model evaluation, calibration, pipelines | The foundation. Use `LogisticRegression`, `RandomForestClassifier`, `cross_val_score`, `brier_score_loss`, and critically `CalibratedClassifierCV` with the new `method="temperature"` (new in 1.8). Temperature scaling is directly relevant for calibrating win probabilities. |
| XGBoost | 3.2.0 | Gradient boosting model (primary boosting approach) | XGBoost 3.2 (Feb 2026) is the latest stable. Excellent scikit-learn API compatibility via `XGBClassifier`. Superior to LightGBM for this use case because: (1) better documentation, (2) built-in feature importance, (3) stronger community for sports analytics specifically. |
| LightGBM | 4.6.0 | Alternative gradient boosting model (comparison benchmark) | Include as a comparison point, not the primary model. LightGBM 4.6 (Feb 2025) trains faster on large datasets but for ~2,430 games/season x 5 seasons (~12K rows), speed difference is negligible. XGBoost is the better default. |
| SHAP | 0.51.0 | Model explainability, feature importance visualization | Explains which features drive predictions (pitcher ERA vs. team wOBA vs. home advantage). `shap.TreeExplainer` works natively with XGBoost and LightGBM. Essential for understanding model behavior and building trust in predictions. |
| Optuna | 4.8.0 | Hyperparameter tuning | Define-by-run API makes it easy to tune XGBoost/LightGBM/RF hyperparameters. Use `optuna.integration.XGBoostPruningCallback` for early stopping during search. Superior to GridSearchCV for boosting models where search space is large. |
| joblib | 1.5.3 | Model serialization and persistence | Save trained models to disk. Scikit-learn's recommended serialization. Use `joblib.dump()` and `joblib.load()` for all models including XGBoost wrapped in sklearn pipelines. |

**Confidence:**
- scikit-learn 1.8 temperature scaling: HIGH -- verified in official release highlights and documentation.
- XGBoost over LightGBM recommendation: MEDIUM -- both are excellent. XGBoost is recommended based on ecosystem fit and documentation quality, not a decisive technical advantage.
- SHAP 0.51.0: HIGH -- verified on PyPI.
- Optuna 4.8.0: HIGH -- verified on PyPI.

### Visualization & Reporting

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| JupyterLab | 4.5.6 | Interactive notebook environment | Primary interface per project requirements. JupyterLab 4.5.6 (Mar 2026) is stable. Use over classic Jupyter Notebook for the multi-tab interface and built-in terminal. |
| matplotlib | 3.10.8 | Static plots, calibration curves, Brier score charts | The baseline visualization library. Required by SHAP and seaborn. Use for publication-quality calibration reliability diagrams. |
| seaborn | 0.13.2 | Statistical visualizations | Built on matplotlib. Use `sns.heatmap()` for correlation matrices, `sns.kdeplot()` for probability distributions. Cleaner defaults than raw matplotlib. |
| plotly | 6.5.2 | Interactive charts in notebooks | Use for interactive model comparison dashboards within Jupyter. Hover-over game details, clickable calibration curves. Not essential but significantly improves the notebook reporting experience. |

**Confidence:** HIGH for all -- versions verified on PyPI.

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tqdm | 4.67+ | Progress bars | Wrap long-running pybaseball Statcast downloads and backtesting loops. `from tqdm.notebook import tqdm` for Jupyter integration. |
| python-dotenv | 1.0+ | Environment variable management | Store Kalshi API credentials (API key path, key ID) in `.env` file. Never hardcode credentials. |
| cryptography | 43+ | RSA key handling for Kalshi auth | Required by Kalshi API for RSA-PSS signature generation. Installed as kalshi-python dependency but pin explicitly. |
| beautifulsoup4 | 4.12+ | HTML parsing fallback | Only if pybaseball scraping breaks against Baseball Reference or FanGraphs. Direct scraping backup. |

**Confidence:** HIGH -- standard, stable libraries.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| MLB Stats API client | MLB-StatsAPI (toddrob99) | python-mlb-statsapi (zero-sum-seattle) | python-mlb-statsapi (0.7.2, Feb 2026) uses Pydantic models and is more modern, but MLB-StatsAPI has a larger user base, more examples, and a well-documented wiki. For schedule/roster lookups, simplicity wins. |
| Gradient boosting | XGBoost | CatBoost | CatBoost handles categorical features well but MLB data is mostly numeric (stats, rates). No advantage here, and CatBoost has fewer sports analytics examples. |
| Kalshi client | kalshi-python (official) | kalshi-py (community) | kalshi-py is auto-built from OpenAPI spec daily and may be more up-to-date, but the official SDK has Kalshi's direct support for issues. Use official first, fall back to kalshi-py if gaps found. |
| Pandas version | pandas 2.2.3 | pandas 3.0.1 | Pandas 3.0 changes default string dtype to PyArrow-backed, which breaks downstream code expecting object dtype. pybaseball returns object-dtype DataFrames. Migration cost is not worth it for this project. |
| Hyperparameter tuning | Optuna | sklearn GridSearchCV | GridSearchCV is simpler but Optuna's pruning callbacks for XGBoost (early stopping bad trials) make it dramatically more efficient for boosting hyperparameter search. |
| Notebook | JupyterLab | VS Code Notebooks | VS Code notebooks work well but JupyterLab's dedicated interface is better for the iterative data science workflow and sharing results. Project spec explicitly calls for Jupyter. |

---

## What NOT to Use

| Technology | Why Avoid |
|------------|-----------|
| pandas 3.0.x | Breaking string dtype changes will cause issues with pybaseball DataFrames and downstream code. Wait for pybaseball to update. |
| numpy 2.4.x | Requires Python 3.11+ minimum and pairs with pandas 3.x. Use numpy 2.2.x with pandas 2.2.x for stability. |
| TensorFlow / PyTorch | Massive overkill for tabular data with ~12K rows. Gradient boosting dominates this problem space. Neural networks need orders of magnitude more data to outperform XGBoost on structured tabular data this size. |
| statsmodels (as primary) | Useful for statistical tests but not for prediction pipelines. scikit-learn's API is better for train/test/evaluate workflows. |
| Apache Spark / Dask | Dataset is small (~12K rows for 5-season backtest). Pandas handles this trivially. Distributed computing adds complexity with zero benefit. |
| Streamlit / Dash | Project explicitly scopes to Jupyter notebooks. Adding a web framework is out of scope and premature. |

---

## Installation

```bash
# Create virtual environment
python -m venv .venv
# Activate (Windows Git Bash)
source .venv/Scripts/activate

# Core data ingestion
pip install "pybaseball>=2.2.7" "MLB-StatsAPI>=1.9.0" "kalshi-python>=2.1.4"

# Data processing
pip install "pandas>=2.2.3,<3.0" "numpy>=2.2.0,<2.4" "scipy>=1.14"

# Machine learning
pip install "scikit-learn>=1.8.0" "xgboost>=3.2.0" "lightgbm>=4.6.0"
pip install "shap>=0.51.0" "optuna>=4.8.0" "joblib>=1.5.3"

# Visualization & notebooks
pip install "jupyterlab>=4.5.0" "matplotlib>=3.10.0" "seaborn>=0.13.2" "plotly>=6.5.0"

# Supporting
pip install "tqdm>=4.67" "python-dotenv>=1.0" "cryptography>=43"

# Development
pip install "pytest>=8.0" "black>=24.0" "ruff>=0.8"
```

### requirements.txt (pinned for reproducibility)

```
# Data ingestion
pybaseball==2.2.7
MLB-StatsAPI==1.9.0
kalshi-python==2.1.4
requests>=2.32

# Data processing
pandas>=2.2.3,<3.0
numpy>=2.2.0,<2.4
scipy>=1.14

# Machine learning
scikit-learn>=1.8.0
xgboost>=3.2.0
lightgbm>=4.6.0
shap>=0.51.0
optuna>=4.8.0
joblib>=1.5.3

# Visualization
jupyterlab>=4.5.0
matplotlib>=3.10.0
seaborn>=0.13.2
plotly>=6.5.0

# Utilities
tqdm>=4.67
python-dotenv>=1.0
cryptography>=43
beautifulsoup4>=4.12

# Dev
pytest>=8.0
black>=24.0
ruff>=0.8
```

---

## Key Version Constraints Summary

```
Python 3.12 (recommended)
  |
  +-- pandas 2.2.x (NOT 3.0 -- avoids PyArrow string dtype breaking changes)
  |     +-- numpy 2.2.x (compatible pair)
  |
  +-- scikit-learn 1.8.0 (temperature scaling calibration)
  |     +-- XGBoost 3.2.0 (sklearn API)
  |     +-- LightGBM 4.6.0 (sklearn API)
  |
  +-- pybaseball 2.2.7 (returns pandas DataFrames with object dtype)
  +-- MLB-StatsAPI 1.9.0 (schedule, roster, pitcher confirmation)
  +-- kalshi-python 2.1.4 (RSA-PSS auth, market data)
```

The critical constraint: **pandas 2.2.x + numpy 2.2.x** is the stable foundation. Everything else plugs in cleanly.

---

## Sources

- [pybaseball PyPI](https://pypi.org/project/pybaseball/) -- v2.2.7, Sep 2023
- [MLB-StatsAPI PyPI](https://pypi.org/project/MLB-StatsAPI/) -- v1.9.0, Apr 2025
- [kalshi-python PyPI](https://pypi.org/project/kalshi-python/) -- v2.1.4, Sep 2025
- [pandas 3.0 migration guide](https://pandas.pydata.org/docs/user_guide/migration-3-strings.html) -- breaking string dtype changes
- [scikit-learn 1.8 release highlights](https://scikit-learn.org/stable/auto_examples/release_highlights/plot_release_highlights_1_8_0.html) -- temperature scaling
- [XGBoost 3.2.0 release notes](https://xgboost.readthedocs.io/en/stable/changes/index.html)
- [LightGBM 4.6.0 docs](https://lightgbm.readthedocs.io/)
- [SHAP PyPI](https://pypi.org/project/shap/) -- v0.51.0, Mar 2026
- [Optuna PyPI](https://pypi.org/project/optuna/) -- v4.8.0
- [Kalshi API docs](https://docs.kalshi.com/python-sdk) -- RSA-PSS authentication
- [python-mlb-statsapi PyPI](https://pypi.org/project/python-mlb-statsapi/) -- v0.7.2, Feb 2026 (considered, not recommended)
- [joblib PyPI](https://pypi.org/project/joblib/) -- v1.5.3, Dec 2025
- [JupyterLab PyPI](https://pypi.org/project/jupyterlab/) -- v4.5.6, Mar 2026
- [plotly PyPI](https://pypi.org/project/plotly/) -- v6.5.2, Jan 2026
