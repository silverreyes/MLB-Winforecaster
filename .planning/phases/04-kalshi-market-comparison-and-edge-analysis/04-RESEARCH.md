# Phase 4: Kalshi Market Comparison and Edge Analysis - Research

**Researched:** 2026-03-29
**Domain:** Kalshi API candlestick data, 2025 MLB prediction pipeline, Brier score benchmarking, fee-adjusted edge analysis
**Confidence:** HIGH

## Summary

Phase 4 extends the existing model pipeline to 2025 data and benchmarks model predictions against Kalshi market-implied probabilities. The core technical challenge -- fetching pre-game opening prices from Kalshi -- has been validated through live API testing. The batch candlestick endpoint (`GET /markets/candlesticks`) returns daily OHLC data including `price.open_dollars` (first trade of the day) for 2,237 settled KXMLBGAME markets. Coverage is 100% from May 2025 onward; the first week (April 16-18) has ~65% coverage due to early-season low-liquidity markets with zero trading volume.

The 2025 data pipeline reuses all existing infrastructure: `FeatureBuilder` (seasons parameter extended to include 2025), `backtest.py` patterns (train/calibrate/predict fold structure), and `evaluate.py` functions (`compute_brier_scores`, `plot_calibration_curves`). The 2025 fold is: train 2015-2023, calibrate 2024, predict 2025 -- core feature set only (xwoba_diff excluded per Phase 3 finding). All 2025 raw data sources except team batting, SP stats, and Statcast are already cached.

**Primary recommendation:** Use the batch candlestick endpoint grouped by date (187 API calls at ~150ms each = ~28 seconds total) to fetch daily `price.open_dollars` for all markets. Fall back to `kalshi_yes_price` (closing/settlement price) for the ~35 games with no candlestick data, with prominent caveat text per user decision. Handle 9 doubleheader collisions by joining on `(date, home_team, away_team, game_num)` where possible or by dropping duplicate matches.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Kalshi price source**: Best-effort fetch via batch candlestick API; opening price = `price.open_dollars` from daily candle. Fallback to closing price (`kalshi_yes_price`) with caveat: *"closing price benchmark is invalid for edge analysis; Brier score comparison only"*. If fallback active, suppress edge-based P&L conclusions.
- **Cache update**: Add `kalshi_open_price` column to `kalshi_game_winners.parquet` alongside existing `kalshi_yes_price`.
- **2025 data pipeline**: Ingest within Phase 4 (no separate phase). Build 2025 features using existing `FeatureBuilder`. Run fold: train 2015-2023, calibrate 2024, predict 2025. Core feature set only (excludes xwoba_diff). Save to `data/results/predictions_2025.parquet` -- never merged with `backtest_results.parquet`.
- **Edge threshold**: Configurable `edge_threshold=0.05` (5pp default). User can change in notebook without code changes.
- **Fee model**: `KALSHI_FEE_RATE = 0.07` as named module-level constant. Fee = `KALSHI_FEE_RATE * (1.0 - p)` on winning YES trades only. Flat $1/contract sizing.
- **Notebook structure**: Two notebooks -- `11_kalshi_comparison.ipynb` (ingestion + predictions + Kalshi join + Brier benchmark) and `12_edge_analysis.ipynb` (edge identification + fee-adjusted profitability). Notebook 12 loads `predictions_2025.parquet` standalone.
- **Prediction logic**: In `src/models/` (new function), called from notebook 11.

