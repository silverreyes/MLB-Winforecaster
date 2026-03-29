# Phase 4: Kalshi Market Comparison and Edge Analysis - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Benchmark 2025 season model predictions against Kalshi implied probabilities for the games where Kalshi market data is available (2025-04-16 onward), compute fee-adjusted edge analysis, and present results in two standalone notebooks. This is the secondary evaluation track — reported separately from the primary 2015–2024 backtest and never conflated with it. Phase 4 also generates the 2025 model predictions (which require new 2025 data ingestion) since feature_matrix.parquet covers 2015–2024 only.

</domain>

<decisions>
## Implementation Decisions

### Kalshi price source
- **Best-effort**: attempt to fetch pre-game opening price via Kalshi candlestick API first (`GET /series/{ticker}/candlesticks` or equivalent endpoint), unauthenticated (consistent with existing public-endpoint-first pattern)
- **Pre-game cutoff**: opening price on game day — OHLC 'open' field (first available price on game morning before any in-day movement)
- **Fallback**: if candlestick endpoint returns 401/403 or is unavailable, fall back to closing price (`last_price_dollars`) — but with a **strong caveat, not an approximation note**: *"closing price benchmark is invalid for edge analysis; Brier score comparison only"*. If fallback is active, the edge analysis notebook must display this caveat prominently and suppress any "edge-based" profit/loss conclusions
- **Cache update**: add `kalshi_open_price` column to existing `kalshi_game_winners.parquet` (alongside `kalshi_yes_price` which remains as closing price). Clear column naming distinguishes closing vs opening. Phase 4 uses `kalshi_open_price` for all benchmark comparisons where available

### 2025 data pipeline
- Phase 4 ingests 2025 season data (team batting, SP stats, per-game team batting logs, schedule, Statcast) within Phase 4 — no separate phase or plan for this
- Builds 2025 features using existing `FeatureBuilder` (same `src/features/feature_builder.py`, same cache infrastructure)
- Runs a new model fold: **train 2015–2023, calibrate 2024, predict 2025** — all three models (LR, RF, XGBoost)
- Feature set: **core feature set only** (excludes `xwoba_diff` which is 100% NaN per Phase 3 finding)
- Predictions saved to `data/results/predictions_2025.parquet` — separate from `backtest_results.parquet` (which covers 2019–2024). The two files must never be merged into a single combined evaluation

### Edge threshold and fee model
- Edge identification uses a **configurable threshold parameter** (not a hardcoded constant), defaulting to `edge_threshold=0.05` (5 percentage points: `|model_prob - kalshi_open_price| > edge_threshold`)
- User can re-run with different thresholds (e.g., 0.03 or 0.10) in the notebook without code changes
- Kalshi fee: **`KALSHI_FEE_RATE = 0.07`** — named module-level constant (7% of profits on winning trades). Easy to update when actual 2025 MLB-specific fee is verified. Not buried inline in formulas
- Fee application: if you buy YES at price `p` and win, contract pays $1.00, profit = `1.0 - p`, fee = `KALSHI_FEE_RATE * (1.0 - p)`, net = `(1.0 - p) * (1 - KALSHI_FEE_RATE)`. If you buy YES and lose, cost = `p` with no fee (fee only on profits)
- Position sizing: **flat $1 per contract** for all simulated positions. Reports net P&L as "if you bet $1 on each flagged edge game" — no Kelly sizing

