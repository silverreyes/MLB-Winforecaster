---
phase: 06-model-retrain-and-calibration
plan: 02
subsystem: models
tags: [walk-forward-backtest, logistic-regression, random-forest, xgboost, isotonic-calibration, joblib, brier-score]

# Dependency graph
requires:
  - phase: 06-model-retrain-and-calibration/plan-01
    provides: "VIF/SHAP pruned feature set (17 features from 20 SP_ENHANCED)"
  - phase: 05-sp-feature-integration
    provides: "feature_store_v2.parquet, SP_ENHANCED_FEATURE_COLS, TEAM_ONLY_FEATURE_COLS"
provides:
  - "6 joblib model artifacts (LR/RF/XGBoost x TEAM_ONLY/SP_ENHANCED_PRUNED) with bundled IsotonicRegression calibrators"
  - "model_metadata.json with training date, fold Brier scores, feature lists, calibration method"
  - "backtest_results_v2.parquet (68K rows, 6 combos, 5 folds)"
  - "predictions_2025_v2.parquet (13.7K rows, 6 combos)"
  - "SP_ENHANCED_PRUNED_COLS constant (17 features post-VIF)"
  - "run_all_v2_models, run_backtest_with_artifact, predict_2025_v2 functions"
affects: [06-03, phase-07-pipeline, phase-08-api-dashboard, brier-comparison]

# Tech tracking
tech-stack:
  added: []
  patterns: [walk-forward backtest with artifact capture, inline isotonic calibration for calibrator persistence, joblib artifact bundling (model+calibrator+feature_cols)]

key-files:
  created:
    - models/artifacts/model_metadata.json
    - models/artifacts/lr_team_only.joblib
    - models/artifacts/lr_sp_enhanced.joblib
    - models/artifacts/rf_team_only.joblib
    - models/artifacts/rf_sp_enhanced.joblib
    - models/artifacts/xgb_team_only.joblib
    - models/artifacts/xgb_sp_enhanced.joblib
    - tests/test_v2_backtest.py
    - tests/test_artifacts.py
    - notebooks/14_v2_model_training.ipynb
    - scripts/run_v2_training.py
  modified:
    - src/models/backtest.py
    - src/models/predict.py
    - src/models/feature_sets.py
    - .gitignore

key-decisions:
  - "SP_ENHANCED uses pruned 17-feature set (SP_ENHANCED_PRUNED_COLS) from Plan 06-01 VIF/SHAP analysis"
  - "TEAM_ONLY kept at original 9 features (VIF pruning was SP_ENHANCED-specific)"
  - "Artifact dict bundles: model + calibrator + feature_cols + model_name + feature_set"
  - "Inline isotonic calibration in run_backtest_with_artifact to capture fitted IsotonicRegression object"
  - "Joblib files gitignored (binary); model_metadata.json committed (lightweight, human-readable)"

patterns-established:
  - "Artifact persistence: joblib dict with keys model/calibrator/feature_cols/model_name/feature_set"
  - "V2_COMBINATIONS constant: tuple of (name, factory, feature_cols, feature_set_name, is_xgb)"
  - "run_backtest_with_artifact returns (results_df, artifact_dict) for combined training + persistence"

requirements-completed: [MDL-01, MDL-02, MDL-07]

# Metrics
duration: 9min
completed: 2026-03-30
---

# Phase 6 Plan 2: V2 Model Training Summary

**6 walk-forward backtested models (LR/RF/XGBoost x TEAM_ONLY/SP_ENHANCED_PRUNED) trained with IsotonicRegression calibrators and persisted as joblib artifacts with metadata JSON**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-30T01:20:36Z
- **Completed:** 2026-03-30T01:30:22Z
- **Tasks:** 2
- **Files modified:** 14

## Accomplishments
- 6 v2 model artifacts trained via 5-fold walk-forward backtest on feature_store_v2 and persisted as joblib bundles
- Each artifact bundles fitted model + fitted IsotonicRegression calibrator + feature column list
- model_metadata.json records training provenance, per-fold Brier scores, and calibration method for all 6 models
- SP_ENHANCED models consistently outperform TEAM_ONLY (LR: 0.2331 vs 0.2374, RF: 0.2342 vs 0.2383, XGB: 0.2349 vs 0.2397 aggregate Brier)
- v2 backtest results (68,058 rows) and 2025 predictions (13,674 rows) ready for Plan 03 Brier comparison

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend backtest.py and predict.py for v2 model combinations (TDD)**
   - `bd6bf3c` (test: add failing tests for v2 backtest and artifact serialization)
   - `9cb3318` (feat: implement v2 backtest with 6 model/feature-set combinations)
