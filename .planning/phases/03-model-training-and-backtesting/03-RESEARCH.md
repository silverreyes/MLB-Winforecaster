# Phase 3: Model Training and Backtesting - Research

**Researched:** 2026-03-29
**Domain:** scikit-learn/XGBoost model training, isotonic calibration, walk-forward backtesting, Brier score evaluation
**Confidence:** HIGH

## Summary

Phase 3 trains three probability-calibrated models (logistic regression, random forest, XGBoost) on the feature matrix built in Phase 2, evaluates them via walk-forward backtesting across 5 seasonal folds, and presents side-by-side comparisons in a dedicated notebook. The feature matrix is already saved at `data/features/feature_matrix.parquet` with 22,714 games across 2015-2024, and all required ML libraries (scikit-learn 1.8.0, XGBoost 2.1.4, matplotlib 3.10.8, seaborn 0.13.2) are already installed.

The most critical technical finding is that **scikit-learn 1.8.0 removed `cv='prefit'` from `CalibratedClassifierCV`**. The CONTEXT.md specifies `CalibratedClassifierCV(cv="prefit", method="isotonic")`, but this will raise `InvalidParameterError` on the installed version. The correct replacement is either `FrozenEstimator` wrapping (added in sklearn 1.5) or direct `IsotonicRegression`. Research recommends `IsotonicRegression(out_of_bounds='clip')` applied directly to base model probabilities, as it provides the cleanest implementation for the explicit train/calibrate/test fold structure described in the CONTEXT.md.

The feature matrix has meaningful NaN patterns that drive the two-feature-set design: `xwoba_diff` is 100% NaN (Statcast data not loaded) making it useless for modeling, while SP pitcher stats (`sp_fip_diff` etc.) are ~83% available and `sp_recent_era_diff` is ~89% available. The "full feature set" requires median imputation for LR/RF (XGBoost handles NaN natively). The "Statcast-safe set" drops `xwoba_diff` and `sp_recent_era_diff`, leaving features with higher completeness that still require imputation for SP stats.

**Primary recommendation:** Use `sklearn.isotonic.IsotonicRegression(out_of_bounds='clip')` instead of `CalibratedClassifierCV(cv='prefit')` for post-hoc isotonic calibration. Wrap all LR/RF preprocessing in `sklearn.pipeline.Pipeline` to prevent data leakage. Store per-game predictions with join keys for Phase 4.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Walk-forward split design:** Expanding window with train 2015..N-2, calibrate N-1, test N. Folds for N = 2019, 2021, 2022, 2023, 2024 (2020 skipped as test year). 2020 included in training sets only.
- **Early-season games:** Games 1-9 per team per season (where `rolling_ops_diff` is NaN) dropped from both training and test sets entirely. No imputation.
- **Calibration mechanics:** Post-hoc isotonic calibration applied after base model is trained. Per-fold pipeline: train on N-2, fit isotonic on N-1, evaluate on N. Calibration re-run per fold. 2020 calibration season constraint: all calibration logic must be data-length-agnostic.
- **Notebook structure:** Two notebooks -- `09_model_training.ipynb` (runs models, saves results) and `10_model_comparison.ipynb` (loads results, displays comparisons). Results persisted to `data/results/backtest_results.parquet`.
- **NaN handling:** Two feature sets (full with imputation, Statcast-safe without). LR pipeline: StandardScaler -> SimpleImputer(median) -> LogisticRegression. RF: SimpleImputer(median) -> RandomForestClassifier. XGBoost: native NaN handling on full set, no imputation on safe set.
- **Code structure:** Model and backtest logic in `src/models/` following thin-notebook pattern from Phase 1/2.

