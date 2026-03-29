# Phase 6: Model Retrain and Calibration - Research

**Researched:** 2026-03-29
**Domain:** ML model training, calibration, feature selection, artifact persistence
**Confidence:** HIGH

## Summary

Phase 6 retrains the existing LR/RF/XGBoost pipeline on the v2 feature store (produced by Phase 5) with two feature sets (TEAM_ONLY and SP_ENHANCED), validates calibration via reliability diagrams, prunes features using VIF and SHAP, and persists 6 model artifacts as joblib files. The core training/calibration/evaluation infrastructure already exists from v1 -- `backtest.py`, `train.py`, `calibrate.py`, `evaluate.py` -- and needs adaptation rather than creation from scratch.

The primary risk areas are: (1) the v2 feature store must be built before any training can happen (Phase 5 code is complete but the store file does not exist yet), (2) VIF computation requires either installing `statsmodels` or implementing a pure sklearn/numpy alternative (statsmodels is currently not installed and installation failed during research), and (3) the FOLD_MAP must be extended to include 2025 as a test year for the Kalshi apples-to-apples comparison required by MDL-03.

**Primary recommendation:** Adapt the existing v1 backtest infrastructure by updating `backtest.py` and `evaluate.py` to support v2 feature sets, add VIF/SHAP analysis modules, extend the fold structure for 2025 out-of-sample testing, and persist artifacts via joblib. Build the v2 feature store as the first task.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MDL-01 | Six model artifacts (LR/RF/XGBoost x TEAM_ONLY/SP_ENHANCED) via walk-forward backtest on 2015-2024, 2020 excluded as test year | Existing `backtest.py` FOLD_MAP + `run_all_models` pattern, adapted for new feature sets. v1 code verified working. |
| MDL-02 | All 6 models calibrated using IsotonicRegression directly; temperature scaling evaluated only if reliability diagrams show problems | Existing `calibrate.py` already uses IsotonicRegression(out_of_bounds='clip'). sklearn 1.8.0 confirmed. Temperature scaling implementable via scipy.optimize. |
| MDL-03 | Brier score comparison table: v2 SP_ENHANCED vs v2 TEAM_ONLY vs v1 vs Kalshi market on identical 2025 out-of-sample games | Requires extending FOLD_MAP with a 2025 fold (train 2015-2023, cal 2024, test 2025). Kalshi opening prices available via candlestick API (2237 games). Existing `evaluate.py` Brier functions reusable. |
| MDL-04 | Reliability diagrams for all 6 model/feature-set combinations generated and visually inspected | Existing `evaluate.py` has `plot_calibration_curves` and `get_calibration_data`. Needs adaptation for new feature_set names ('team_only', 'sp_enhanced'). |
| MDL-05 | VIF analysis on SP_ENHANCED set; features with VIF > 10 dropped before final training | statsmodels not installed; VIF computable via sklearn LinearRegression (R^2 method). Tested and verified working. |
| MDL-06 | SHAP TreeExplainer feature importance for XGBoost; near-zero gain features removed | SHAP 0.51.0 installed. TreeExplainer verified working with XGBoost 2.1.4. shap_values returns correct shape. |
| MDL-07 | All 6 artifacts persisted as joblib in `models/artifacts/`; `model_metadata.json` records training date, feature columns, fold Brier scores, calibration method | joblib 1.5.3 available (ships with sklearn). Round-trip serialization of model+calibrator bundles verified. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| scikit-learn | 1.8.0 | LR, RF, IsotonicRegression, calibration_curve, brier_score_loss | Already installed; v1 trained all models with this |
| xgboost | 2.1.4 | XGBClassifier with early stopping | Already installed; native NaN handling, no pipeline wrapper needed |
| shap | 0.51.0 | TreeExplainer for XGBoost feature importance | Already installed; verified working with XGBoost 2.1.4 |
| joblib | 1.5.3 | Model artifact serialization (dump/load) | Ships with sklearn; verified round-trip for model+calibrator bundles |
| matplotlib | 3.10.8 | Reliability diagrams, Brier comparison plots | Already installed; existing evaluate.py uses it |
| pandas | 2.2.3 | Feature store I/O, data manipulation | Hard-pinned at 2.2.x (pybaseball constraint) |
| numpy | 2.4.3 | Numerical operations | Already installed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| scipy | (installed) | Temperature scaling optimization (minimize_scalar, expit, logit) | Only if reliability diagrams show poor isotonic calibration on small folds |
| json (stdlib) | - | model_metadata.json serialization | MDL-07 metadata file |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| sklearn VIF (manual) | statsmodels variance_inflation_factor | statsmodels failed to install; sklearn LinearRegression R^2 approach is equivalent and dependency-free |
| SHAP TreeExplainer | XGBoost feature_importances_ | SHAP provides per-sample explanations; feature_importances_ is aggregate gain only. MDL-06 specifically requires SHAP. However, feature_importances_ can be used for a quick sanity check. |
| IsotonicRegression | CalibratedClassifierCV(cv='prefit') | Deprecated in sklearn 1.8.0; direct IsotonicRegression is the settled approach |

