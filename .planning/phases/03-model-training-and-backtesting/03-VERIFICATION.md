---
phase: 03-model-training-and-backtesting
verified: 2026-03-29T08:30:00Z
status: passed
score: 14/14 must-haves verified
re_verification: false
gaps: []
human_verification:
  - test: "Run notebooks/09_model_training.ipynb end-to-end against real feature_matrix.parquet (22,714 rows)"
    expected: "Backtest completes for all 6 model/feature-set combinations; results saved to data/results/backtest_results.parquet; quick Brier preview shows 6 rows in 0.20–0.26 range"
    why_human: "Full backtest takes several minutes; notebook execution requires a running Jupyter kernel against real data"
  - test: "Run notebooks/10_model_comparison.ipynb standalone (without re-running NB09)"
    expected: "Calibration curve plots render for both feature sets; per-season Brier bar charts appear; accuracy table shows values in 0.50–0.65 range"
    why_human: "Visual correctness of matplotlib plots cannot be verified programmatically"
---

# Phase 3: Model Training and Backtesting — Verification Report

**Phase Goal:** User can compare three trained, calibrated models on Brier score and calibration quality across multiple seasons of walk-forward backtesting
**Verified:** 2026-03-29T08:30:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Walk-forward fold generator produces 5 folds with correct train/calibrate/test season splits | VERIFIED | `FOLD_MAP` in `backtest.py` has exactly 5 tuples with test years [2019,2021,2022,2023,2024] and cal years [2018,2020,2021,2022,2023]; `test_fold_map_structure` passes |
| 2 | 2020 is never a test year and is only included in training sets | VERIFIED | No fold in `FOLD_MAP` has `test_year=2020`; 2020 appears as calibration year in fold 2 and as part of training sets in folds 3–5; `test_2020_not_test_year` passes |
| 3 | Early-season NaN rows (rolling_ops_diff is NaN) are excluded from all splits | VERIFIED | `generate_folds` drops NaN rows before season filtering: `df_clean = df[df["rolling_ops_diff"].notna()].copy()`; `test_nan_rows_excluded` passes |
| 4 | LR pipeline trains and produces probabilities in [0,1] | VERIFIED | `make_lr_pipeline()` returns Pipeline(StandardScaler→SimpleImputer→LogisticRegression(max_iter=500)); no deprecated `penalty=`; `test_lr_pipeline_trains` passes |
| 5 | RF pipeline trains and produces probabilities in [0,1] | VERIFIED | `make_rf_pipeline()` returns Pipeline(SimpleImputer→RandomForestClassifier(n_estimators=300,max_depth=8,min_samples_leaf=20)); `test_rf_pipeline_trains` passes |
| 6 | XGBoost trains with early stopping on last 20% of training window | VERIFIED | `run_backtest` with `is_xgb=True` splits training data: `n_val = int(len(X_train) * 0.2)`, uses `X_train.iloc[:-n_val]` / `X_train.iloc[-n_val:]`; calls `model.fit(X_tr, y_tr, eval_set=[(X_val,y_val)], verbose=False)`; `test_xgb_early_stopping` passes |
| 7 | Isotonic calibration produces valid probabilities clipped to [0,1] | VERIFIED | `calibrate_model` uses `IsotonicRegression(out_of_bounds='clip')` fitted per-fold; real results parquet shows `prob_calibrated` range [0.0, 1.0]; `test_isotonic_calibration` passes |
| 8 | Brier score is computed correctly per fold and in aggregate | VERIFIED | `compute_brier_scores` groups by model_name/feature_set/fold_test_year and computes `brier_score_loss`; also computes aggregate per model+feature_set; real aggregate scores 0.2349–0.2372 (well within expected 0.20–0.26); `test_brier_score_per_fold` passes |
| 9 | Calibration curve data can be generated from results | VERIFIED | `get_calibration_data` calls `calibration_curve(y_true, y_prob, n_bins, strategy='uniform')` from sklearn; `test_calibration_curve_output` passes |
| 10 | User can run notebook 09 to train all 3 models on both feature sets via walk-forward backtest and save results to disk | VERIFIED | NB09 (13 cells) imports `run_all_models`, has cache-before-compute pattern (`RESULTS_PATH.exists()`), calls `to_parquet('...backtest_results.parquet')`; contains no direct `.fit()` call (delegates entirely to src/models/) |
| 11 | User can run notebook 10 standalone to view side-by-side Brier scores, calibration curves, and per-season accuracy without re-training | VERIFIED | NB10 (18 cells) imports from `src.models.evaluate` only (no `run_backtest`), asserts `RESULTS_PATH.exists()`, calls `compute_brier_scores`, `plot_calibration_curves`, `plot_brier_by_season`, `compute_naive_baseline_brier`; contains per-season accuracy computation |
| 12 | Backtest results contain per-game predictions with Phase 4 join keys preserved | VERIFIED | `data/results/backtest_results.parquet` exists with shape (68058, 10); columns include `game_date`, `home_team`, `away_team` (Phase 4 join keys) plus `season`, `home_win`, `model_name`, `feature_set`, `fold_test_year`, `prob_calibrated`, `prob_raw` |
| 13 | Brier scores are reported per model, per feature set, per season, and in aggregate | VERIFIED | NB10 displays aggregate Brier table, per-season Brier pivot table, per-season Brier bar charts for both feature sets, and full-vs-core comparison |
| 14 | Calibration curves show where each model is over- or underconfident | VERIFIED | `plot_calibration_curves` plots diagonal reference + 3 model curves per feature set; NB10 calls it for both 'full' and 'core' feature sets with `plt.show()` |