### Claude's Discretion
- Exact hyperparameters for RF (n_estimators, max_depth, min_samples_leaf)
- XGBoost early stopping: validation set is last 20% of training window (temporally ordered)
- Exact column names for the Statcast-safe feature set
- data/results/ subdirectory structure and exact Parquet schema
- Calibration curve binning (number of bins for reliability diagrams)
- Per-season accuracy metric definition

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MODEL-01 | Logistic regression as interpretable baseline and calibration anchor | LR pipeline pattern verified: StandardScaler -> SimpleImputer -> LogisticRegression via sklearn.pipeline.Pipeline. max_iter=500 recommended for convergence with scaled features. |
| MODEL-02 | Random forest as ensemble comparison benchmark | RF pipeline: SimpleImputer -> RandomForestClassifier. Recommended: n_estimators=300, max_depth=8, min_samples_leaf=20 for ~12K-row tabular data. |
| MODEL-03 | XGBoost with aggressive regularization and early stopping | XGBClassifier verified: max_depth=4, learning_rate=0.05, reg_alpha=1.0, reg_lambda=2.0, subsample=0.8, early_stopping_rounds=20. NaN handling confirmed working on sklearn 1.8.0 + xgboost 2.1.4. |
| MODEL-04 | Probability calibration via CalibratedClassifierCV | **CRITICAL API CHANGE:** cv='prefit' removed in sklearn 1.8.0. Use IsotonicRegression(out_of_bounds='clip') directly on base model predict_proba output. Verified working. |
| EVAL-01 | Walk-forward backtesting (train seasons 1..N, predict N+1) | 5 folds defined: test years 2019, 2021, 2022, 2023, 2024. Expanding window with calibration season. ~1,700-2,000 complete rows per test fold depending on feature set. |
| EVAL-02 | Brier score per model, per season, and aggregate | sklearn.metrics.brier_score_loss verified. Signature: brier_score_loss(y_true, y_proba). Returns mean squared error between predicted probability and actual outcome. |
| EVAL-03 | Calibration curves (reliability diagrams) per model | sklearn.calibration.calibration_curve verified. Params: n_bins (recommend 10), strategy='uniform'. Matplotlib plotting for reliability diagrams. |
| EVAL-04 | Side-by-side model comparison notebook | Notebook 10 loads saved results from data/results/backtest_results.parquet. Standalone execution without re-training. Both feature sets compared. |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| scikit-learn | 1.8.0 (installed) | LR, RF, Pipeline, StandardScaler, SimpleImputer, calibration_curve, brier_score_loss, IsotonicRegression | Industry standard for tabular ML; Pipeline prevents data leakage |
| xgboost | 2.1.4 (installed) | XGBClassifier with native NaN handling, early stopping | Best-in-class gradient boosting; handles missing values natively |
| pandas | 2.2.3 (pinned) | DataFrame manipulation, Parquet I/O, groupby for walk-forward splits | Hard pinned per project constraints (pybaseball incompatible with 3.0) |
| matplotlib | 3.10.8 (installed) | Calibration curves, comparison charts | Standard plotting; already used in notebook 08 |
| seaborn | 0.13.2 (installed) | Heatmaps, styled plots | Already used in notebook 08 for feature exploration |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| numpy | 2.4.3 (installed) | Array operations, NaN handling | Used throughout for numerical computation |
| pyarrow | >=15.0.0 (installed) | Parquet read/write engine | Already used for feature matrix I/O |
| pytest | 8.1.1 (installed) | Unit testing for model modules | Wave 0 test infrastructure for walk-forward logic |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| IsotonicRegression (direct) | FrozenEstimator + CalibratedClassifierCV | FrozenEstimator works but adds CV splitting on calibration data, which is unnecessary when we explicitly provide the calibration season. Direct isotonic is simpler and matches the CONTEXT.md intent exactly. |
| SimpleImputer(median) | IterativeImputer, KNNImputer | Median imputation is fast, interpretable, and appropriate for ~17% missingness in SP stats. Advanced imputers add complexity without clear benefit at this scale. |

**All packages already installed.** No new `pip install` required.

## Architecture Patterns