### Not Needed
- **statsmodels**: VIF computable without it. Do NOT add as a dependency.
- **lightgbm**: Out of scope per project requirements.
- **optuna/hyperopt**: No hyperparameter tuning in scope; v1 hyperparameters are fixed.

## Architecture Patterns

### Recommended Project Structure
```
models/
  artifacts/              # NEW: 6 joblib files + model_metadata.json
    lr_team_only.joblib
    lr_sp_enhanced.joblib
    rf_team_only.joblib
    rf_sp_enhanced.joblib
    xgb_team_only.joblib
    xgb_sp_enhanced.joblib
    model_metadata.json

src/models/
  backtest.py             # MODIFY: add v2 fold structure, support new feature sets
  calibrate.py            # NO CHANGE: already uses IsotonicRegression correctly
  evaluate.py             # MODIFY: add Kalshi comparison, update plot labels
  feature_sets.py         # NO CHANGE: TEAM_ONLY/SP_ENHANCED already defined
  predict.py              # MODIFY: extend for v2 2025 predictions (both feature sets)
  train.py                # NO CHANGE: factory functions work with any feature set
  vif.py                  # NEW: VIF computation using sklearn LinearRegression
  shap_analysis.py        # NEW: SHAP TreeExplainer wrapper for feature pruning

data/
  features/
    feature_matrix.parquet      # v1 (preserve unchanged)
    feature_store_v2.parquet    # v2 (must be built as first task)
  results/
    backtest_results.parquet    # v1 results (preserve unchanged)
    backtest_results_v2.parquet # NEW: v2 results
    predictions_2025.parquet    # v1 2025 predictions (preserve unchanged)
    predictions_2025_v2.parquet # NEW: v2 2025 predictions (both feature sets)
    brier_comparison.csv        # NEW: MDL-03 comparison table
    vif_analysis.csv            # NEW: MDL-05 VIF results

notebooks/
  13_v2_model_training.ipynb      # NEW: orchestrates v2 training
  14_v2_model_comparison.ipynb    # NEW: Brier comparison + reliability diagrams
```

### Pattern 1: Walk-Forward Backtest with v2 Feature Sets
**What:** Extend the existing FOLD_MAP-based walk-forward loop to train on v2 feature store with TEAM_ONLY and SP_ENHANCED feature sets.
**When to use:** MDL-01 training of all 6 models.
**Key change from v1:** The v1 `run_all_models` uses `FULL_FEATURE_COLS`/`CORE_FEATURE_COLS`. v2 replaces these with `SP_ENHANCED_FEATURE_COLS`/`TEAM_ONLY_FEATURE_COLS`.
**Example:**
```python
# v2 model combinations (replacing v1's full/core)
V2_COMBINATIONS = [
    ('lr', make_lr_pipeline, TEAM_ONLY_FEATURE_COLS, 'team_only', False),
    ('lr', make_lr_pipeline, SP_ENHANCED_FEATURE_COLS, 'sp_enhanced', False),
    ('rf', make_rf_pipeline, TEAM_ONLY_FEATURE_COLS, 'team_only', False),
    ('rf', make_rf_pipeline, SP_ENHANCED_FEATURE_COLS, 'sp_enhanced', False),
    ('xgb', make_xgb_model, TEAM_ONLY_FEATURE_COLS, 'team_only', True),
    ('xgb', make_xgb_model, SP_ENHANCED_FEATURE_COLS, 'sp_enhanced', True),
]
```