**Score: 14/14 truths verified**

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/models/__init__.py` | Package init with module exports | VERIFIED | Exists; docstring lists all 5 submodules (feature_sets, train, calibrate, backtest, evaluate) |
| `src/models/feature_sets.py` | FULL_FEATURE_COLS (14), CORE_FEATURE_COLS (13), TARGET_COL, JOIN_KEYS, META_COLS | VERIFIED | 14 cols confirmed; xwoba_diff absent; sp_recent_era_diff differentiates full vs core; all 5 constants present |
| `src/models/train.py` | make_lr_pipeline, make_rf_pipeline, make_xgb_model factory functions | VERIFIED | All 3 factories present; no deprecated `penalty=` or `use_label_encoder`; correct hyperparameters (LR: max_iter=500; RF: n_estimators=300,max_depth=8,min_samples_leaf=20; XGB: max_depth=4,learning_rate=0.05,early_stopping_rounds=20) |
| `src/models/calibrate.py` | calibrate_model using IsotonicRegression | VERIFIED | Uses `IsotonicRegression(out_of_bounds='clip')`; no `CalibratedClassifierCV` in executable code (only in comment noting its removal); returns `(cal_probs_test, raw_probs_test)` tuple |
| `src/models/backtest.py` | FOLD_MAP, generate_folds, run_backtest, run_all_models | VERIFIED | All 4 exports present; FOLD_MAP has 5 tuples; generate_folds drops NaN rows; run_all_models runs all 6 combinations with logger.info progress |
| `src/models/evaluate.py` | compute_brier_scores, compute_naive_baseline_brier, get_calibration_data, plot_calibration_curves, plot_brier_by_season | VERIFIED | All 5 functions present; imports `brier_score_loss` and `calibration_curve` from sklearn; returns Figure (not plt.show()) |
| `tests/test_backtest.py` | 6 tests for fold structure, overlaps, 2020 exclusion, NaN exclusion, Brier, schema | VERIFIED | 6 tests present and passing; covers all required behaviors |
| `tests/test_models.py` | 5 tests for LR/RF/XGB, calibration, calibration curve | VERIFIED | 5 tests present and passing; all assertions on shape, bounds [0,1], and output types |
| `notebooks/09_model_training.ipynb` | Training notebook (min 40 lines) | VERIFIED | 13 cells, valid JSON; imports run_all_models; cache-before-compute pattern; delegates all ML logic to src/models/ |
| `notebooks/10_model_comparison.ipynb` | Comparison notebook (min 50 lines) | VERIFIED | 18 cells, valid JSON; loads saved results; no training dependency; displays full comparison suite |
| `data/results/backtest_results.parquet` | Per-game predictions for all models/folds | VERIFIED | Exists; 68,058 rows x 10 cols; 3 models x 2 feature sets x 5 test years; all required columns present |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/models/backtest.py` | `src/models/train.py` | `model_factory()` call in run_backtest | WIRED | `from src.models.train import make_lr_pipeline, make_rf_pipeline, make_xgb_model`; called via `model = model_factory()` |
| `src/models/backtest.py` | `src/models/calibrate.py` | `calibrate_model` call in backtest loop | WIRED | `from src.models.calibrate import calibrate_model`; called as `cal_probs, raw_probs = calibrate_model(model, X_cal, y_cal, X_test)` per fold |
| `src/models/backtest.py` | `src/models/feature_sets.py` | FULL_FEATURE_COLS / CORE_FEATURE_COLS imported | WIRED | `from src.models.feature_sets import CORE_FEATURE_COLS, FULL_FEATURE_COLS, TARGET_COL`; both used in `run_all_models` combinations |
| `src/models/evaluate.py` | `sklearn.metrics` / `sklearn.calibration` | brier_score_loss and calibration_curve | WIRED | `from sklearn.metrics import brier_score_loss` and `from sklearn.calibration import calibration_curve`; both called in production code paths |
| `notebooks/09_model_training.ipynb` | `src/models/backtest.py` | `from src.models.backtest import run_all_models` | WIRED | Import confirmed; `run_all_models(df)` called in backtest cell |
| `notebooks/09_model_training.ipynb` | `data/results/backtest_results.parquet` | `to_parquet` save | WIRED | `results_df.to_parquet(RESULTS_PATH, ...)` present; file exists on disk with 68,058 rows |
| `notebooks/10_model_comparison.ipynb` | `data/results/backtest_results.parquet` | `read_parquet` load | WIRED | `pd.read_parquet(RESULTS_PATH)` confirmed; `assert RESULTS_PATH.exists()` guards against missing file |
| `notebooks/10_model_comparison.ipynb` | `src/models/evaluate.py` | `from src.models.evaluate import` | WIRED | Imports compute_brier_scores, compute_naive_baseline_brier, get_calibration_data, plot_calibration_curves, plot_brier_by_season — all 5 called in notebook |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| MODEL-01 | 03-01 | Logistic regression model trains on the feature matrix | SATISFIED | `make_lr_pipeline()` builds Pipeline(StandardScaler→SimpleImputer→LR); trained per fold in `run_backtest`; `test_lr_pipeline_trains` passes; results parquet contains 'lr' rows |
| MODEL-02 | 03-01 | Random forest model trains on the feature matrix | SATISFIED | `make_rf_pipeline()` builds Pipeline(SimpleImputer→RF); trained per fold; `test_rf_pipeline_trains` passes; results parquet contains 'rf' rows |
| MODEL-03 | 03-01 | XGBoost trains with aggressive regularization and early stopping on temporal validation | SATISFIED | `make_xgb_model()` uses max_depth=4, reg_alpha=1.0, reg_lambda=2.0, early_stopping_rounds=20; temporal split (last 20% of training window) used in `run_backtest` with `is_xgb=True`; `test_xgb_early_stopping` passes |
| MODEL-04 | 03-01 | All three models are probability-calibrated | SATISFIED (with documented API substitution) | Requirement specified `CalibratedClassifierCV` which was removed in sklearn 1.8.0; `IsotonicRegression(out_of_bounds='clip')` is the correct substitute (documented in RESEARCH.md line 51); calibration intent fully achieved; `test_isotonic_calibration` verifies bounds [0,1]; `prob_calibrated` in results parquet ranges [0.0, 1.0] |
| EVAL-01 | 03-01, 03-02 | Walk-forward backtesting (no random splits) | SATISFIED | `FOLD_MAP` enforces expanding training window; `generate_folds` filters by season membership (temporal integrity); 5 test years all in future relative to training; `test_fold_splits_no_overlap`, `test_2020_not_test_year`, `test_nan_rows_excluded` all pass |
| EVAL-02 | 03-01, 03-02 | Brier score per model, per season, and in aggregate | SATISFIED | `compute_brier_scores` groups by model_name/feature_set/fold_test_year and adds aggregate rows; NB10 displays both per-season pivot and aggregate table; real scores confirmed 0.2349–0.2372 |
| EVAL-03 | 03-01, 03-02 | Calibration curves generated per model | SATISFIED | `get_calibration_data` and `plot_calibration_curves` implemented; NB10 plots reliability diagrams for 'full' and 'core' feature sets with diagonal reference line; `test_calibration_curve_output` passes |
| EVAL-04 | 03-02 | Model comparison notebook presents LR vs RF vs XGBoost side-by-side | SATISFIED | NB10 (18 cells) presents: aggregate Brier table, per-season Brier tables and bar charts, calibration curves, full-vs-core feature comparison, per-season accuracy — all three models shown side-by-side |