### Recommended Project Structure
```
src/
  models/
    __init__.py
    backtest.py         # Walk-forward backtest loop, fold generation
    train.py            # Model factory functions (LR, RF, XGB pipelines)
    calibrate.py        # IsotonicRegression wrapper for post-hoc calibration
    evaluate.py         # Brier score, calibration curves, comparison metrics
    feature_sets.py     # Feature column definitions (full vs Statcast-safe)

data/
  results/
    backtest_results.parquet   # Per-game predictions for all models, all folds

notebooks/
  09_model_training.ipynb      # Thin wrapper: calls src/models/, saves results
  10_model_comparison.ipynb    # Loads saved results, displays comparisons
```

### Pattern 1: Walk-Forward Fold Generator
**What:** Generate train/calibrate/test splits by season, respecting the explicit fold map.
**When to use:** Every backtest iteration.
**Example:**
```python
# Source: CONTEXT.md locked decision + verified feature matrix
FOLD_MAP = [
    # (test_year, train_seasons, calibration_season)
    (2019, list(range(2015, 2018)), 2018),
    (2021, list(range(2015, 2020)), 2020),
    (2022, list(range(2015, 2021)), 2021),
    (2023, list(range(2015, 2022)), 2022),
    (2024, list(range(2015, 2023)), 2023),
]

def generate_folds(df: pd.DataFrame) -> list[tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]]:
    """Yield (train_df, cal_df, test_df) for each fold.

    Drops early-season NaN rows (rolling_ops_diff is NaN) from all splits.
    """
    df_clean = df[df["rolling_ops_diff"].notna()].copy()
    folds = []
    for test_year, train_years, cal_year in FOLD_MAP:
        train_df = df_clean[df_clean["season"].isin(train_years)]
        cal_df = df_clean[df_clean["season"] == cal_year]
        test_df = df_clean[df_clean["season"] == test_year]
        folds.append((train_df, cal_df, test_df))
    return folds
```

### Pattern 2: Calibration via Direct IsotonicRegression
**What:** Post-hoc isotonic calibration replacing deprecated cv='prefit'.
**When to use:** After training each base model, before evaluation.
**Example:**
```python
# Source: sklearn 1.8.0 verified API
from sklearn.isotonic import IsotonicRegression

def calibrate_model(model, X_cal, y_cal, X_test):
    """Apply isotonic calibration to a pre-trained model.

    Args:
        model: Fitted sklearn Pipeline or estimator with predict_proba
        X_cal: Calibration features (season N-1)
        y_cal: Calibration labels (season N-1)
        X_test: Test features to produce calibrated predictions for

    Returns:
        Calibrated probability array for X_test
    """
    raw_probs_cal = model.predict_proba(X_cal)[:, 1]
    iso = IsotonicRegression(out_of_bounds='clip')
    iso.fit(raw_probs_cal, y_cal)

    raw_probs_test = model.predict_proba(X_test)[:, 1]
    return iso.predict(raw_probs_test)
```

### Pattern 3: Model Factory with Pipeline Wrapping
**What:** Create sklearn Pipelines that encapsulate preprocessing to prevent leakage.
**When to use:** For LR and RF models that need imputation/scaling.
**Example:**
```python
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
import xgboost as xgb

def make_lr_pipeline() -> Pipeline:
    return Pipeline([
        ('scaler', StandardScaler()),
        ('imputer', SimpleImputer(strategy='median')),
        ('clf', LogisticRegression(max_iter=500, random_state=42)),
    ])

def make_rf_pipeline() -> Pipeline:
    return Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('clf', RandomForestClassifier(
            n_estimators=300, max_depth=8, min_samples_leaf=20,
            random_state=42, n_jobs=-1,
        )),
    ])

def make_xgb_model() -> xgb.XGBClassifier:
    return xgb.XGBClassifier(
        n_estimators=500,
        max_depth=4,
        learning_rate=0.05,
        reg_alpha=1.0,
        reg_lambda=2.0,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=3,
        early_stopping_rounds=20,
        eval_metric='logloss',
        random_state=42,
        n_jobs=-1,
    )
```

