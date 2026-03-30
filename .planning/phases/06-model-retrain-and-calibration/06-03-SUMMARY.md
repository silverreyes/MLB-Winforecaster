---
phase: 06-model-retrain-and-calibration
plan: 03
subsystem: models
tags: [brier-score, calibration, reliability-diagram, kalshi-comparison, production-readiness]

# Dependency graph
requires:
  - phase: 06-model-retrain-and-calibration/plan-02
    provides: "6 model artifacts, backtest_results_v2.parquet, predictions_2025_v2.parquet"
  - phase: 05-sp-feature-integration
    provides: "feature_store_v2.parquet, SP_ENHANCED_FEATURE_COLS, TEAM_ONLY_FEATURE_COLS"
provides:
  - "Brier comparison table: v2 SP_ENHANCED vs v2 TEAM_ONLY vs v1 vs Kalshi on 2,128 identical 2025 games"
  - "Reliability diagrams (calibration curves) for all 6 v2 model/feature-set combinations"
  - "Production-readiness declaration: all 6 v2 models approved after visual inspection"
  - "generate_v2_comparison.py script for reproducible comparison generation"
affects: [phase-07-pipeline, phase-08-api-dashboard, phase-09-portfolio-brier-table]

# Tech tracking
tech-stack:
  added: []
  patterns: [apples-to-apples comparison on game-set intersection, reliability diagram visual inspection gate]

key-files:
  created:
    - data/results/brier_comparison.csv
    - data/results/reliability_team_only.png
    - data/results/reliability_sp_enhanced.png
    - notebooks/15_v2_model_comparison.ipynb
    - scripts/generate_v2_comparison.py
    - tests/test_v2_evaluation.py
  modified: []

key-decisions:
  - "v2 SP_ENHANCED RF is the best single model (Brier 0.2371), beating Kalshi market (0.2434) by 0.0063"
  - "All 6 v2 models declared production-ready after human visual inspection of reliability diagrams"
  - "SP_ENHANCED improves over TEAM_ONLY by 0.005-0.007 Brier across all model types on identical 2025 games"
  - "v2 SP_ENHANCED beats v1 best (LR 0.2399) by 0.0028 on the 2,128-game common set"

patterns-established:
  - "Visual inspection gate: reliability diagrams must be human-approved before production-readiness declaration"
  - "Apples-to-apples comparison: intersection of v2/v1/Kalshi game sets ensures identical evaluation samples"

requirements-completed: [MDL-03, MDL-04]

# Metrics
duration: 12min
completed: 2026-03-30
---

# Phase 6 Plan 3: V2 Model Evaluation Summary

**Brier comparison table on 2,128 identical 2025 games shows v2 SP_ENHANCED RF (0.2371) beats Kalshi market (0.2434); reliability diagrams visually approved, all 6 models declared production-ready**

## Performance

- **Duration:** 12 min (including checkpoint pause for human review)
- **Started:** 2026-03-29T23:42:00Z
- **Completed:** 2026-03-30T02:53:00Z
- **Tasks:** 2 (1 auto + 1 human-verify checkpoint)
- **Files modified:** 6

## Accomplishments
- Brier comparison table generated on 2,128-game intersection (all four sources: v2 SP_ENHANCED, v2 TEAM_ONLY, v1, Kalshi market)
- v2 SP_ENHANCED RF achieves best Brier score (0.2371), outperforming Kalshi market (0.2434) by 0.0063
- Reliability diagrams generated for all 6 v2 model/feature-set combinations and visually inspected
- Human approved calibration quality -- all 6 models declared production-ready for Phase 7 pipeline

## Brier Score Comparison (2,128 identical 2025 games)

| Group | Best Model | Brier Score | vs Kalshi |
|-------|-----------|-------------|-----------|
| v2 SP_ENHANCED | RF | 0.2371 | -0.0063 (better) |
| v2 SP_ENHANCED | LR | 0.2376 | -0.0058 (better) |
| v2 SP_ENHANCED | XGB | 0.2382 | -0.0052 (better) |
| v1 | LR | 0.2399 | -0.0035 (better) |
| v1 | RF | 0.2408 | -0.0026 (better) |
| v1 | XGB | 0.2425 | -0.0009 (better) |
| v2 TEAM_ONLY | LR | 0.2429 | -0.0005 (better) |
| Kalshi Market | market | 0.2434 | baseline |
| v2 TEAM_ONLY | XGB | 0.2436 | +0.0002 (worse) |
| v2 TEAM_ONLY | RF | 0.2439 | +0.0005 (worse) |

Key findings:
- All v2 SP_ENHANCED models beat Kalshi market pricing
- SP_ENHANCED improves over TEAM_ONLY by 0.005-0.007 Brier across all model types
- v2 SP_ENHANCED beats v1 best model (LR 0.2399) by 0.0028
- TEAM_ONLY models are roughly at Kalshi-market level (within 0.0005)

## Task Commits

Each task was committed atomically:

1. **Task 1: Generate Brier comparison table and reliability diagrams (TDD)**
   - `5d7e115` (test: add failing tests for Brier comparison and reliability diagrams)
   - `1ff0136` (feat: Brier comparison table and reliability diagrams for v2 models)
2. **Task 2: Visual inspection of reliability diagrams** -- checkpoint:human-verify, approved by user

## Files Created/Modified
- `data/results/brier_comparison.csv` - 4-group Brier comparison table (11 rows: 3 models each for v2_sp_enhanced, v2_team_only, v1, plus Kalshi market)
- `data/results/reliability_team_only.png` - Reliability diagram for TEAM_ONLY feature set (LR/RF/XGB)
- `data/results/reliability_sp_enhanced.png` - Reliability diagram for SP_ENHANCED feature set (LR/RF/XGB)
- `notebooks/15_v2_model_comparison.ipynb` - Comparison notebook with Brier table generation and reliability diagrams
- `scripts/generate_v2_comparison.py` - Standalone script for reproducible comparison generation
- `tests/test_v2_evaluation.py` - 4 tests: four_groups, same_n_games, valid_scores, required_columns

## Decisions Made
- **RF is best v2 model**: v2 SP_ENHANCED RF (0.2371) edges out LR (0.2376) on the 2,128-game common set, though LR was best in aggregate backtest (0.2331) -- difference is game set and fold composition
- **All 6 models approved**: Human reviewed reliability diagrams for both feature sets; SP_ENHANCED models well-calibrated, TEAM_ONLY shows slightly higher deviation at extremes but acceptable
- **No temperature scaling needed**: IsotonicRegression calibration confirmed sufficient; reliability diagrams show no systematic miscalibration requiring alternative calibration

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 6 complete: all 6 v2 model artifacts trained, calibrated, evaluated, and declared production-ready
- Artifacts ready for Phase 7 pipeline consumption: joblib dicts with model/calibrator/feature_cols
- Brier comparison data available for Phase 9 portfolio page
- Reliability diagram PNGs available for Phase 9 portfolio page

## Self-Check: PASSED

All 6 files verified on disk. Both task commits verified in git log.

---
*Phase: 06-model-retrain-and-calibration*
*Completed: 2026-03-30*