### Claude's Discretion
- Which `src/models/` file gets the 2025 fold function (new `predict.py` vs extending `backtest.py`)
- Exact candlestick API endpoint path and response field for opening price
- How to display the fallback caveat in the notebook
- 2025 data ingestion retry/rate-limit strategy
- Exact column layout and index of `predictions_2025.parquet`

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MARKET-01 | Kalshi resolved prices joined to feature matrix for 2025 season games where data available | Batch candlestick endpoint validated; `price.open_dollars` provides pre-game price. Join on `(date, home_team, away_team)` with date type alignment (Kalshi=str, predictions=datetime64). 9 doubleheader collisions need handling. |
| MARKET-02 | Each model's Brier score benchmarked against Kalshi implied probability Brier score on same 2025 games | `sklearn.metrics.brier_score_loss` works directly with Kalshi prices as probability inputs. Existing `compute_brier_scores()` in `evaluate.py` reusable. Partial benchmark clearly labeled. |
| MARKET-03 | Edge analysis identifies games where model probability diverges from Kalshi opening price by meaningful margin | Edge = `abs(model_prob - kalshi_open_price) > edge_threshold`. Configurable threshold (default 0.05). Only valid when `kalshi_open_price` is non-null (not fallback). |
| MARKET-04 | Profitability analysis fee-adjusted before any edge reported | Fee formula: `KALSHI_FEE_RATE * (1.0 - p)` on wins only. Net profit per winning YES trade: `(1.0 - p) * (1 - KALSHI_FEE_RATE)`. Net loss per losing YES trade: `-p`. Flat $1/contract. |
</phase_requirements>

## Standard Stack

### Core (all already installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pandas | 2.2.x (pinned) | DataFrames for all data manipulation | Project-wide pin due to pybaseball incompatibility with 3.0 |
| scikit-learn | >=1.3,<2.0 | `brier_score_loss`, `calibration_curve`, `IsotonicRegression` | Already used in Phase 3 evaluate.py and calibrate.py |
| xgboost | >=2.0,<3.0 | XGBoost model training for 2025 fold | Already used in Phase 3 train.py |
| matplotlib | >=3.7,<4.0 | Plots for calibration curves, edge visualizations | Already used in Phase 3 notebooks |
| seaborn | >=0.13,<1.0 | Enhanced plot styling | Already used in Phase 3 notebooks |
| requests | 2.31.0 | Kalshi API HTTP calls | Already used in kalshi.py |
| pybaseball | 2.2.7 | 2025 team batting, SP stats, Statcast data | Already used in Phase 1/2 data loaders |
| statsapi (MLB-StatsAPI) | 1.9.0 | 2025 schedule (already cached) | Already used in mlb_schedule.py |

### No new dependencies
Phase 4 requires zero new packages. All functionality is achievable with the existing stack.

## Architecture Patterns

### Recommended Project Structure (new files only)
```
src/
  models/
    predict.py           # NEW: 2025 fold runner (train/calibrate/predict single fold)
  data/
    kalshi.py            # MODIFIED: add fetch_kalshi_open_prices() function
notebooks/
  11_kalshi_comparison.ipynb   # NEW: 2025 ingestion + predictions + Kalshi benchmark
  12_edge_analysis.ipynb       # NEW: edge identification + fee-adjusted profitability
data/
  raw/kalshi/
    kalshi_game_winners.parquet  # MODIFIED: add kalshi_open_price column
  results/
    predictions_2025.parquet     # NEW: 2025 model predictions
```

### Pattern 1: 2025 Fold Runner (new `src/models/predict.py`)
**What:** A function that runs a single train/calibrate/predict fold for 2025, reusing existing model factories and calibration.
**When to use:** Called from notebook 11 to generate 2025 predictions.
**Rationale for new file:** The existing `backtest.py` has `FOLD_MAP` and `run_backtest()` tightly coupled to the 5-fold 2015-2024 structure. A new `predict.py` avoids modifying working backtest code and keeps the 2025 prediction pipeline clearly separate (per CONTEXT.md: "never merged").