### Pattern 4: XGBoost Early Stopping with Temporal Validation
**What:** Use last 20% of training window (by date) as validation set.
**When to use:** XGBoost training only.
**Example:**
```python
def fit_xgb_with_early_stopping(model, X_train, y_train, feature_cols):
    """Fit XGBoost with temporal early stopping validation.

    Last 20% of training data (by temporal order) used as validation set.
    """
    n_val = int(len(X_train) * 0.2)
    X_tr = X_train.iloc[:-n_val][feature_cols]
    y_tr = y_train.iloc[:-n_val]
    X_val = X_train.iloc[-n_val:][feature_cols]
    y_val = y_train.iloc[-n_val:]

    model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)
    return model
```

### Pattern 5: Results Persistence for Standalone Comparison Notebook
**What:** Save per-game predictions to Parquet with Phase 4 join keys.
**When to use:** After all folds complete in notebook 09.
**Example:**
```python
# Each row: one game prediction from one model in one fold
results_schema = {
    'game_date': 'datetime64[ns]',   # Phase 4 join key
    'home_team': 'str',               # Phase 4 join key
    'away_team': 'str',               # Phase 4 join key
    'season': 'int',                  # For per-season grouping
    'home_win': 'int',                # Actual outcome
    'model_name': 'str',              # 'lr', 'rf', 'xgb'
    'feature_set': 'str',             # 'full', 'statcast_safe'
    'fold_test_year': 'int',          # Which fold this prediction belongs to
    'prob_calibrated': 'float',       # Isotonic-calibrated probability
    'prob_raw': 'float',              # Uncalibrated base model probability
}
```

### Anti-Patterns to Avoid
- **Random splits anywhere:** sklearn's default `shuffle=True` silently corrupts evaluation. All splits must be by season. Never use `train_test_split` with shuffle.
- **Fitting scaler/imputer on full dataset:** StandardScaler and SimpleImputer must be fit ONLY on training data. Pipeline handles this automatically when you call `pipeline.fit(X_train, y_train)`.
- **Using CalibratedClassifierCV(cv='prefit'):** Removed in sklearn 1.8.0. Will raise `InvalidParameterError`.
- **Calibrating on test data:** Calibration season (N-1) must be strictly separate from test season (N). Never calibrate on the same data you evaluate.
- **Hardcoding game count assertions:** The 2020 calibration fold has ~727 games (vs ~2,200 for full seasons). All logic must be data-length-agnostic.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Feature scaling + imputation pipeline | Manual transform/inverse-transform chains | `sklearn.pipeline.Pipeline` | Prevents leakage, handles fit/transform lifecycle automatically |
| Brier score computation | Manual `mean((p - y)^2)` | `sklearn.metrics.brier_score_loss` | Handles edge cases, consistent with literature |
| Calibration curve binning | Manual binning and averaging | `sklearn.calibration.calibration_curve` | Correct handling of bin boundaries and fraction computation |
| Isotonic regression | Custom monotone interpolation | `sklearn.isotonic.IsotonicRegression` | Handles out-of-bounds, ties, edge cases |
| Parquet I/O | CSV or pickle serialization | `pandas.DataFrame.to_parquet` with pyarrow engine | Typed columns, compression, fast reads |

**Key insight:** The sklearn ecosystem provides well-tested implementations for every statistical operation in this phase. The only custom code should be the walk-forward fold loop, feature set definitions, and the orchestration connecting these components.

## Common Pitfalls

### Pitfall 1: Data Leakage via Imputation Scope
**What goes wrong:** SimpleImputer or StandardScaler is fit on the entire dataset (including calibration and test seasons), then applied to training data. Median values from future seasons leak into training features.
**Why it happens:** Easy to call `imputer.fit_transform(X_all)` before splitting.
**How to avoid:** Use `sklearn.pipeline.Pipeline` which enforces fit on training split only. `pipeline.fit(X_train, y_train)` fits all transformers on X_train; `pipeline.predict_proba(X_test)` applies the training-fit transformers to X_test.
**Warning signs:** Unrealistically good Brier scores in early folds (e.g., 2019 fold outperforming later folds).