### Notebook structure
- **Two notebooks** (consistent with Phase 3's 2-notebook pattern):
  - `11_kalshi_comparison.ipynb` — 2025 data ingestion + predictions + Kalshi join + Brier benchmark comparison (model vs market)
  - `12_edge_analysis.ipynb` — edge identification (above threshold) + fee-adjusted profitability analysis
- Prediction logic in `src/models/` (new function, following thin-notebook pattern), called from notebook 11
- Notebook 12 **loads `predictions_2025.parquet` from disk** and runs standalone without re-running notebook 11 (same pattern as notebook 10 loading `backtest_results.parquet`)

### Claude's Discretion
- Which `src/models/` file gets the 2025 fold function (new `predict.py` vs extending `backtest.py`)
- Exact candlestick API endpoint path and response field for opening price (research at implementation time)
- How to display the fallback caveat in the notebook if closing price is used (cell output, markdown cell, or raised warning)
- 2025 data ingestion retry/rate-limit strategy (follow Phase 2 pattern from `src/data/`)
- Exact column layout and index of `predictions_2025.parquet`

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §MARKET-01 through MARKET-04 — all Kalshi market comparison acceptance criteria for this phase

### Roadmap
- `.planning/ROADMAP.md` §Phase 4 — goal, success criteria, two-track evaluation note (primary 2015–2024 vs secondary 2025 Kalshi comparison must be reported separately)

### Prior phase context (patterns to follow)
- `.planning/phases/01-data-ingestion-and-raw-cache/01-CONTEXT.md` — cache infrastructure, Kalshi loader, team_mappings, notebook structure
- `.planning/phases/02-feature-engineering-and-feature-store/02-CONTEXT.md` — FeatureBuilder interface, NaN policy, rolling feature design, rate limiting pattern
- `.planning/phases/03-model-training-and-backtesting/03-CONTEXT.md` — model fold structure, calibration mechanics, feature sets, backtest_results schema

### No external specs
No ADRs or design docs. Requirements fully captured in REQUIREMENTS.md and decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/data/kalshi.py` — `fetch_kalshi_markets()` fetches and caches `kalshi_game_winners.parquet`. Phase 4 extends this to add `kalshi_open_price` column via candlestick API. `PHASE 4 BLOCKER` comment at line 201 marks where the price issue lives.
- `src/data/cache.py` — `is_cached()`, `save_to_cache()`, `read_cached()`: 2025 data ingestion and predictions_2025.parquet use this same cache infrastructure
- `src/data/team_mappings.py` — `normalize_team()`: reused when joining Kalshi tickers to model predictions
- `src/models/backtest.py` + `train.py` + `calibrate.py` — existing fold runner and model factories; 2025 fold function reuses these
- `src/models/evaluate.py` — `compute_brier_scores()`, `plot_calibration_curves()`: reused directly for Kalshi comparison track

### Established Patterns
- `data/results/backtest_results.parquet` schema: `game_date, home_team, away_team, season, home_win, model_name, feature_set, fold_test_year, prob_calibrated, prob_raw` — `predictions_2025.parquet` should follow same schema
- Join key for all Kalshi data: `(date, home_team, away_team)` — `backtest_results` uses `game_date`, Kalshi uses `date`; need type/format alignment at join time
- `kalshi_game_winners.parquet`: 2,237 rows, columns: `date, home_team, away_team, kalshi_yes_price, kalshi_no_price, result, market_ticker`. Phase 4 adds `kalshi_open_price` column to this file
- Kalshi API base URL: `https://api.elections.kalshi.com/trade-api/v2` — confirmed working unauthenticated for settled markets
- 2025 season is complete (as of 2026-03-29) — all 2025 pybaseball/MLB Stats API data is final, no partial-season edge cases

### Integration Points
- `predictions_2025.parquet` is the output of notebook 11 and the input of notebook 12
- Kalshi join: `predictions_2025.parquet` joined to `kalshi_game_winners.parquet` on `(game_date==date, home_team, away_team)`
- Feature matrix 2025 extension reads from `data/raw/` (existing cache dirs) and outputs to `data/features/` — or keep 2025 features in-memory within the fold (avoid polluting the Phase 2 feature matrix)

</code_context>

<specifics>
## Specific Ideas

- Strong fallback caveat wording (user's exact language): *"closing price benchmark is invalid for edge analysis; Brier score comparison only"* — use this exact language in the notebook if falling back to closing price
- `KALSHI_FEE_RATE = 0.07` as a named constant (not inline) so the assumption is explicit and trivial to update when the actual MLB-specific fee rate is verified
- Notebook 12 should mirror notebook 10's standalone-load pattern: open with `pd.read_parquet('data/results/predictions_2025.parquet')` and run without triggering any training

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 04-kalshi-market-comparison-and-edge-analysis*
*Context gathered: 2026-03-29*