```python
# src/models/predict.py
"""Single-fold prediction for 2025 season (Phase 4 Kalshi comparison track).

Trains on 2015-2023, calibrates on 2024, predicts 2025 -- core feature set only.
Produces predictions_2025.parquet with same schema as backtest_results.parquet.
"""
from src.models.train import make_lr_pipeline, make_rf_pipeline, make_xgb_model
from src.models.calibrate import calibrate_model
from src.models.feature_sets import CORE_FEATURE_COLS, TARGET_COL

TRAIN_SEASONS = list(range(2015, 2024))  # 2015-2023
CAL_SEASON = 2024
TEST_SEASON = 2025

def predict_2025(df):
    """Run 3 models on 2025 fold, return predictions DataFrame."""
    # Filter and clean (same pattern as backtest.py generate_folds)
    df_clean = df[df["rolling_ops_diff"].notna()].copy()
    train_df = df_clean[df_clean["season"].isin(TRAIN_SEASONS)]
    cal_df = df_clean[df_clean["season"] == CAL_SEASON]
    test_df = df_clean[df_clean["season"] == TEST_SEASON]

    results = []
    models = [
        ("lr", make_lr_pipeline, False),
        ("rf", make_rf_pipeline, False),
        ("xgb", make_xgb_model, True),
    ]
    for model_name, factory, is_xgb in models:
        model = factory()
        X_train = train_df[CORE_FEATURE_COLS]
        y_train = train_df[TARGET_COL]
        # ... train, calibrate, predict (same as backtest.py)
        # ... append per-game results with same schema
    return pd.DataFrame(results)
```

### Pattern 2: Kalshi Open Price Fetcher (extend `src/data/kalshi.py`)
**What:** New function `fetch_kalshi_open_prices()` that fetches daily candlestick `price.open_dollars` for all cached markets.
**When to use:** Called from notebook 11 after `fetch_kalshi_markets()`.
**Key implementation details:**
- Uses batch endpoint `GET /markets/candlesticks` (no auth required)
- Groups tickers by date, one API call per date (187 calls)
- Each call: `start_ts` = game_date 00:00 UTC, `end_ts` = game_date + 30h UTC (to capture midnight-ET candle boundary at 04:00 UTC)
- `period_interval=1440` (daily)
- Max 20 tickers per date (well under 100 limit and 10,000 candle limit)
- Adds `kalshi_open_price` column to cached parquet

```python
def fetch_kalshi_open_prices(df: pd.DataFrame) -> pd.DataFrame:
    """Fetch pre-game opening prices via Kalshi candlestick API.

    Args:
        df: DataFrame from fetch_kalshi_markets() with market_ticker and date columns.
    Returns:
        Same DataFrame with kalshi_open_price column added (NaN where unavailable).
    """
    # Group by date, batch-fetch daily candles per date
    # Map ticker -> price.open_dollars
    # Merge back, NaN for markets with no candlestick data
```

### Pattern 3: Thin Notebook Wrapper (established pattern)
**What:** Notebooks call `src/` functions, display results, and save artifacts.
**Example (notebook 11 structure):**
1. Cell 1: sys.path setup, imports
2. Cell 2: Build 2025 feature matrix (`FeatureBuilder(seasons=list(range(2015, 2026)))`)
3. Cell 3: Run `predict_2025(feature_matrix_2025)` -- save to `predictions_2025.parquet`
4. Cell 4: Load Kalshi data, fetch open prices, join to predictions
5. Cell 5: Compute Brier scores (model vs Kalshi) using `compute_brier_scores()` equivalent
6. Cell 6: Display comparison table and calibration curves

**Example (notebook 12 structure):**
1. Cell 1: sys.path setup, imports
2. Cell 2: `pd.read_parquet('data/results/predictions_2025.parquet')` -- standalone load
3. Cell 3: Join Kalshi open prices, apply edge threshold
4. Cell 4: Fee-adjusted profitability analysis
5. Cell 5: Summary tables and visualizations