### Pitfall 2: XGBoost Early Stopping Using Calibration Season
**What goes wrong:** The calibration season (N-1) is used as the XGBoost eval_set for early stopping, contaminating the calibration step.
**Why it happens:** Conceptual confusion between "validation for hyperparameter selection" and "calibration for probability adjustment."
**How to avoid:** Early stopping uses last 20% of the TRAINING window (temporally ordered). Calibration season is reserved exclusively for isotonic regression fitting.
**Warning signs:** Calibration curves show unusual patterns in folds where the calibration season overlaps with XGBoost validation data.

### Pitfall 3: Isotonic Calibration Overfitting on Small Calibration Sets
**What goes wrong:** Isotonic regression on the 2020 calibration fold (~727 rows) produces a step function with too many jumps, causing erratic probability predictions.
**Why it happens:** Isotonic regression is non-parametric and can overfit small samples.
**How to avoid:** With ~727 games, isotonic should still work acceptably. Monitor calibration curves for the 2021 fold (which uses 2020 as calibration). If problematic, sigmoid calibration is the fallback for this specific fold.
**Warning signs:** 2021 fold calibration curve looks markedly worse than other folds.

### Pitfall 4: xwoba_diff Column Confusion
**What goes wrong:** Including `xwoba_diff` in the "full feature set" even though it's 100% NaN (object dtype, all None values). Imputation creates a constant column; XGBoost ignores it but LR/RF waste a feature slot on noise.
**Why it happens:** CONTEXT.md mentions xwOBA as a Statcast feature, but the actual data has 0% coverage.
**How to avoid:** Explicitly exclude `xwoba_diff` from ALL feature sets. The "full" vs "Statcast-safe" distinction applies to `sp_recent_era_diff` (89% coverage) and the SP stat columns. `xwoba_diff` provides no information.
**Warning signs:** Feature importance for xwoba_diff shows non-zero importance in RF/XGBoost (artifact of imputed constant value).

### Pitfall 5: Inconsistent NaN Dropping Between Feature Sets
**What goes wrong:** The Statcast-safe set drops `sp_recent_era_diff` but still has NaN in SP stats (`sp_fip_diff` etc. at 83%). If the code expects "no imputation needed" for the safe set, it will encounter NaN.
**Why it happens:** CONTEXT.md says "All models train on complete rows, no imputation needed" for the Statcast-safe set, but SP stat NaN comes from FanGraphs name-matching failures, not Statcast.
**How to avoid:** For the Statcast-safe set, either (a) still use imputation for SP stats, or (b) drop rows with any NaN in the selected feature columns. Research recommends option (a) -- impute SP stats even in the Statcast-safe set -- because dropping 17% of rows per season significantly reduces training data.
**Warning signs:** Training set sizes differ wildly between full and Statcast-safe sets when they should be similar (both should have ~same row count with imputation).

### Pitfall 6: LogisticRegression max_iter Too Low
**What goes wrong:** Default `max_iter=100` causes `ConvergenceWarning` with StandardScaler'd features on ~10K rows.
**Why it happens:** sklearn 1.8.0 changed the default penalty from 'l2' to deprecated, and lbfgs solver may need more iterations.
**How to avoid:** Set `max_iter=500` explicitly.
**Warning signs:** `ConvergenceWarning: lbfgs failed to converge` in training output.

## Code Examples

