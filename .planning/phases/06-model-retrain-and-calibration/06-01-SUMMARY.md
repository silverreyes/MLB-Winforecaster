---
phase: 06-model-retrain-and-calibration
plan: 01
subsystem: models
tags: [vif, shap, feature-selection, xgboost, multicollinearity, sklearn]

# Dependency graph
requires:
  - phase: 05-sp-feature-integration
    provides: "SP_ENHANCED_FEATURE_COLS (20 features), FeatureBuilder.build_and_save_v2, feature_store_v2.parquet"
provides:
  - "VIF module (src/models/vif.py) with compute_vif function"
  - "SHAP module (src/models/shap_analysis.py) with compute_shap_importance function"
  - "VIF analysis results (data/results/vif_analysis.csv)"
  - "Pruned feature set: 17 features (3 dropped by VIF, 0 by SHAP)"
  - "Feature analysis notebook (notebooks/13_v2_feature_analysis.ipynb)"
affects: [06-02, 06-03, model-retrain, feature-sets]

# Tech tracking
tech-stack:
  added: [shap 0.51.0 (already installed)]
  patterns: [sklearn LinearRegression for VIF (no statsmodels), SHAP TreeExplainer for feature importance]

key-files:
  created:
    - src/models/vif.py
    - src/models/shap_analysis.py
    - tests/test_vif.py
    - tests/test_shap_analysis.py
    - notebooks/13_v2_feature_analysis.ipynb
    - data/results/vif_analysis.csv
  modified: []

key-decisions:
  - "VIF pruning removed 3 features: is_home (constant=inf VIF), team_woba_diff (VIF=163, redundant with team_ops_diff), sp_siera_diff (VIF=18, redundant with sp_fip_diff/sp_xfip_diff)"
  - "SHAP analysis kept all 17 remaining features -- none below 0.1% importance threshold"
  - "Final v2 pruned feature set: 17 features (from original 20 SP_ENHANCED)"

patterns-established:
  - "VIF via sklearn LinearRegression R^2 method (avoids statsmodels dependency)"
  - "SHAP TreeExplainer for XGBoost feature importance ranking"
  - "Iterative VIF pruning: drop highest VIF feature, recompute, repeat until all VIF <= 10"

requirements-completed: [MDL-05, MDL-06]

# Metrics
duration: 6min
completed: 2026-03-30
---

# Phase 6 Plan 1: Feature Selection Summary

**VIF multicollinearity and SHAP importance analysis pruned 20 SP_ENHANCED features to 17, removing is_home (constant), team_woba_diff (redundant), and sp_siera_diff (redundant FIP-family)**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-30T01:11:27Z
- **Completed:** 2026-03-30T01:17:24Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- VIF module computing multicollinearity via sklearn LinearRegression (no statsmodels dependency)
- SHAP TreeExplainer wrapper for XGBoost feature importance ranking with percentage-of-total
- Full VIF/SHAP analysis on 20 SP_ENHANCED features: 3 pruned by VIF, 0 by SHAP
- 8 unit tests (4 VIF + 4 SHAP) all passing, full test suite green

## Task Commits

Each task was committed atomically:

1. **Task 1: Create VIF and SHAP analysis modules with tests (TDD)**
   - `d9219af` (test: add failing tests for VIF and SHAP modules)
   - `f625960` (feat: implement VIF and SHAP analysis modules)
2. **Task 2: Build v2 feature store and run VIF/SHAP feature analysis** - `b3e3f44` (feat)

## Files Created/Modified
- `src/models/vif.py` - VIF computation via sklearn LinearRegression R^2 method
- `src/models/shap_analysis.py` - SHAP TreeExplainer wrapper for feature importance
- `tests/test_vif.py` - 4 VIF unit tests (dataframe shape, perfect collinearity, independent, nan-free)
- `tests/test_shap_analysis.py` - 4 SHAP unit tests (dataframe shape, feature names, pct sum, sorted)
- `notebooks/13_v2_feature_analysis.ipynb` - Full VIF/SHAP analysis notebook (5 cells)
- `data/results/vif_analysis.csv` - VIF results for all 20 SP_ENHANCED features (gitignored)

## Analysis Results

### VIF Analysis (all 20 SP_ENHANCED features)

| Feature | VIF | Action |
|---------|-----|--------|
| is_home | inf | DROPPED (constant column = 1 for all rows) |
| team_woba_diff | 162.74 | DROPPED (redundant with team_ops_diff) |
| team_ops_diff | 156.01 | KEPT (team_woba_diff dropped first) |
| sp_siera_diff | 17.93 | DROPPED (redundant FIP-family metric) |
| sp_xfip_diff | 15.51 | KEPT (VIF dropped to 4.32 after sp_siera_diff removed) |
| All others | < 10 | KEPT |

### SHAP Analysis (17 post-VIF features)

Top 5 by importance:
1. pyth_win_pct_diff (27.2%)
2. sp_whip_diff (26.8%)
3. sp_fip_diff (11.4%)
4. sp_era_diff (8.1%)
5. team_ops_diff (6.0%)

All 17 features above 0.1% threshold -- none pruned by SHAP.

### Final Feature Set (17 features)

sp_fip_diff, sp_xfip_diff, sp_k_bb_pct_diff, sp_whip_diff, sp_era_diff,
sp_recent_era_diff, sp_recent_fip_diff, sp_pitch_count_last_diff, sp_days_rest_diff,
xwoba_diff, team_ops_diff, pyth_win_pct_diff, rolling_ops_diff,
bullpen_era_diff, bullpen_fip_diff, park_factor, log5_home_wp

## Decisions Made
- **VIF threshold = 10**: Standard multicollinearity threshold; iterative removal of worst offender each round
- **is_home dropped**: Constant column (always 1 in home-perspective data), infinite VIF, contributes zero information
- **team_woba_diff dropped over team_ops_diff**: Both measure team batting quality; VIF reduction prioritized dropping the first (highest VIF) feature
- **sp_siera_diff dropped**: Redundant with sp_fip_diff and sp_xfip_diff (all FIP-family metrics); removal brought sp_xfip_diff VIF from 15.5 to 4.3
- **No SHAP pruning**: All 17 post-VIF features contribute meaningfully (lowest: sp_days_rest_diff at 0.22%)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Pruned feature set (17 features) ready for Plan 06-02 (final model training)
- VIF and SHAP modules available for reuse in future analysis
- feature_store_v2.parquet validated and ready for training

## Self-Check: PASSED

All 7 files verified on disk. All 3 commits verified in git log.

---
*Phase: 06-model-retrain-and-calibration*
*Completed: 2026-03-30*
