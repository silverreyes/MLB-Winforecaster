---
phase: 03-model-training-and-backtesting
plan: 02
subsystem: models
tags: [jupyter, notebooks, brier-score, calibration-curves, walk-forward, model-comparison]

# Dependency graph
requires:
  - phase: 03-model-training-and-backtesting (plan 01)
    provides: "src/models/ package with backtest loop, evaluation utilities, model factories"
provides:
  - "Notebook 09: walk-forward backtest runner with cache-before-compute pattern"
  - "Notebook 10: standalone model comparison with Brier scores, calibration curves, per-season accuracy"
  - "data/results/backtest_results.parquet with per-game predictions and Phase 4 join keys"
affects: [04-market-comparison]

# Tech tracking
tech-stack:
  added: []
  patterns: [thin-notebook-wrapper, cache-before-compute, standalone-comparison-notebook]

key-files:
  created:
    - notebooks/09_model_training.ipynb
    - notebooks/10_model_comparison.ipynb
    - data/results/backtest_results.parquet
  modified: []

key-decisions:
  - "No new decisions -- notebooks follow established thin-wrapper pattern from Phases 1 and 2"

patterns-established:
  - "Cache-before-compute: NB09 checks if results Parquet exists before running expensive backtest"
  - "Standalone comparison: NB10 loads saved results without importing backtest -- no training dependency"

requirements-completed: [EVAL-04]

# Metrics
duration: 10min
completed: 2026-03-29
---

# Phase 3 Plan 2: Training and Comparison Notebooks Summary

**Walk-forward backtest notebook (09) and side-by-side model comparison notebook (10) with Brier scores, calibration curves, and per-season accuracy for LR/RF/XGBoost on full and core feature sets**

## Performance

- **Duration:** 10 min (includes checkpoint wait for user verification)
- **Started:** 2026-03-29T07:44:00Z
- **Completed:** 2026-03-29T07:54:00Z
- **Tasks:** 2
- **Files created:** 2 notebooks + 1 results Parquet

## Accomplishments
- Created notebook 09 that runs all 3 models (LR, RF, XGBoost) on both feature sets via walk-forward backtest and saves results to data/results/backtest_results.parquet
- Created notebook 10 that loads saved results standalone (no training) and displays aggregate Brier scores, per-season Brier scores, calibration curves for both feature sets, full-vs-core feature comparison, and per-season accuracy
- User verified both notebooks produce correct outputs: Brier scores in expected range, calibration curves and per-season accuracy look good
- Results Parquet preserves Phase 4 join keys (game_date, home_team, away_team) for Kalshi market comparison

## Task Commits

Each task was committed atomically:

1. **Task 1: Create training notebook 09 and comparison notebook 10** - `b205f67` (feat)
2. **Task 2: Verify training and comparison notebooks produce correct outputs** - human-verify checkpoint (approved)

## Files Created/Modified
- `notebooks/09_model_training.ipynb` - Thin wrapper calling run_all_models() with cache-before-compute pattern, fold map display, results summary, and quick Brier preview
- `notebooks/10_model_comparison.ipynb` - Standalone comparison loading backtest_results.parquet with aggregate Brier table (incl. naive baseline), per-season Brier tables and bar charts, calibration curves for both feature sets, full-vs-core comparison, per-season accuracy, and summary
- `data/results/backtest_results.parquet` - Per-game predictions for all model/feature-set/fold combinations with Phase 4 join keys

## Decisions Made
None - followed plan as specified. Both notebooks use the established thin-wrapper pattern from Phases 1 and 2.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 3 complete: all 3 models trained, calibrated, and evaluated via walk-forward backtest
- data/results/backtest_results.parquet ready for Phase 4 Kalshi market comparison join
- Join keys (game_date, home_team, away_team) preserved in results for market price matching
- Phase 4 blocker remains: last_price_dollars is settlement closing price, need pre-game opening price

## Self-Check: PASSED

All 3 files verified on disk (notebooks/09_model_training.ipynb, notebooks/10_model_comparison.ipynb, 03-02-SUMMARY.md). Task 1 commit (b205f67) verified in git log. Task 2 approved by user at checkpoint.

---
*Phase: 03-model-training-and-backtesting*
*Completed: 2026-03-29*