### Feature Set Definitions
```python
# Source: feature_matrix.parquet column analysis (verified 2026-03-29)

# All available differential feature columns
ALL_FEATURE_COLS = [
    'sp_fip_diff',        # FanGraphs SP stats (83.1% coverage)
    'sp_xfip_diff',       # FanGraphs SP stats (83.1% coverage)
    'sp_k_pct_diff',      # FanGraphs SP stats (83.1% coverage)
    'sp_siera_diff',      # FanGraphs SP stats (83.1% coverage)
    'team_woba_diff',     # FanGraphs team batting (100% coverage)
    'team_ops_diff',      # FanGraphs team batting (100% coverage)
    'pyth_win_pct_diff',  # Derived from schedule (100% coverage)
    'rolling_ops_diff',   # Game logs (100% after NaN-row drop)
    'bullpen_era_diff',   # FanGraphs pitching (100% coverage)
    'bullpen_fip_diff',   # FanGraphs pitching (100% coverage)
    'is_home',            # Always 1 (100% coverage)
    'park_factor',        # Static lookup (100% coverage)
    'sp_recent_era_diff', # MLB Stats API game logs (89.4% coverage)
    'log5_home_wp',       # Derived from win records (100% coverage)
]

# Full feature set: all columns, imputation for NaN
FULL_FEATURE_COLS = ALL_FEATURE_COLS  # Same as all; xwoba_diff excluded (0% coverage)

# Statcast-safe set: exclude sp_recent_era_diff (uses pitching date ranges)
# Note: xwoba_diff already excluded from ALL_FEATURE_COLS since it's 100% NaN
STATCAST_SAFE_COLS = [c for c in ALL_FEATURE_COLS if c != 'sp_recent_era_diff']

# Target column
TARGET_COL = 'home_win'

# Join keys preserved for Phase 4
JOIN_KEYS = ['game_date', 'home_team', 'away_team']

# Metadata columns needed for splitting
META_COLS = ['season', 'home_win', 'game_date', 'home_team', 'away_team']
```

### Complete Backtest Loop
```python
# Source: Verified against sklearn 1.8.0 + xgboost 2.1.4 APIs
from sklearn.metrics import brier_score_loss
from sklearn.isotonic import IsotonicRegression

def run_backtest(df, model_factory, model_name, feature_cols,
                 is_xgb=False):
    """Run walk-forward backtest for one model across all folds.

    Returns list of per-game prediction dicts.
    """
    results = []
    df_clean = df[df['rolling_ops_diff'].notna()].copy()

    for test_year, train_years, cal_year in FOLD_MAP:
        train_df = df_clean[df_clean['season'].isin(train_years)]
        cal_df = df_clean[df_clean['season'] == cal_year]
        test_df = df_clean[df_clean['season'] == test_year]

        X_train = train_df[feature_cols]
        y_train = train_df[TARGET_COL]
        X_cal = cal_df[feature_cols]
        y_cal = cal_df[TARGET_COL]
        X_test = test_df[feature_cols]
        y_test = test_df[TARGET_COL]

        # Train base model
        model = model_factory()
        if is_xgb:
            # Early stopping on last 20% of training window
            n_val = int(len(X_train) * 0.2)
            model.fit(
                X_train.iloc[:-n_val], y_train.iloc[:-n_val],
                eval_set=[(X_train.iloc[-n_val:], y_train.iloc[-n_val:])],
                verbose=False,
            )
        else:
            model.fit(X_train, y_train)

        # Calibrate on season N-1
        raw_cal = model.predict_proba(X_cal)[:, 1]
        iso = IsotonicRegression(out_of_bounds='clip')
        iso.fit(raw_cal, y_cal.values)

        # Predict on test season
        raw_test = model.predict_proba(X_test)[:, 1]
        cal_test = iso.predict(raw_test)

        # Collect per-game results
        for i, (_, row) in enumerate(test_df.iterrows()):
            results.append({
                'game_date': row['game_date'],
                'home_team': row['home_team'],
                'away_team': row['away_team'],
                'season': row['season'],
                'home_win': row['home_win'],
                'model_name': model_name,
                'feature_set': 'full' if 'sp_recent_era_diff' in feature_cols else 'statcast_safe',
                'fold_test_year': test_year,
                'prob_calibrated': cal_test[i],
                'prob_raw': raw_test[i],
            })

    return results
```