### Anti-Patterns to Avoid
- **Merging 2025 predictions into backtest_results.parquet:** The two evaluation tracks (2015-2024 backtest vs 2025 Kalshi comparison) must remain separate files and separate analyses.
- **Using closing price for edge analysis without caveat:** The `kalshi_yes_price` (settlement price) reflects the game outcome and is invalid for edge analysis. Only `kalshi_open_price` is valid.
- **Hardcoding edge threshold or fee rate inline:** Both must be named constants/parameters for easy modification.
- **Re-running training in notebook 12:** Notebook 12 loads predictions from disk, never imports training code.
- **Using the live candlestick endpoint for settled 2025 markets:** Must use the batch endpoint `GET /markets/candlesticks` with wide date ranges OR the historical endpoint `GET /historical/markets/{ticker}/candlesticks`. The live per-series endpoint returns empty for settled historical markets.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Brier score computation | Custom MSE-like formula | `sklearn.metrics.brier_score_loss` | Handles edge cases, well-tested, already used in evaluate.py |
| Calibration curves | Custom binning logic | `sklearn.calibration.calibration_curve` | Already used in evaluate.py `get_calibration_data()` |
| Model training pipeline | New training code | Existing `train.py` factories + `calibrate.py` | Exact same model configs as Phase 3 backtest |
| Feature construction | Manual feature computation | Existing `FeatureBuilder` class | All rolling/temporal safety already implemented |
| Team name normalization | Manual string mapping | Existing `normalize_team()` | Already handles all Kalshi ticker codes (KAN, FLA, ATH, etc.) |
| Kalshi API pagination | Custom page loop | Existing `_paginate_endpoint()` in kalshi.py | Rate limiting and cursor handling already tested |

**Key insight:** Phase 4's novelty is in the comparison and edge analysis, not in data pipeline or model training. Reuse everything from Phases 1-3.

## Common Pitfalls

### Pitfall 1: Date Type Mismatch at Join Time
**What goes wrong:** `predictions_2025.parquet` will have `game_date` as `datetime64[ns]` (from FeatureBuilder schedule loading), but `kalshi_game_winners.parquet` has `date` as `object` (string `"YYYY-MM-DD"`). A naive merge produces zero matches.
**Why it happens:** Different data loaders produce different date types.
**How to avoid:** Convert Kalshi `date` to `datetime64` before join, or convert predictions `game_date` to string. Explicitly name the join columns: `predictions.merge(kalshi, left_on='game_date', right_on='date')`.
**Warning signs:** Zero rows after merge; all `kalshi_open_price` values are NaN.

### Pitfall 2: Doubleheader Many-to-Many Join
**What goes wrong:** 9 doubleheaders in 2025 create duplicate `(date, home_team, away_team)` keys in both predictions and Kalshi data. A merge produces 2x2=4 rows per doubleheader instead of 2 correct 1:1 matches.
**Why it happens:** Neither schedule `game_id` nor Kalshi `market_ticker` is present in the other dataset as a direct join key. The Kalshi ticker encodes game number as a suffix (e.g., `CWSBOS2` = game 2) while the schedule uses `game_num`.
**How to avoid:** Parse the doubleheader suffix from the Kalshi ticker (presence of trailing digit in the teams portion = game 2; absence = game 1). Add a `game_num` column to Kalshi data. Join on `(date, home_team, away_team, game_num)`. Alternatively, for simplicity: drop doubleheader games from the comparison (only 9 affected, <0.5% of data).
**Warning signs:** More rows after merge than before; unexpected duplicate game entries.

### Pitfall 3: Candlestick Time Window Boundary
**What goes wrong:** Daily candles end at 04:00 UTC (midnight Eastern), so a date-range query with `end_ts` = midnight UTC of the next day misses the candle. Returns empty `candlesticks` array.
**Why it happens:** Kalshi daily candle boundaries are aligned to US Eastern midnight, not UTC midnight.
**How to avoid:** Set `end_ts` to game_date + 30 hours (06:00 UTC next day), which safely captures the midnight-ET candle boundary.
**Warning signs:** Batch endpoint returns markets but with empty candlestick arrays for all of them.

### Pitfall 4: Batch Endpoint Candle Count Limit
**What goes wrong:** Batch `GET /markets/candlesticks` returns 400 error: "requested candlesticks across all markets: N, max candlesticks: 10000".
**Why it happens:** Wide date range (e.g., full season) multiplies tickers by candle-days. 60 tickers x 200 days = 12,000 candles > 10,000 limit.
**How to avoid:** Group tickers by date and make one batch call per date. Max 20 tickers/date x 1 candle/ticker = 20 candles per call (well under limit).
**Warning signs:** HTTP 400 from batch endpoint with explicit error message about candle count.

