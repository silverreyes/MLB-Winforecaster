---
phase: 04-kalshi-market-comparison-and-edge-analysis
plan: 01
subsystem: models, data
tags: [kalshi, edge-analysis, prediction, candlestick-api, fee-model, isotonic-calibration]

# Dependency graph
requires:
  - phase: 03-model-training-and-backtesting
    provides: model factories (train.py), calibration (calibrate.py), feature sets, backtest schema
  - phase: 01-data-ingestion-and-raw-cache
    provides: kalshi.py market loader, cache infrastructure, team_mappings
provides:
  - predict_2025() single-fold runner producing predictions with backtest_results schema
  - fetch_kalshi_open_prices() for pre-game opening price via candlestick API
  - compute_edge_signals() with configurable threshold for edge identification
  - compute_fee_adjusted_pnl() with KALSHI_FEE_RATE=0.07 fee-on-profits formula
  - Comprehensive tests covering MARKET-01 through MARKET-04
affects: [04-02 notebooks, Phase 4 edge analysis, Phase 4 Kalshi comparison]

# Tech tracking
tech-stack:
  added: []
  patterns: [single-fold prediction reusing model factories, batch candlestick API fetching, edge-threshold analysis, fee-adjusted P&L]

key-files:
  created:
    - src/models/predict.py
    - src/models/edge.py
    - tests/test_edge.py
  modified:
    - src/data/kalshi.py
    - tests/test_kalshi.py
    - tests/test_models.py

key-decisions:
  - "predict_2025 follows exact backtest.py pattern: rolling_ops_diff NaN filter, XGBoost early stopping on last 20%, isotonic calibration"
  - "fetch_kalshi_open_prices groups requests by date for batch API efficiency (one call per game day)"
  - "Fixed np.True_ identity check in test assertions (use == instead of is for numpy booleans)"

patterns-established:
  - "Single-fold prediction: train on range, calibrate on N-1, predict on N -- same schema as backtest_results"
  - "Edge signal: |model_prob - market_price| > configurable threshold with BUY_YES/BUY_NO position assignment"
  - "Fee-adjusted P&L: fee on profits only (KALSHI_FEE_RATE applied to winning side net)"

requirements-completed: [MARKET-01, MARKET-02, MARKET-03, MARKET-04]

# Metrics
duration: 5min
completed: 2026-03-29
---

# Phase 4 Plan 01: Library Code Summary

**predict_2025 fold runner, Kalshi candlestick open price fetcher, and edge/fee analysis module with 51 passing tests**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-29T14:12:32Z
- **Completed:** 2026-03-29T14:17:18Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Created predict_2025() that trains LR/RF/XGBoost on 2015-2023, calibrates on 2024, predicts 2025 using core feature set with output matching backtest_results schema
- Created edge.py with KALSHI_FEE_RATE=0.07, compute_edge_signals() with configurable threshold (default 5pp), and compute_fee_adjusted_pnl() implementing correct fee-on-profits-only formula for all four BUY_YES/BUY_NO win/lose cases
- Extended kalshi.py with fetch_kalshi_open_prices() that fetches daily price.open_dollars via batch candlestick API grouped by date
- Added 51 tests covering MARKET-01 through MARKET-04 requirements

## Task Commits

Each task was committed atomically:

1. **Task 1: Create predict.py, edge.py, and extend kalshi.py** - `a1326fb` (feat)
2. **Task 2: Create comprehensive tests** - `b8ac36e` (test)

## Files Created/Modified
- `src/models/predict.py` - Single-fold 2025 prediction runner reusing existing model factories and calibration
- `src/models/edge.py` - Edge identification (configurable threshold) and fee-adjusted P&L computation
- `src/data/kalshi.py` - Extended with fetch_kalshi_open_prices() for batch candlestick API
- `tests/test_edge.py` - Tests for edge signals and fee-adjusted P&L (MARKET-03, MARKET-04)
- `tests/test_kalshi.py` - Extended with open price fetch tests (MARKET-01)
- `tests/test_models.py` - Extended with predict_2025 tests (MARKET-02)

## Decisions Made
- predict_2025 follows exact backtest.py pattern: rolling_ops_diff NaN filter, XGBoost early stopping on temporal 20% split, isotonic calibration via calibrate_model
- fetch_kalshi_open_prices groups market tickers by date and makes one batch candlestick API call per date for efficiency
- Fixed np.True_ vs True identity mismatch in test assertions by using == instead of is (numpy boolean scalar is not Python True)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed numpy boolean identity comparison in tests**
- **Found during:** Task 2 (test creation)
- **Issue:** Plan's test code used `assert result.iloc[0]["has_edge"] is True` which fails because pandas returns numpy.bool_ (not Python bool), and `np.True_ is True` is False
- **Fix:** Changed `is True` to `== True` and `is False` to `== False` in three test assertions
- **Files modified:** tests/test_edge.py
- **Verification:** All 14 test_edge.py tests pass
- **Committed in:** b8ac36e (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Minor test assertion fix. No scope creep.

## Issues Encountered
None beyond the numpy boolean fix documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All Phase 4 library code ready for notebook consumption (Plan 02)
- predict_2025() ready to be called from notebook 11 with 2025 feature matrix
- fetch_kalshi_open_prices() ready to enrich kalshi_game_winners.parquet
- compute_edge_signals() and compute_fee_adjusted_pnl() ready for notebook 12

## Self-Check: PASSED

- All 6 files exist on disk
- Both task commits (a1326fb, b8ac36e) found in git log
- All 51 tests pass across test_edge.py, test_kalshi.py, test_models.py

---
*Phase: 04-kalshi-market-comparison-and-edge-analysis*
*Completed: 2026-03-29*