### Reliability Diagram
```python
# Source: sklearn.calibration.calibration_curve (verified 1.8.0 API)
from sklearn.calibration import calibration_curve
import matplotlib.pyplot as plt

def plot_calibration_curves(results_df, model_names, n_bins=10):
    """Plot reliability diagrams for multiple models."""
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.plot([0, 1], [0, 1], 'k--', label='Perfectly calibrated')

    for name in model_names:
        mask = results_df['model_name'] == name
        y_true = results_df.loc[mask, 'home_win']
        y_prob = results_df.loc[mask, 'prob_calibrated']

        fraction_positive, mean_predicted = calibration_curve(
            y_true, y_prob, n_bins=n_bins, strategy='uniform'
        )
        ax.plot(mean_predicted, fraction_positive, 's-', label=name)

    ax.set_xlabel('Mean predicted probability')
    ax.set_ylabel('Fraction of positives')
    ax.set_title('Calibration Curves (Reliability Diagram)')
    ax.legend()
    return fig
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `CalibratedClassifierCV(cv='prefit')` | `FrozenEstimator` or direct `IsotonicRegression` | sklearn 1.5 (FrozenEstimator added), 1.8 (cv='prefit' removed) | **Must use new API** -- old approach raises InvalidParameterError |
| `LogisticRegression(penalty='l2')` | `LogisticRegression()` (penalty deprecated in 1.8) | sklearn 1.8.0 | Default solver is lbfgs, default penalty is internally l2 but parameter is deprecated. Set max_iter=500. |
| `XGBClassifier(use_label_encoder=False)` | `XGBClassifier()` (parameter removed) | xgboost 2.0+ | `use_label_encoder` is no longer a valid parameter; passing it triggers a warning |

**Deprecated/outdated:**
- `cv='prefit'` in CalibratedClassifierCV: removed in sklearn 1.8.0. Use `FrozenEstimator` wrapping or direct `IsotonicRegression`.
- `penalty='l2'` in LogisticRegression: deprecated in sklearn 1.8.0. The default behavior still applies L2 but the parameter name will be removed in a future version. Simply omit it.
- `use_label_encoder=False` in XGBClassifier: no longer needed in xgboost 2.x.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.1.1 |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `python -m pytest tests/test_backtest.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MODEL-01 | LR pipeline trains and produces probabilities | unit | `python -m pytest tests/test_models.py::test_lr_pipeline_trains -x` | No -- Wave 0 |
| MODEL-02 | RF pipeline trains and produces probabilities | unit | `python -m pytest tests/test_models.py::test_rf_pipeline_trains -x` | No -- Wave 0 |
| MODEL-03 | XGBoost trains with early stopping and handles NaN | unit | `python -m pytest tests/test_models.py::test_xgb_early_stopping -x` | No -- Wave 0 |
| MODEL-04 | Isotonic calibration produces valid probabilities [0,1] | unit | `python -m pytest tests/test_models.py::test_isotonic_calibration -x` | No -- Wave 0 |
| EVAL-01 | Walk-forward fold generator produces correct splits (no overlap) | unit | `python -m pytest tests/test_backtest.py::test_fold_splits_no_overlap -x` | No -- Wave 0 |
| EVAL-01 | 2020 never appears as test year | unit | `python -m pytest tests/test_backtest.py::test_2020_not_test_year -x` | No -- Wave 0 |
| EVAL-01 | Early-season NaN rows excluded from all splits | unit | `python -m pytest tests/test_backtest.py::test_nan_rows_excluded -x` | No -- Wave 0 |
| EVAL-02 | Brier score computed correctly per fold | unit | `python -m pytest tests/test_backtest.py::test_brier_score_per_fold -x` | No -- Wave 0 |
| EVAL-03 | Calibration curve data generated | unit | `python -m pytest tests/test_models.py::test_calibration_curve_output -x` | No -- Wave 0 |
| EVAL-04 | Results Parquet contains all required columns and join keys | unit | `python -m pytest tests/test_backtest.py::test_results_schema -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_backtest.py tests/test_models.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_backtest.py` -- covers EVAL-01, EVAL-02, EVAL-04 (fold generation, Brier score, results schema)
- [ ] `tests/test_models.py` -- covers MODEL-01 through MODEL-04, EVAL-03 (model factories, calibration, curves)
- [ ] No new conftest fixtures needed -- existing `conftest.py` mock_cache_dir can be extended if results saving uses cache