**All 8 requirement IDs from PLAN frontmatter accounted for. No orphaned requirements found.**

Note on MODEL-04: The REQUIREMENTS.md description references `CalibratedClassifierCV` (temperature scaling), which was removed from scikit-learn 1.8.0. The implementation correctly uses `IsotonicRegression(out_of_bounds='clip')` as a direct replacement. This is an API-level substitution, not a functional deviation — the probability calibration goal is fully achieved.

### Anti-Patterns Found

No anti-patterns detected. Scan across all 8 phase-03 source files found:
- Zero TODO/FIXME/HACK/PLACEHOLDER comments
- Zero `return null` / empty return stubs
- Zero `raise NotImplementedError`
- `CalibratedClassifierCV` appears only in a docstring comment in `calibrate.py` (line 4) documenting why it was NOT used

### Human Verification Required

#### 1. Full Backtest Execution

**Test:** Open and run `notebooks/09_model_training.ipynb` top-to-bottom against real `data/features/feature_matrix.parquet`
**Expected:** Feature matrix loads 22,714 rows; fold map displays 5 folds; backtest runs or loads from cache; results summary shows 3 models x 2 feature sets; quick Brier preview shows 6 rows with scores in 0.20–0.26 range
**Why human:** Full backtest takes several minutes; requires a running Jupyter kernel with real feature data loaded from disk