### Pattern 2: v2 NaN Handling Differs from v1
**What:** The v1 backtest drops rows where `rolling_ops_diff` is NaN (early-season warmup games). The v2 feature store (after Phase 5 fixes) will have much lower NaN rates for SP columns (~0% with cold-start imputation vs 16.9% in v1). However, `rolling_ops_diff` still has early-season NaN by design (10-game warmup window).
**When to use:** Data cleaning before training.
**Critical detail:** The v2 backtest should use the same `rolling_ops_diff` NaN drop as v1 for consistency. SP columns should have zero NaN after Phase 5 cold-start imputation (SP-10).

### Pattern 3: Artifact Bundle Serialization
**What:** Each joblib file stores a dict containing the model, calibrator, and feature list -- not just the raw model.
**When to use:** MDL-07 artifact persistence.
**Example:**
```python
import joblib

artifact = {
    'model': fitted_model,           # sklearn Pipeline or XGBClassifier
    'calibrator': fitted_isotonic,    # IsotonicRegression
    'feature_cols': feature_col_list, # list[str]
    'model_name': 'lr',              # str
    'feature_set': 'team_only',      # str
}
joblib.dump(artifact, 'models/artifacts/lr_team_only.joblib')
```

### Pattern 4: VIF Computation Without statsmodels
**What:** Compute Variance Inflation Factor using sklearn LinearRegression R^2.
**When to use:** MDL-05 multicollinearity check.
**Example:**
```python
from sklearn.linear_model import LinearRegression
import pandas as pd

def compute_vif(X: pd.DataFrame) -> pd.DataFrame:
    vif_data = []
    for col in X.columns:
        y = X[col].values
        X_other = X.drop(columns=[col]).values
        lr = LinearRegression()
        lr.fit(X_other, y)
        r_sq = lr.score(X_other, y)
        vif = 1 / (1 - r_sq) if r_sq < 1.0 else float('inf')
        vif_data.append({'feature': col, 'VIF': round(vif, 2)})
    return pd.DataFrame(vif_data).sort_values('VIF', ascending=False)
```

### Pattern 5: SHAP TreeExplainer for Feature Pruning
**What:** Use SHAP to identify near-zero-gain features in XGBoost.
**When to use:** MDL-06 feature importance analysis.
**Example:**
```python
import shap
import numpy as np

explainer = shap.TreeExplainer(fitted_xgb_model)
shap_values = explainer.shap_values(X_train)  # returns (n_samples, n_features)
mean_abs_shap = np.abs(shap_values).mean(axis=0)  # per-feature importance

# Identify near-zero features
feature_importance = pd.DataFrame({
    'feature': feature_cols,
    'mean_abs_shap': mean_abs_shap,
}).sort_values('mean_abs_shap', ascending=False)

near_zero = feature_importance[feature_importance['mean_abs_shap'] < 0.001]
```

### Pattern 6: 2025 Fold for Kalshi Comparison
**What:** Extend the fold structure with a 2025 test year for apples-to-apples comparison.
**When to use:** MDL-03 Brier comparison.
**Key detail:** The 2025 fold trains on 2015-2023, calibrates on 2024, tests on 2025. This is the same pattern as the existing `predict.py` but applied to all 6 v2 models plus the v1 models for comparison.
**Kalshi overlap:** 2237 Kalshi games cover 2025-04-16 through 2026-03-28. The comparison must use the intersection of games that have both model predictions and Kalshi opening prices.

