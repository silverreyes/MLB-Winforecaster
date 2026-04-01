# Phase 15: Deferred Items

## Pre-existing Test Failure

- **File:** `tests/test_feature_builder.py::test_rolling_ops`
- **Issue:** Test expects NaN for early-season rolling_ops_diff but gets 0.0 (likely due to imputation changes)
- **Discovered during:** Plan 15-02 execution (full suite regression check)
- **Not related to:** Phase 15 changes (live score polling)