2. **Task 2: Run v2 training and persist artifacts** - `7f318a2` (feat)

## Files Created/Modified
- `src/models/feature_sets.py` - Added SP_ENHANCED_PRUNED_COLS (17 features post-VIF/SHAP)
- `src/models/backtest.py` - Added V2_FOLD_MAP, V2_COMBINATIONS, run_backtest_with_artifact, run_all_v2_models
- `src/models/predict.py` - Added predict_2025_v2 with 6 model/feature-set combos
- `tests/test_v2_backtest.py` - 7 tests for v2 backtest infrastructure
- `tests/test_artifacts.py` - 2 tests for artifact round-trip and metadata JSON schema
- `models/artifacts/model_metadata.json` - Training metadata for all 6 models
- `models/artifacts/*.joblib` - 6 model artifacts (gitignored binary files)
- `notebooks/14_v2_model_training.ipynb` - V2 training notebook
- `scripts/run_v2_training.py` - Standalone training script
- `.gitignore` - Added models/artifacts/*.joblib exclusion

## Brier Score Results

| Model | Feature Set | Aggregate Brier | Best Fold | Worst Fold |
|-------|-------------|----------------|-----------|------------|
| LR    | sp_enhanced | 0.2331         | 2022 (0.2278) | 2024 (0.2374) |
| LR    | team_only   | 0.2374         | 2019 (0.2333) | 2023 (0.2400) |
| RF    | sp_enhanced | 0.2342         | 2022 (0.2302) | 2024 (0.2369) |
| RF    | team_only   | 0.2383         | 2022 (0.2344) | 2024 (0.2411) |
| XGB   | sp_enhanced | 0.2349         | 2022 (0.2303) | 2019 (0.2337) |
| XGB   | team_only   | 0.2397         | 2022 (0.2347) | 2024 (0.2427) |

Best overall: LR sp_enhanced (0.2331). SP features improve Brier by 0.004-0.005 across all model types.

## Decisions Made
- **SP_ENHANCED_PRUNED_COLS as v2 default**: Used the 17-feature set from Plan 06-01 VIF/SHAP analysis (3 dropped: is_home, team_woba_diff, sp_siera_diff) rather than the full 20-feature SP_ENHANCED set
- **TEAM_ONLY unchanged**: Kept original 9 features since VIF was run on SP_ENHANCED specifically; TEAM_ONLY has its own independent validation purpose
- **Inline calibration for artifact capture**: run_backtest_with_artifact uses inline IsotonicRegression instead of calling calibrate_model, to capture the fitted calibrator for serialization
- **Joblib gitignored**: Binary model files (20-50KB each) excluded from git; metadata JSON committed for provenance tracking

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] jupyter nbconvert CWD issue on Windows**
- **Found during:** Task 2 (notebook execution)
- **Issue:** jupyter nbconvert runs notebook kernel in a different working directory on Windows, causing FileNotFoundError for relative paths
- **Fix:** Created `scripts/run_v2_training.py` as a standalone script executed via `python -m scripts.run_v2_training` from project root. Notebook updated with os.chdir for interactive use.
- **Files modified:** scripts/run_v2_training.py, notebooks/14_v2_model_training.ipynb
- **Verification:** Script runs successfully, all artifacts produced
- **Committed in:** 7f318a2 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minor execution path change (script vs nbconvert). All outputs identical. No scope creep.

## Issues Encountered
None beyond the nbconvert CWD issue documented in deviations.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- 6 model artifacts ready for Plan 06-03 Brier comparison analysis
- backtest_results_v2.parquet and predictions_2025_v2.parquet available for v1-vs-v2 comparison
- model_metadata.json provides fold-level Brier scores for comparison table
- Artifacts in exact format Phase 7 pipeline will consume (joblib dict with model/calibrator/feature_cols)

## Self-Check: PASSED

All 14 files verified on disk. All 3 commits verified in git log.

---
*Phase: 06-model-retrain-and-calibration*
*Completed: 2026-03-30*