### Anti-Patterns to Avoid
- **Training on v2 features but evaluating on v1 feature store:** Always train and evaluate from the same feature store file to prevent silent column mismatch.
- **Using v1 backtest results as v2 baseline:** The v1 results used `FULL_FEATURE_COLS` which includes `sp_k_pct_diff` and 100% NaN `xwoba_diff`. For fair comparison, re-run v1-equivalent training from the v2 feature store using `V1_FULL_FEATURE_COLS`.
- **Dropping features after calibration:** VIF and SHAP pruning must happen before final training, not after. The sequence is: analyze features -> prune -> retrain -> calibrate -> evaluate.
- **Saving model without calibrator:** The Phase 7 pipeline needs both the model and its paired IsotonicRegression calibrator. Always serialize as a bundle.
- **Amending FOLD_MAP in place:** Keep the v1 5-fold FOLD_MAP unchanged for backward compatibility. Create a separate `V2_FOLD_MAP` or a 2025-specific fold constant.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Probability calibration | Custom sigmoid fitting | sklearn IsotonicRegression(out_of_bounds='clip') | Handles monotonicity, edge cases, already verified in v1 |
| Brier score computation | Manual MSE of probabilities | sklearn brier_score_loss | Handles edge cases, sample weights, well-tested |
| Calibration curve data | Manual binning | sklearn calibration_curve(strategy='uniform') | Consistent binning logic, handles sparse bins |
| Model serialization | pickle/custom JSON | joblib.dump/load | Handles numpy arrays, large models, compression |
| SHAP values for trees | Manual feature permutation | shap.TreeExplainer | Exact Shapley values for tree models, not approximate |
| Early stopping for XGBoost | Manual epoch loop | XGBClassifier(early_stopping_rounds=20) with eval_set | Built-in, efficient, handles the callback properly |

**Key insight:** The v1 codebase already solved most of these problems. Phase 6 extends rather than replaces.

## Common Pitfalls

### Pitfall 1: Feature Store Not Built
**What goes wrong:** Phase 5 code is complete (all 4 plans done) but `feature_store_v2.parquet` does not exist on disk. Attempting to train on v2 features will fail with FileNotFoundError.
**Why it happens:** Phase 5 wrote the code to build the store but the actual build (which requires fetching data from APIs) was not executed as part of the plan completion.
**How to avoid:** The first task of Phase 6 must build the v2 feature store by calling `FeatureBuilder.build_and_save_v2()`. This is a prerequisite for all subsequent tasks.
**Warning signs:** `data/features/feature_store_v2.parquet` does not exist.

### Pitfall 2: NaN-Drop Strategy Mismatch Between Feature Sets
**What goes wrong:** TEAM_ONLY has 9 features, none of which are SP-specific. SP_ENHANCED has 20 features including SP columns. If the NaN-drop strategy differs (e.g., dropping rows with any NaN in SP columns for SP_ENHANCED but not for TEAM_ONLY), the game sets are different sizes and Brier comparison is not apples-to-apples.
**Why it happens:** Different feature sets have different NaN patterns.
**How to avoid:** Use the same row-filtering strategy for both feature sets. The v2 feature store should have zero SP NaN after cold-start imputation. The only NaN should be `rolling_ops_diff` early-season warmup, which affects both sets equally.
**Warning signs:** Different `n_games` counts between TEAM_ONLY and SP_ENHANCED in Brier comparison table.

### Pitfall 3: VIF on Features with NaN
**What goes wrong:** VIF computation using LinearRegression will fail or produce meaningless results if input features contain NaN values.
**Why it happens:** sklearn LinearRegression does not handle NaN natively.
**How to avoid:** Compute VIF on the NaN-dropped training set (after `rolling_ops_diff` filter). Or impute before VIF computation.
**Warning signs:** VIF computation raises ValueError or returns all-infinity values.

### Pitfall 4: SHAP Feature Names Mismatch
**What goes wrong:** SHAP TreeExplainer with XGBoost uses internal feature names (f0, f1, ...) unless explicitly mapped.
**Why it happens:** XGBoost stores feature names from the DataFrame column names if trained with a DataFrame, but SHAP may not carry them through.
**How to avoid:** Pass `feature_names=feature_cols` to TreeExplainer, or map after computation using the feature_cols list.
**Warning signs:** SHAP summary plot shows f0, f1 instead of actual feature names.

### Pitfall 5: Temperature Scaling Unnecessary for Most Cases
**What goes wrong:** Implementing temperature scaling "just in case" adds complexity without benefit if isotonic calibration works well.
**Why it happens:** MDL-02 mentions it as a fallback.
**How to avoid:** Only implement temperature scaling if reliability diagrams show clear problems with isotonic calibration on small folds (specifically the 2020 calibration fold with ~891 games). Isotonic regression is the settled default.
**Warning signs:** Reliability diagrams for isotonic-calibrated models are well-calibrated (close to diagonal) -- no need for temperature scaling.

