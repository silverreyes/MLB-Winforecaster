---
phase: 07-live-pipeline-and-database
plan: 02
subsystem: pipeline
tags: [live-features, inference, joblib, kalshi-api, statsapi, feature-builder]

# Dependency graph
requires:
  - phase: 06-model-retrain-and-evaluation
    provides: 6 model artifacts (LR/RF/XGB x team_only/sp_enhanced) with calibrators
  - phase: 05-sp-feature-integration
    provides: FeatureBuilder with SP features, feature_sets.py column definitions
provides:
  - LiveFeatureBuilder class for constructing features from today's game data
  - Inference module (load_all_artifacts, predict_game) for model prediction
  - fetch_today_schedule for live game schedule
  - fetch_kalshi_live_prices for open market prices
affects: [07-03-pipeline-runner, 08-api-and-dashboard]

# Tech tracking
tech-stack:
  added: []
  patterns: [adapter-pattern-for-live-features, graceful-degradation-for-external-apis]

key-files:
  created:
    - src/pipeline/live_features.py
    - src/pipeline/inference.py
    - tests/test_pipeline/test_inference.py
    - tests/test_pipeline/test_live_features.py
  modified:
    - src/data/mlb_schedule.py
    - src/data/kalshi.py

key-decisions:
  - "LiveFeatureBuilder delegates to FeatureBuilder private methods (accepted coupling risk for v1)"
  - "fetch_kalshi_live_prices uses yes_team==home_code check (adapted from _parse_ticker return format)"
  - "predict_game clips probabilities to [0.01, 0.99] range for numerical safety"
  - "fetch_kalshi_live_prices returns empty dict on API failure (graceful degradation)"

patterns-established:
  - "Adapter pattern: LiveFeatureBuilder wraps FeatureBuilder with as_of_date=today for temporal safety"
  - "Graceful degradation: External API failures return empty results, not exceptions"
  - "Artifact loading: Fail hard on missing artifacts (startup-time detection, not runtime)"

requirements-completed: [PIPE-02, PIPE-03, PIPE-05]

# Metrics
duration: 4min
completed: 2026-03-30
---

# Phase 7 Plan 2: Live Pipeline Data Adapters Summary

**LiveFeatureBuilder adapter wrapping FeatureBuilder for single-day inference, plus model artifact loading and live Kalshi/schedule data fetchers**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-30T03:18:22Z
- **Completed:** 2026-03-30T03:22:52Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- LiveFeatureBuilder reuses FeatureBuilder infrastructure for live feature construction with temporal safety (as_of_date=today)
- Inference module loads 6 model artifacts at startup and produces calibrated P(home_win) per model with NaN safety and probability clipping
- Data modules extended with fetch_today_schedule (non-final games) and fetch_kalshi_live_prices (open markets with graceful degradation)
- 13 tests covering artifact loading, prediction, feature builder initialization, team normalization, and SP confirmation

## Task Commits

Each task was committed atomically:

1. **Task 1: Add fetch_today_schedule and fetch_kalshi_live_prices** - `e92ee5d` (feat)
2. **Task 2: Create LiveFeatureBuilder, inference module, and tests** - `21a1da4` (feat)

## Files Created/Modified
- `src/pipeline/live_features.py` - LiveFeatureBuilder class wrapping FeatureBuilder for today's games
- `src/pipeline/inference.py` - load_all_artifacts and predict_game for model inference
- `src/data/mlb_schedule.py` - Extended with fetch_today_schedule (no caching, no status filter)
- `src/data/kalshi.py` - Extended with fetch_kalshi_live_prices (open markets, graceful degradation)
- `tests/test_pipeline/test_inference.py` - 6 tests: artifact loading, prediction, NaN handling, clipping
- `tests/test_pipeline/test_live_features.py` - 7 tests: team normalization, TBD pitchers, SP confirmation, initialization

## Decisions Made
- LiveFeatureBuilder delegates to FeatureBuilder private methods (_add_sp_features, _add_offense_features, etc.) -- accepted coupling risk for v1, already tracked in STATE.md as tech debt
- Adapted plan's `parsed.get("is_home_yes")` to `parsed["yes_team"] == parsed["home_code"]` since _parse_ticker returns yes_team/home_code, not is_home_yes
- Used picklable dicts instead of MagicMock for joblib dump/load tests (MagicMock cannot be pickled)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed _parse_ticker return format mismatch in fetch_kalshi_live_prices**
- **Found during:** Task 1
- **Issue:** Plan referenced `parsed.get("is_home_yes")` but `_parse_ticker` returns `yes_team` and `home_code` separately, not an `is_home_yes` boolean
- **Fix:** Used `parsed["yes_team"] != parsed["home_code"]` check instead
- **Files modified:** src/data/kalshi.py
- **Verification:** Import test passes, logic matches existing _parse_market pattern

**2. [Rule 1 - Bug] Fixed MagicMock pickle failure in artifact loading tests**
- **Found during:** Task 2
- **Issue:** MagicMock objects cannot be serialized by joblib.dump, causing test_load_all_artifacts_success to fail with PicklingError
- **Fix:** Created _make_picklable_artifact helper using plain dicts for joblib tests, kept MagicMock for predict_game tests that don't touch disk
- **Files modified:** tests/test_pipeline/test_inference.py
- **Verification:** All 13 tests pass

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- LiveFeatureBuilder, inference module, and data fetchers ready for Plan 03 (pipeline runner)
- Pipeline runner will orchestrate: fetch schedule -> build features -> run inference -> store predictions -> fetch Kalshi prices
- DB layer from Plan 01 ready for prediction storage

## Self-Check: PASSED

All 6 files verified present on disk. Both task commits (e92ee5d, 21a1da4) verified in git log.

---
*Phase: 07-live-pipeline-and-database*
*Completed: 2026-03-30*
