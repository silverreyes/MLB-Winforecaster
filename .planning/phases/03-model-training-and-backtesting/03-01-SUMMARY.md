---
phase: 03-model-training-and-backtesting
plan: 01
subsystem: models
tags: [sklearn, xgboost, isotonic-calibration, walk-forward, brier-score, backtest]

# Dependency graph
requires:
  - phase: 02-feature-engineering-and-feature-store
    provides: "Feature matrix with 14 differential columns, rolling features, metadata columns"
provides:
  - "src/models/ package with 6 importable modules"
  - "14-col FULL and 13-col CORE feature set definitions"
  - "LR, RF, XGBoost model factory functions (sklearn 1.8 / xgb 2.x compatible)"
  - "IsotonicRegression-based post-hoc calibration wrapper"
  - "5-fold walk-forward backtest loop with FOLD_MAP"
  - "Brier score computation (per-fold and aggregate)"
  - "Calibration curve and per-season Brier plotting utilities"
  - "Naive baseline Brier score for comparison"
affects: [03-02, 04-market-comparison]

# Tech tracking
tech-stack:
  added: [sklearn.isotonic.IsotonicRegression, xgboost.XGBClassifier, sklearn.calibration.calibration_curve]
  patterns: [model-factory-per-fold, isotonic-calibration-per-fold, walk-forward-expanding-window, temporal-early-stopping]

key-files:
  created:
    - src/models/__init__.py
    - src/models/feature_sets.py
    - src/models/train.py
    - src/models/calibrate.py
    - src/models/backtest.py
    - src/models/evaluate.py
    - tests/test_models.py
    - tests/test_backtest.py
  modified: []

key-decisions:
  - "Used IsotonicRegression directly instead of deprecated CalibratedClassifierCV(cv='prefit') for sklearn 1.8.0 compatibility"
  - "Omitted penalty= from LogisticRegression (deprecated in sklearn 1.8.0) and use_label_encoder from XGBClassifier (removed in xgboost 2.x)"
  - "Excluded xwoba_diff from all feature sets (100% NaN); core set differentiates on sp_recent_era_diff only"
  - "XGBoost early stopping uses last 20% of training window (temporal split), not calibration season"
  - "feature_set_name is explicit string parameter, not derived from column contents"

patterns-established:
  - "Model factory pattern: fresh model per fold via factory callable, no state leakage"
  - "Walk-forward FOLD_MAP: explicit 5-tuple constant, 2020 never test year, data-length-agnostic"
  - "Calibration per fold: isotonic calibrator fitted independently per fold on season N-1"
  - "Results schema: per-game predictions with Phase 4 join keys preserved"

requirements-completed: [MODEL-01, MODEL-02, MODEL-03, MODEL-04, EVAL-01, EVAL-02, EVAL-03]

# Metrics
duration: 5min
completed: 2026-03-29
---

# Phase 3 Plan 1: Model Training Library Summary

**Walk-forward backtest library with LR/RF/XGBoost factories, isotonic calibration, 5-fold FOLD_MAP, Brier evaluation, and 11 passing tests**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-29T07:33:35Z
- **Completed:** 2026-03-29T07:38:27Z
- **Tasks:** 3
- **Files created:** 8

## Accomplishments
- Created complete src/models/ package with 6 importable modules following the Phase 1/2 pattern of thin notebooks calling library code
- Defined 14-column FULL and 13-column CORE feature sets (xwoba_diff excluded, sp_recent_era_diff as differentiator)
- Built 3 model factories compatible with sklearn 1.8.0 and xgboost 2.1.4 API changes
- Implemented walk-forward backtest loop with 5-fold FOLD_MAP (2020 never test year, NaN rows excluded)
- Added isotonic calibration using IsotonicRegression (not deprecated CalibratedClassifierCV)
- Created evaluation utilities: Brier scores (per-fold + aggregate), naive baseline, calibration curves, season bar charts
- All 11 new tests pass, full suite green at 95 tests

## Task Commits

Each task was committed atomically:

1. **Task 1: Create src/models/ package with feature sets, model factories, and calibration** - `c588a2f` (feat)
2. **Task 2: Create backtest loop and evaluation utilities** - `7e50589` (feat)
3. **Task 3: Create test suites for models and backtest modules** - `33faf3a` (test)

## Files Created/Modified
- `src/models/__init__.py` - Package init with module docstring listing all submodules
- `src/models/feature_sets.py` - FULL_FEATURE_COLS (14), CORE_FEATURE_COLS (13), TARGET_COL, JOIN_KEYS, META_COLS
- `src/models/train.py` - make_lr_pipeline, make_rf_pipeline, make_xgb_model factory functions
- `src/models/calibrate.py` - calibrate_model using IsotonicRegression(out_of_bounds='clip')
- `src/models/backtest.py` - FOLD_MAP, generate_folds, run_backtest, run_all_models
- `src/models/evaluate.py` - compute_brier_scores, compute_naive_baseline_brier, get_calibration_data, plot_calibration_curves, plot_brier_by_season
- `tests/test_models.py` - 5 tests covering LR/RF/XGB training, isotonic calibration, calibration curves
- `tests/test_backtest.py` - 6 tests covering fold structure, overlaps, 2020 exclusion, NaN exclusion, Brier scores, results schema

## Decisions Made
- Used IsotonicRegression directly (not CalibratedClassifierCV cv='prefit') per sklearn 1.8.0 API removal
- Omitted LogisticRegression penalty= parameter (deprecated in sklearn 1.8.0) and XGBClassifier use_label_encoder (removed in xgboost 2.x)
- Excluded xwoba_diff from all feature sets (100% NaN in feature matrix); core set defined as full minus sp_recent_era_diff
- XGBoost early stopping validation split is last 20% of training window (temporally ordered), not calibration season
- feature_set_name passed as explicit string parameter to run_backtest, not inferred from column contents
- All calibration logic is data-length-agnostic (no hardcoded game counts) to handle 2020's ~891-game calibration set

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- src/models/ package fully importable and tested
- Plan 03-02 (notebooks) can call run_all_models, compute_brier_scores, plot_calibration_curves as thin wrappers
- Results schema includes Phase 4 join keys (game_date, home_team, away_team) for Kalshi comparison

## Self-Check: PASSED

All 8 created files verified on disk. All 3 task commits (c588a2f, 7e50589, 33faf3a) verified in git log. 95 tests passing.

---
*Phase: 03-model-training-and-backtesting*
*Completed: 2026-03-29*