### Pitfall 6: Circular Feature Pruning
**What goes wrong:** VIF identifies feature A as high-VIF. Dropping A changes VIF of feature B. Iterative pruning can oscillate.
**Why it happens:** VIF is relative -- removing one feature changes all other VIFs.
**How to avoid:** Drop one feature at a time (highest VIF first), recompute, repeat until all VIF < 10. Document each step.
**Warning signs:** VIF computation looping indefinitely.

### Pitfall 7: Artifact Naming Convention Mismatch with Phase 7
**What goes wrong:** Phase 7 pipeline expects specific artifact filenames/paths. If Phase 6 uses different naming, Phase 7 breaks.
**Why it happens:** No convention established yet.
**How to avoid:** Use the naming convention `{model_name}_{feature_set}.joblib` (e.g., `lr_team_only.joblib`). Phase 7's API startup will load by these names.
**Warning signs:** Phase 7 planning discovers unexpected artifact structure.

## Code Examples

### Building the v2 Feature Store (Prerequisite)
```python
from src.features.feature_builder import FeatureBuilder

# Build v2 feature store covering 2015-2025 (includes 2025 for Kalshi comparison)
builder = FeatureBuilder(seasons=list(range(2015, 2026)))
df = builder.build_and_save_v2("data/features/feature_store_v2.parquet")
```

### v2 Walk-Forward Backtest
```python
from src.models.backtest import generate_folds, FOLD_MAP
from src.models.feature_sets import SP_ENHANCED_FEATURE_COLS, TEAM_ONLY_FEATURE_COLS

# Load v2 feature store
df = pd.read_parquet("data/features/feature_store_v2.parquet")

# Run backtest for one model (e.g., XGBoost on SP_ENHANCED)
results = run_backtest(
    df, make_xgb_model, 'xgb', SP_ENHANCED_FEATURE_COLS, 'sp_enhanced', is_xgb=True
)
```

### Saving Model Artifacts with Metadata
```python
import joblib
import json
from datetime import datetime

artifacts_dir = Path("models/artifacts")
artifacts_dir.mkdir(parents=True, exist_ok=True)

metadata = {
    "training_date": datetime.now().isoformat(),
    "models": {}
}

for model_name, feature_set, model, calibrator, feature_cols, fold_briers in trained_models:
    artifact_name = f"{model_name}_{feature_set}"
    artifact = {
        'model': model,
        'calibrator': calibrator,
        'feature_cols': feature_cols,
        'model_name': model_name,
        'feature_set': feature_set,
    }
    joblib.dump(artifact, artifacts_dir / f"{artifact_name}.joblib")

    metadata["models"][artifact_name] = {
        "feature_cols": feature_cols,
        "fold_brier_scores": fold_briers,  # dict of {test_year: brier_score}
        "calibration_method": "IsotonicRegression",
    }

with open(artifacts_dir / "model_metadata.json", "w") as f:
    json.dump(metadata, f, indent=2)
```

### VIF Analysis
```python
from sklearn.linear_model import LinearRegression

def compute_vif(X: pd.DataFrame) -> pd.DataFrame:
    """Compute VIF for each feature. VIF > 10 = problematic multicollinearity."""
    vif_data = []
    for col in X.columns:
        y = X[col].values
        X_other = X.drop(columns=[col]).values
        lr = LinearRegression()
        lr.fit(X_other, y)
        r_sq = lr.score(X_other, y)
        vif = 1 / (1 - r_sq) if r_sq < 1.0 else float('inf')
        vif_data.append({'feature': col, 'VIF': round(vif, 2)})
    return pd.DataFrame(vif_data).sort_values('VIF', ascending=False)

# Usage: run on SP_ENHANCED training data
X_train = df_clean[SP_ENHANCED_FEATURE_COLS].dropna()
vif_results = compute_vif(X_train)
high_vif = vif_results[vif_results['VIF'] > 10]
```

### SHAP Feature Importance
```python
import shap
import numpy as np

# After training XGBoost on SP_ENHANCED
explainer = shap.TreeExplainer(fitted_xgb)
shap_values = explainer.shap_values(X_train[SP_ENHANCED_FEATURE_COLS])

mean_abs_shap = np.abs(shap_values).mean(axis=0)
importance_df = pd.DataFrame({
    'feature': SP_ENHANCED_FEATURE_COLS,
    'mean_abs_shap': mean_abs_shap,
}).sort_values('mean_abs_shap', ascending=False)

# Near-zero: features contributing < 0.1% of total SHAP budget
total_shap = mean_abs_shap.sum()
importance_df['pct_of_total'] = importance_df['mean_abs_shap'] / total_shap
near_zero = importance_df[importance_df['pct_of_total'] < 0.001]
```

