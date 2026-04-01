# Deferred Items -- Phase 17

## Pre-existing Test Failures (Out of Scope)

These test failures pre-date Phase 17 changes and are not caused by reconciliation work:

1. **tests/test_feature_builder.py::test_rolling_ops** -- Rolling OPS diff expects NaN for early-season games but gets 0.0. Likely caused by Phase 16 FeatureBuilder `_load_from_game_logs` changes.

2. **tests/test_leakage.py::test_shift1_prevents_current_game_leakage** -- Same rolling_ops_diff NaN expectation failure.

3. **tests/test_leakage.py::test_season_boundary_reset** -- Season 2023 game 1 expects NaN rolling_ops_diff but gets 0.0.

4. **tests/test_leakage.py::test_early_season_nan** -- Early-season games expected to have NaN rolling features but all return 0.0.

All 4 failures appear related to the same root cause: `rolling_ops_diff` returning 0.0 instead of NaN for early-season games. This is a Phase 16 FeatureBuilder concern, not a Phase 17 reconciliation issue.