### Pitfall 5: Confusing Opening Price Fields
**What goes wrong:** Using `yes_bid.open_dollars` or `yes_ask.open_dollars` instead of `price.open_dollars`. The bid/ask opens are order book state, not trade prices. `yes_ask.open_dollars` is often `1.0000` (market maker's initial wide ask).
**Why it happens:** Multiple OHLC sub-objects in the candlestick response.
**How to avoid:** Always use `price.open_dollars` -- this is the first actual trade price of the candle period. Fall back to `kalshi_yes_price` (closing price) when `price.open_dollars` is null (no trades occurred).
**Warning signs:** Opening prices skewed toward 1.00 or 0.00; unrealistic implied probabilities.

### Pitfall 6: Feature Matrix 2025 Includes xwoba_diff (All NaN)
**What goes wrong:** FeatureBuilder builds all features including xwoba_diff, which is 100% NaN. If accidentally included in the 2025 feature set, it creates a column that XGBoost handles silently but degrades other models.
**Why it happens:** FeatureBuilder._add_advanced_features() has two bugs (documented in STATE.md) that prevent xwoba lookup from populating.
**How to avoid:** The CONTEXT.md locks core feature set only. Use `CORE_FEATURE_COLS` from `feature_sets.py` (13 columns, xwoba_diff excluded). The FeatureBuilder will still create the column but it's simply not selected for model input.
**Warning signs:** Column `xwoba_diff` appears in feature matrix with all NaN values.

### Pitfall 7: Early-Season NaN Rows Not Dropped
**What goes wrong:** First ~2 weeks of each season have NaN `rolling_ops_diff` (10-game rolling window needs warmup). If not filtered, these rows produce NaN predictions.
**Why it happens:** Rolling window features require N games of history before producing valid values.
**How to avoid:** Filter `df[df["rolling_ops_diff"].notna()]` before splitting -- same pattern as `backtest.py:generate_folds()`.
**Warning signs:** NaN values in `prob_calibrated` column; sklearn errors about NaN inputs.

### Pitfall 8: 2025 pybaseball Data Not Yet Cached
**What goes wrong:** `FeatureBuilder` for seasons including 2025 will call `fetch_team_batting(2025)`, `fetch_sp_stats(2025)`, and `fetch_statcast_pitcher()` which hit FanGraphs/pybaseball. These may be slow (rate-limited) or fail if FanGraphs is temporarily down.
**Why it happens:** 2025 team batting, SP stats, and Statcast data are not yet in the cache (confirmed via manifest check).
**How to avoid:** Run the FeatureBuilder ingestion step early in notebook 11 with error handling and retry logic. Log which data sources succeed vs fail. If FanGraphs is down, the cached 2015-2024 data is unaffected -- only 2025 features will fail.
**Warning signs:** HTTP 403/timeout from FanGraphs; missing feature values for 2025 games only.

## Code Examples

### Kalshi Batch Candlestick Fetch (verified pattern)
```python
# Source: Live API testing on 2026-03-29 against production Kalshi API
import requests
from datetime import datetime, timezone, timedelta

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

def fetch_open_prices_for_date(tickers: list[str], game_date: str) -> dict[str, float | None]:
    """Fetch daily open prices for a batch of tickers on a specific date.

    Returns dict of {ticker: open_price_dollars} (None if no candle data).
    """
    dt = datetime.strptime(game_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    start_ts = int(dt.timestamp())
    end_ts = int((dt + timedelta(hours=30)).timestamp())  # Captures midnight-ET boundary

    resp = requests.get(
        f"{BASE_URL}/markets/candlesticks",
        params={
            "market_tickers": ",".join(tickers),
            "start_ts": start_ts,
            "end_ts": end_ts,
            "period_interval": 1440,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    result = {}
    for m in data.get("markets", []):
        ticker = m["market_ticker"]
        candles = m["candlesticks"]
        if candles and candles[0]["price"].get("open_dollars") is not None:
            result[ticker] = float(candles[0]["price"]["open_dollars"])
        else:
            result[ticker] = None  # No trades -- fallback to closing price
    return result
```

### Brier Score: Model vs Kalshi (reuses existing evaluate.py)
```python
# Source: Verified with sklearn.metrics.brier_score_loss
from sklearn.metrics import brier_score_loss

# For each model, compute Brier on the same 2025 game subset
kalshi_brier = brier_score_loss(merged["home_win"], merged["kalshi_open_price"])
model_brier = brier_score_loss(merged["home_win"], merged["prob_calibrated"])
```

### Edge Identification with Configurable Threshold
```python
# Per CONTEXT.md locked decision
edge_threshold = 0.05  # Configurable parameter

merged["edge"] = merged["prob_calibrated"] - merged["kalshi_open_price"]
merged["abs_edge"] = merged["edge"].abs()
edge_games = merged[merged["abs_edge"] > edge_threshold].copy()
edge_games["position"] = edge_games["edge"].apply(lambda e: "BUY_YES" if e > 0 else "BUY_NO")
```

### Fee-Adjusted Profitability (per CONTEXT.md formula)
```python
KALSHI_FEE_RATE = 0.07  # Named module-level constant

def compute_fee_adjusted_pnl(row):
    """Compute P&L for a $1 flat bet based on edge signal."""
    p = row["kalshi_open_price"]
    actual_home_win = row["home_win"]
    position = row["position"]  # BUY_YES or BUY_NO

    if position == "BUY_YES":
        if actual_home_win == 1:
            # Won: profit = 1-p, fee on profit, net = (1-p) * (1 - fee_rate)
            return (1.0 - p) * (1 - KALSHI_FEE_RATE)
        else:
            # Lost: cost = p, no fee
            return -p
    else:  # BUY_NO (bet against home)
        if actual_home_win == 0:
            # Won: profit = p, fee on profit
            return p * (1 - KALSHI_FEE_RATE)
        else:
            # Lost: cost = 1-p, no fee
            return -(1.0 - p)
```

### predictions_2025.parquet Schema (matches backtest_results.parquet)
```python
# Per CONTEXT.md: same schema as backtest_results.parquet
# Columns: game_date, home_team, away_team, season, home_win,
#           model_name, feature_set, fold_test_year, prob_calibrated, prob_raw
# Where:
#   fold_test_year = 2025 (always)
#   feature_set = "core" (always -- xwoba_diff excluded)
#   model_name in {"lr", "rf", "xgb"}
#   season = 2025 (always)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Live candlestick endpoint for settled markets | Historical/batch endpoint required | March 6, 2026 (Kalshi data migration) | Live endpoint returns empty for pre-cutoff markets; must use batch `GET /markets/candlesticks` or `GET /historical/markets/{ticker}/candlesticks` |
| `CalibratedClassifierCV(cv='prefit')` | `IsotonicRegression` directly | sklearn 1.8.0 | Already handled in Phase 3 calibrate.py |
| `kalshi_yes_price` as benchmark | `kalshi_open_price` (pre-game) | Phase 4 (this phase) | Closing price reflects outcome (look-ahead bias); opening price is valid pre-game benchmark |

**Deprecated/outdated:**
- Kalshi `GET /historical/markets` endpoint for broad market queries: Disabled in Phase 1 due to unbounded pagination (19+ min). Still disabled; Phase 4 uses per-market and batch endpoints only.
- `use_label_encoder` parameter in XGBClassifier: Removed in xgboost 2.x. Already omitted in train.py.
- `penalty` parameter in LogisticRegression: Deprecated in sklearn 1.8.0. Already omitted in train.py.

## Kalshi API Findings (Live-Tested)

### Verified Endpoints (tested 2026-03-29)
| Endpoint | Auth Required | Works for 2025 KXMLBGAME | Notes |
|----------|---------------|--------------------------|-------|
| `GET /markets/candlesticks` (batch) | No | YES | Up to 50 tickers x 1 daily candle works. 10,000 candle limit applies across all markets. |
| `GET /historical/markets/{ticker}/candlesticks` | No | YES (hourly/minute) | Works for individual markets. Daily interval requires correct end_ts (past 04:00 UTC). |
| `GET /series/{series_ticker}/markets/{ticker}/candlesticks` (live per-series) | No | Empty results | Settled 2025 markets removed from live data post-March 6, 2026 cutoff. |
| `GET /historical/cutoff` | No | N/A | Returns `market_settled_ts: 2025-12-29T00:00:00Z` -- confirms all 2025 games are historical. |

### Response Schema (batch endpoint)
```json
{
  "markets": [
    {
      "market_ticker": "KXMLBGAME-25APR16NYMMIN-MIN",
      "candlesticks": [
        {
          "end_period_ts": 1744862400,
          "price": {
            "open_dollars": "0.5500",    // FIRST TRADE PRICE -- use this
            "close_dollars": "0.9900",
            "high_dollars": "0.9900",
            "low_dollars": "0.3800",
            "mean_dollars": "0.7777"
          },
          "yes_bid": { "open_dollars": "0.4600", ... },  // Order book -- DON'T use
          "yes_ask": { "open_dollars": "1.0000", ... },  // Often 1.00 -- DON'T use
          "volume_fp": "19972.00",
          "open_interest_fp": "15325.00"
        }
      ]
    }
  ]
}
```

### Coverage Analysis
| Period | Games | Open Price Available | Coverage |
|--------|-------|---------------------|----------|
| Apr 16-18 (first week) | ~46 | ~30 | ~65% |
| May-Sep 2025 (rest of season) | ~2,191 | ~2,191 | ~100% |
| **Total** | **2,237** | **~2,221** | **~99.3%** |

Markets missing `price.open_dollars` had zero trading volume (no trades occurred at all). These are exclusively from the first few days of KXMLBGAME availability.

### Fetching Strategy
- Group 2,237 markets by date (187 unique dates)
- One batch `GET /markets/candlesticks` call per date
- Max 20 tickers per date (well under 100-ticker and 10,000-candle limits)
- Rate limit: 150ms between requests (matching existing `RATE_LIMIT_DELAY`)
- Estimated total fetch time: ~28 seconds
- No authentication required

### Historical vs Batch Endpoint Field Name Difference
| Field | Batch endpoint | Historical per-market endpoint |
|-------|----------------|-------------------------------|
| Open price | `price.open_dollars` | `price.open` |
| Volume | `volume_fp` | `volume` |
| Open interest | `open_interest_fp` | `open_interest` |

Use the batch endpoint consistently to avoid field name inconsistency.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.1.1 |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MARKET-01 | Kalshi open prices joined to predictions for 2025 games | unit | `pytest tests/test_kalshi.py -x -q -k "open_price"` | Wave 0 |
| MARKET-01 | Date type alignment in join | unit | `pytest tests/test_kalshi.py -x -q -k "join"` | Wave 0 |
| MARKET-02 | Brier score computed for model vs Kalshi on same game set | unit | `pytest tests/test_models.py -x -q -k "brier_kalshi"` | Wave 0 |
| MARKET-03 | Edge identification with configurable threshold | unit | `pytest tests/test_edge.py -x -q` | Wave 0 |
| MARKET-04 | Fee-adjusted P&L computation | unit | `pytest tests/test_edge.py -x -q -k "fee"` | Wave 0 |
| MARKET-04 | 2025 fold prediction output schema matches backtest_results | unit | `pytest tests/test_models.py -x -q -k "predict_2025"` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x -q`
- **Per wave merge:** `pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_edge.py` -- covers MARKET-03 (edge threshold) and MARKET-04 (fee-adjusted P&L)
- [ ] `tests/test_kalshi.py::test_fetch_open_prices_*` -- covers MARKET-01 (candlestick fetch, join logic)
- [ ] `tests/test_models.py::test_predict_2025_*` -- covers MARKET-02 (2025 fold output schema and Brier comparison)

## Open Questions

1. **Doubleheader handling strategy**
   - What we know: 9 doubleheaders (18 games) in 2025 create duplicate join keys. Kalshi tickers encode game number as trailing digit suffix.
   - What's unclear: Whether the schedule's `game_num` column reliably maps to Kalshi's G2 suffix convention.
   - Recommendation: Parse game_num from Kalshi ticker suffix (presence = game 2, absence = game 1). If ambiguous, drop doubleheader games from comparison (~0.4% of data).

2. **FanGraphs availability for 2025 data**
   - What we know: team_batting_2025, sp_stats_2025, and statcast 2025 are not yet cached. FanGraphs was inaccessible during Phase 2 research.
   - What's unclear: Whether FanGraphs is currently accessible via pybaseball.
   - Recommendation: Add retry/fallback logic for 2025 data ingestion. If FanGraphs is down, the 2025 FeatureBuilder will fail for SP stats and team batting but succeed for schedule and game logs (which use MLB Stats API). Consider logging which features are available vs missing for 2025.

3. **Actual Kalshi fee formula vs simplified model**
   - What we know: Real Kalshi fee is quadratic: `ceil(0.07 * C * P * (1-P))` (from web search). CONTEXT.md locks simplified model: `KALSHI_FEE_RATE * (1-p)` on profits only.
   - What's unclear: The divergence between simplified and actual fee models for extreme prices.
   - Recommendation: Use the locked simplified model. Add a note in the notebook that the actual Kalshi fee formula is more complex and the constant is easy to update.

## Sources

### Primary (HIGH confidence)
- Live Kalshi API testing (2026-03-29) -- batch candlestick endpoint, historical endpoint, cutoff timestamps, response schemas
- Existing codebase: `src/data/kalshi.py`, `src/models/backtest.py`, `src/models/evaluate.py`, `src/models/train.py`, `src/models/calibrate.py`, `src/models/feature_sets.py`, `src/features/feature_builder.py`
- `data/raw/kalshi/kalshi_game_winners.parquet` -- 2,237 rows, confirmed schema and content

### Secondary (MEDIUM confidence)
- [Kalshi API docs: Get Market Candlesticks](https://docs.kalshi.com/api-reference/market/get-market-candlesticks) -- endpoint path and parameters
- [Kalshi API docs: Batch Get Market Candlesticks](https://docs.kalshi.com/api-reference/market/batch-get-market-candlesticks) -- batch limits (100 tickers, 10K candles)
- [Kalshi API docs: Historical Market Candlesticks](https://docs.kalshi.com/api-reference/historical/get-historical-market-candlesticks) -- historical endpoint path
- [Kalshi API docs: Historical Data](https://docs.kalshi.com/getting_started/historical_data) -- March 6 2026 cutoff, 1-year lookback
- [Kalshi API docs: Historical Cutoff Timestamps](https://docs.kalshi.com/api-reference/historical/get-historical-cutoff-timestamps) -- cutoff endpoint

### Tertiary (LOW confidence)
- [Kalshi fee schedule details](https://help.kalshi.com/trading/fees) -- fee formula `0.07 * C * P * (1-P)` sourced from web search, PDF inaccessible (429). User's simplified model used instead per locked decision.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all packages already installed and tested in Phases 1-3
- Architecture: HIGH -- follows established patterns from prior phases; predict.py is a minor extension
- Kalshi API: HIGH -- all endpoints live-tested with actual KXMLBGAME tickers on production API
- Pitfalls: HIGH -- doubleheader, date type, and candle boundary issues discovered through hands-on testing
- Fee model: MEDIUM -- simplified fee model per user decision; actual Kalshi fee formula is more complex

**Research date:** 2026-03-29
**Valid until:** 2026-04-28 (30 days -- stable domain, all 2025 data is final)