#### 2. Model Comparison Visuals

**Test:** Open and run `notebooks/10_model_comparison.ipynb` without re-running NB09 first
**Expected:** Calibration curve plots render with diagonal reference line and 3 model curves (for both 'full' and 'core' feature sets); per-season Brier bar charts appear; per-season accuracy table shows values in 0.50–0.65 range; no errors from missing results file
**Why human:** Visual rendering quality of matplotlib plots cannot be verified programmatically; real-world Brier and accuracy values depend on actual model training output already confirmed in parquet

### Summary

The phase goal is fully achieved. All three models (LR, RF, XGBoost) are implemented as factory functions with correct sklearn 1.8 / xgboost 2.x API compliance. The 5-fold walk-forward backtest enforces temporal integrity (2020 never as test year, NaN rows excluded, no random splits). Isotonic calibration is applied per-fold. Evaluation utilities compute Brier scores (per-fold and aggregate) and generate calibration curve data. Two thin-wrapper notebooks orchestrate training (NB09) and comparison (NB10). The actual results parquet (68,058 rows) is on disk with confirmed schema and plausible Brier scores (0.2349–0.2372). All 11 phase-specific tests pass; full suite is 95/95 green.

The only item requiring human verification is visual inspection of notebook plots — all automated checks are fully satisfied.

---

_Verified: 2026-03-29T08:30:00Z_
_Verifier: Claude (gsd-verifier)_