### Brier Score Comparison Table (MDL-03)
```python
from sklearn.metrics import brier_score_loss

# Collect predictions for identical 2025 game set
# Filter to games present in ALL comparison groups
common_games = set(v2_sp_enhanced.game_key) & set(v2_team_only.game_key) & \
               set(v1_preds.game_key) & set(kalshi_preds.game_key)

comparison = {}
for name, preds in [('v2_sp_enhanced', ...), ('v2_team_only', ...), ('v1', ...), ('kalshi', ...)]:
    filtered = preds[preds.game_key.isin(common_games)]
    comparison[name] = brier_score_loss(filtered.home_win, filtered.prob)
```

## State of the Art

| Old Approach (v1) | Current Approach (v2) | When Changed | Impact |
|--------------------|-----------------------|--------------|--------|
| CalibratedClassifierCV(cv='prefit') | IsotonicRegression direct | sklearn 1.8.0 | Already migrated in v1 code |
| FULL_FEATURE_COLS (14 cols, 100% NaN xwoba) | SP_ENHANCED_FEATURE_COLS (20 cols, fixed xwoba) | Phase 5 | More features, better coverage |
| CORE_FEATURE_COLS (13 cols, no xwoba) | TEAM_ONLY_FEATURE_COLS (9 cols, no SP) | Phase 5 | Clean separation of team vs pitcher |
| Single feature store | Versioned v1/v2 stores | Phase 5 | Apples-to-apples comparison possible |
| Manual backtest results cache | Versioned results files | Phase 6 | Preserves v1 results unchanged |

**v1 Baseline Brier Scores (aggregate, 2019-2024 test years):**
| Model | Feature Set | Brier Score | N Games |
|-------|-------------|-------------|---------|
| LR | core | 0.2349 | 11,343 |
| LR | full | 0.2350 | 11,343 |
| RF | core | 0.2364 | 11,343 |
| RF | full | 0.2372 | 11,343 |
| XGB | core | 0.2372 | 11,343 |
| XGB | full | 0.2371 | 11,343 |

**v1 2025 Predictions (core features only):**
| Model | Brier Score | N Games |
|-------|-------------|---------|
| LR | 0.2394 | 2,279 |
| RF | 0.2406 | 2,279 |
| XGB | 0.2421 | 2,279 |

**Key observation:** v1 full vs core difference is negligible (< 0.003 Brier). The SP features in v1 had 16.9% NaN and 100% NaN xwoba. v2 with fixed SP features and cold-start imputation should show a more meaningful gap between TEAM_ONLY and SP_ENHANCED.

## Open Questions

1. **Feature Store Build Time**
   - What we know: `build_and_save_v2()` calls multiple APIs (MLB Stats, FanGraphs, Statcast) and the v1 build took substantial time. Phase 5 code handles caching.
   - What's unclear: Whether all the raw data is already cached from previous runs or if fresh API calls are needed for 2025 season data.
   - Recommendation: Plan for the build to take 10-30 minutes. If raw data is cached, it will be faster.

2. **SP_ENHANCED VIF Expectations**
   - What we know: SP_ENHANCED has 20 features. Several SP features may be correlated (sp_fip_diff and sp_xfip_diff, sp_era_diff and sp_recent_era_diff).
   - What's unclear: Exactly which features will have VIF > 10.
   - Recommendation: Run VIF analysis early. Likely candidates for high VIF: sp_fip_diff vs sp_xfip_diff (same FIP family), sp_era_diff vs sp_recent_era_diff (overlapping signal).

3. **Apples-to-Apples 2025 Comparison Scope**
   - What we know: v1 2025 predictions cover 2,279 games (core features). Kalshi has 2,237 games. The intersection defines the comparison set.
   - What's unclear: Whether the v2 feature store for 2025 will have the same game coverage as v1. Some games may be excluded if SP data is unavailable in v2 but was available in v1 (or vice versa).
   - Recommendation: Define the comparison game set as the intersection of all four groups (v2 SP_ENHANCED, v2 TEAM_ONLY, v1, Kalshi). Document the count.

