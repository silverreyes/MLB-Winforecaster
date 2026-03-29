---
phase: 04-kalshi-market-comparison-and-edge-analysis
plan: 02
subsystem: notebooks, models
tags: [kalshi, brier-score, calibration, edge-analysis, fee-model, jupyter, profitability]

# Dependency graph
requires:
  - phase: 04-kalshi-market-comparison-and-edge-analysis
    provides: predict_2025(), fetch_kalshi_open_prices(), compute_edge_signals(), compute_fee_adjusted_pnl()
  - phase: 03-model-training-and-backtesting
    provides: model factories, calibration, feature sets, evaluate utilities
  - phase: 02-feature-engineering-and-feature-store
    provides: FeatureBuilder class for 2025 feature matrix
  - phase: 01-data-ingestion-and-raw-cache
    provides: kalshi.py market loader, cache infrastructure
provides:
  - Notebook 11 (Kalshi comparison) with 2025 Brier score benchmark (3 models vs Kalshi market)
  - Notebook 12 (edge analysis) with fee-adjusted profitability analysis
  - predictions_2025.parquet at data/results/ (separate from backtest_results.parquet)
  - Calibration curves comparing 3 models + Kalshi on same 2025 game set
  - Edge distribution histograms and cumulative P&L visualizations
affects: [final project deliverables, v2 live prediction pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns: [thin-wrapper notebook pattern, standalone notebook loading from parquet, two-track evaluation reporting, configurable edge threshold]

key-files:
  created:
    - notebooks/11_kalshi_comparison.ipynb
    - notebooks/12_edge_analysis.ipynb
  modified: []

key-decisions:
  - "No new decisions -- notebooks follow established thin-wrapper pattern and use library code from Plan 01"

patterns-established:
  - "Two-track evaluation: 2025 Kalshi comparison explicitly labeled as partial benchmark, never conflated with 2015-2024 backtest"
  - "Standalone notebook pattern: notebook 12 loads predictions_2025.parquet from disk, never imports training code"
  - "Fallback price caveat: closing price rows excluded from edge analysis with prominent warning text"

requirements-completed: [MARKET-01, MARKET-02, MARKET-03, MARKET-04]

# Metrics
duration: 5min
completed: 2026-03-29
---

# Phase 4 Plan 02: Notebooks Summary

**Kalshi comparison notebook (Brier benchmark + calibration curves) and edge analysis notebook (fee-adjusted profitability with configurable threshold) completing all MARKET requirements**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-29T14:17:18Z
- **Completed:** 2026-03-29T15:00:00Z
- **Tasks:** 3
- **Files created:** 2

## Accomplishments
- Notebook 11 builds 2025 feature matrix, runs 3 models via predict_2025(), fetches Kalshi opening prices, and displays Brier score comparison table (LR, RF, XGBoost vs Kalshi market) with calibration curves
- Notebook 12 loads predictions_2025.parquet standalone, identifies edge games above configurable threshold (default 5pp), computes fee-adjusted P&L with KALSHI_FEE_RATE=0.07, and displays edge distribution histograms + cumulative P&L charts
- Two-track evaluation language enforced throughout: "partial benchmark" and "2025 season only" clearly distinguish from 2015-2024 primary backtest
- predictions_2025.parquet saved separately from backtest_results.parquet (never merged)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create notebook 11 - Kalshi comparison** - `425ac90` (feat)
2. **Task 2: Create notebook 12 - Edge analysis and fee-adjusted profitability** - `1a832c7` (feat)
3. **Task 3: Verify notebooks run end-to-end** - human-verified checkpoint (approved)

## Files Created/Modified
- `notebooks/11_kalshi_comparison.ipynb` - 2025 data ingestion, model predictions, Kalshi join, Brier score benchmark comparison, calibration curves
- `notebooks/12_edge_analysis.ipynb` - Edge identification with configurable threshold, fee-adjusted P&L, edge distribution histograms, cumulative P&L chart

## Decisions Made
None - followed plan as specified. Notebooks use the established thin-wrapper pattern from notebooks 09 and 10.

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
This is the final plan of the final phase (Phase 4, Plan 02). All v1 requirements are complete:
- 22/22 v1 requirements satisfied (DATA-01 through MARKET-04)
- 4 phases, 10 plans executed
- Full pipeline: data ingestion -> feature engineering -> model training/backtesting -> Kalshi market comparison and edge analysis
- v2 requirements (LIVE-01 through ADVF-06) documented in REQUIREMENTS.md for future iteration

## Self-Check: PASSED

- FOUND: notebooks/11_kalshi_comparison.ipynb
- FOUND: notebooks/12_edge_analysis.ipynb
- FOUND: commit 425ac90 (Task 1)
- FOUND: commit 1a832c7 (Task 2)

---
*Phase: 04-kalshi-market-comparison-and-edge-analysis*
*Completed: 2026-03-29*
