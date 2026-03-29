---
status: complete
phase: 04-kalshi-market-comparison-and-edge-analysis
source: [04-01-SUMMARY.md, 04-02-SUMMARY.md]
started: 2026-03-29T16:43:57Z
updated: 2026-03-29T16:55:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Full Test Suite
expected: Running `pytest tests/` from the project root completes with all tests green. The suite should report 120 passed (or more), 0 failures, 0 errors.
result: pass

### 2. predict_2025() Output Schema
expected: Importing and calling `predict_2025()` (or inspecting predictions_2025.parquet) shows a DataFrame with columns matching the backtest schema — with rows for 2025 games only.
result: pass

### 3. Edge Signal Identification
expected: Calling `compute_edge_signals(df, threshold=0.05)` on a joined predictions+Kalshi DataFrame returns rows with has_edge (bool), position (BUY_YES or BUY_NO), and abs_edge (float) columns. Games where |model_prob - kalshi_price| < 0.05 have has_edge=False.
result: pass

### 4. Fee-Adjusted P&L Formula
expected: `compute_fee_adjusted_pnl()` applies the 7% fee on winning trades only (not losses). A winning $100 trade nets $93 (fee deducted from profit). A losing trade loses the full stake with no fee. Net P&L column is present in output.
result: pass

### 5. Notebook 11 — Kalshi Comparison Output
expected: Running 11_kalshi_comparison.ipynb top-to-bottom shows: (1) a Brier score comparison table with LR, RF, XGBoost, and Kalshi market rows, (2) calibration curves for all four on the same axes, (3) "partial benchmark" language clarifying this is 2025-only, and (4) predictions_2025.parquet saved to data/results/.
result: pass

### 6. predictions_2025.parquet File Isolation
expected: data/results/predictions_2025.parquet exists on disk AND is a separate file from data/results/backtest_results.parquet. The two files are never merged — predictions_2025 contains 2025 season only, backtest_results contains 2015-2024.
result: pass

### 7. Notebook 12 — Standalone Edge Analysis
expected: Running 12_edge_analysis.ipynb top-to-bottom loads predictions from parquet (no model training calls), renders edge distribution histograms for all 3 models, renders a cumulative P&L chart over time, and shows a summary table with edge counts and fee-adjusted profitability metrics. If fallback closing prices are present, a caveat warning is displayed.
result: pass

## Summary

total: 7
passed: 7
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