4. **"Near-Zero Gain" Threshold for SHAP**
   - What we know: MDL-06 says "near-zero gain." No numeric threshold specified.
   - What's unclear: What counts as "near-zero."
   - Recommendation: Use < 0.1% of total SHAP budget as the threshold. Document the threshold and results. If zero features meet the threshold, document that finding (it is a valid outcome).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.1.1 |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest tests/ -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MDL-01 | 6 model artifacts trained via walk-forward on v2 feature store | integration | `python -m pytest tests/test_v2_backtest.py -x -q` | No -- Wave 0 |
| MDL-02 | IsotonicRegression calibration produces valid [0,1] probs | unit | `python -m pytest tests/test_models.py::test_isotonic_calibration -x` | Yes (existing) |
| MDL-03 | Brier comparison table has 4 rows on identical game set | unit | `python -m pytest tests/test_v2_evaluation.py::test_brier_comparison_apples_to_apples -x` | No -- Wave 0 |
| MDL-04 | Reliability diagram generation for all 6 combinations | unit | `python -m pytest tests/test_v2_evaluation.py::test_reliability_diagrams_generated -x` | No -- Wave 0 |
| MDL-05 | VIF computation returns valid values; high-VIF features identified | unit | `python -m pytest tests/test_vif.py -x -q` | No -- Wave 0 |
| MDL-06 | SHAP TreeExplainer produces per-feature importance for XGBoost | unit | `python -m pytest tests/test_shap_analysis.py -x -q` | No -- Wave 0 |
| MDL-07 | Artifacts serialize/deserialize correctly; metadata JSON is valid | unit | `python -m pytest tests/test_artifacts.py -x -q` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/ -x -q`
- **Per wave merge:** `python -m pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_vif.py` -- covers MDL-05 (VIF computation, high-VIF detection)
- [ ] `tests/test_shap_analysis.py` -- covers MDL-06 (SHAP TreeExplainer, near-zero feature detection)
- [ ] `tests/test_artifacts.py` -- covers MDL-07 (joblib round-trip, metadata JSON schema)
- [ ] `tests/test_v2_backtest.py` -- covers MDL-01 (v2 model combinations, fold structure)
- [ ] `tests/test_v2_evaluation.py` -- covers MDL-03, MDL-04 (Brier comparison, reliability diagrams)
- [ ] Existing `tests/test_models.py` and `tests/test_backtest.py` cover MDL-02 and backtest fold integrity (already passing)

## Sources

### Primary (HIGH confidence)
- Existing codebase: `src/models/backtest.py`, `train.py`, `calibrate.py`, `evaluate.py`, `feature_sets.py`, `predict.py` -- read in full, all patterns verified
- sklearn 1.8.0 API verified via runtime `inspect.signature()` -- IsotonicRegression, calibration_curve, brier_score_loss
- XGBoost 2.1.4 verified installed and working
- SHAP 0.51.0 TreeExplainer verified via smoke test with XGBoost 2.1.4
- joblib 1.5.3 round-trip serialization verified for model+calibrator bundles

### Secondary (MEDIUM confidence)
- VIF manual computation (sklearn LinearRegression R^2 method) verified via test with synthetic data
- Temperature scaling implementation verified via scipy.optimize.minimize_scalar test
- v1 Brier scores computed from existing `data/results/backtest_results.parquet` and `predictions_2025.parquet`

### Tertiary (LOW confidence)
- statsmodels installation status -- it failed to install during research. May work in a different environment, but the manual VIF approach is a safe fallback.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all packages verified installed and working with correct versions
- Architecture: HIGH -- extending existing v1 infrastructure with well-understood patterns
- Pitfalls: HIGH -- identified from direct codebase inspection and v1 experience (NaN patterns, feature store dependency, naming conventions)
- VIF approach: MEDIUM -- manual computation verified with synthetic data; not tested on real feature data yet
- Feature store build: MEDIUM -- code exists but the actual build has not been run; depends on API cache state

**Research date:** 2026-03-29
**Valid until:** 2026-04-28 (stable ML stack, no expected breaking changes)