## Open Questions

1. **xwoba_diff at 0% coverage**
   - What we know: The `xwoba_diff` column is object dtype, all None values. Statcast data was fetched but xwOBA join appears to have failed.
   - What's unclear: Whether this is a Phase 2 bug or intentional (Statcast pitcher data format mismatch).
   - Recommendation: Exclude `xwoba_diff` from all feature sets. It provides zero information. If the user wants to investigate, it's a Phase 2 fix, not a Phase 3 concern. The "full" vs "Statcast-safe" feature set comparison should focus on `sp_recent_era_diff` as the differentiating feature.

2. **Imputation strategy for Statcast-safe set**
   - What we know: CONTEXT.md says "All models train on complete rows, no imputation needed" for the Statcast-safe set. But SP stat columns (sp_fip_diff, etc.) still have ~17% NaN from FanGraphs name-matching failures.
   - What's unclear: Whether the user intended "no imputation" to mean "drop incomplete rows" or "these columns won't have NaN."
   - Recommendation: Apply median imputation to SP stat columns in BOTH feature sets. The SP stat NaN is from FanGraphs name matching, not Statcast. Dropping 17% of rows loses significant training signal. If strict adherence to "no imputation" is required, drop rows with any NaN in the selected columns.

3. **Practical impact of LogisticRegression penalty deprecation**
   - What we know: sklearn 1.8.0 deprecated the `penalty` parameter. Default behavior is still L2 regularization.
   - What's unclear: Whether this will produce deprecation warnings in output.
   - Recommendation: Omit `penalty` parameter entirely. If a warning appears, it can be suppressed with `warnings.filterwarnings`.

## Sources

### Primary (HIGH confidence)
- **scikit-learn 1.8.0** -- installed locally, all API signatures verified via `inspect.signature()` and functional testing
- **xgboost 2.1.4** -- installed locally, NaN handling and early stopping verified via functional testing
- **Feature matrix** -- `data/features/feature_matrix.parquet` inspected directly: 22,714 rows, 52 columns, column dtypes and NaN patterns verified
- **CONTEXT.md** -- locked decisions define fold structure, calibration mechanics, feature sets, notebook structure

### Secondary (MEDIUM confidence)
- **sklearn deprecation timeline** -- `cv='prefit'` removal confirmed via runtime `InvalidParameterError` on sklearn 1.8.0. FrozenEstimator replacement confirmed working via functional test.
- **Hyperparameter recommendations** (RF: n_estimators=300, max_depth=8; XGB: max_depth=4, lr=0.05) -- based on standard practices for ~12K-row tabular binary classification. Reasonable defaults that can be tuned.

### Tertiary (LOW confidence)
- **Isotonic vs sigmoid calibration on small samples** -- the claim that isotonic works at ~727 rows (2020 season) is based on general ML knowledge. May need empirical validation on this specific dataset.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all packages installed and version-verified locally
- Architecture: HIGH -- patterns verified against actual API signatures and functional tests; fold structure explicit from CONTEXT.md
- Pitfalls: HIGH -- cv='prefit' removal confirmed empirically; NaN patterns verified from actual data
- Hyperparameters: MEDIUM -- reasonable defaults for problem scale, not empirically tuned
- xwoba_diff handling: HIGH -- 0% coverage confirmed from data inspection

**Research date:** 2026-03-29
**Valid until:** 2026-04-28 (30 days -- stable ML stack, no fast-moving dependencies)
