# Deferred Items - Phase 14

## Pre-existing Test Failures (Out of Scope)

Observed during 14-03 verification. All predate Phase 14 changes.

1. **test_feature_builder.py::test_rolling_ops** - Rolling OPS NaN assertion fails because Opening Day NaN imputation fills early-season values with 0.0 instead of leaving NaN. Last modified in Phase 5.
2. **test_leakage.py::test_shift1_prevents_current_game_leakage** - Same root cause as above (rolling_ops_diff is 0.0 not NaN for early games).
3. **test_pipeline/test_live_features.py::test_live_feature_builder_season_and_date** - LiveFeatureBuilder now passes [2024, 2025] seasons instead of [2025] alone. Test expectation outdated.
