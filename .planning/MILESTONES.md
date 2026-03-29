# Milestones

## v1.0 MVP (Shipped: 2026-03-29)

**Phases completed:** 4 phases · 10 plans
**Timeline:** 2026-03-28 → 2026-03-29 (2 days)
**Git commits:** 81 · **Files:** 97 · **Python LOC:** ~40,800 · **Notebooks:** 12
**Tests:** 120 passing

**Key accomplishments:**
1. Parquet cache infrastructure with team normalization for all 30 MLB teams across 5 data sources (pybaseball/FanGraphs, MLB Stats API, Statcast, Kalshi)
2. Kalshi KXMLBGAME settled market loader — ticker-based team extraction, home-YES deduplication, 2,237 unique games (Apr 2025–present); candlestick API for pre-game opening prices
3. FeatureBuilder with 14 differential features (SP stats, team offense, rolling OPS, bullpen ERA, park factors, Log5, Pythagorean, advanced xwOBA/SIERA) with verified shift(1) temporal safety and leakage tests
4. Walk-forward backtest (5 folds, 2015–2024, 2020 excluded as test year) with per-fold isotonic calibration; LR/RF/XGBoost evaluated via Brier score and calibration curves
5. predict_2025() single-fold runner + fetch_kalshi_open_prices() via candlestick API + compute_edge_signals() + compute_fee_adjusted_pnl() — full Phase 4 library with 120 tests
6. 12-notebook pipeline: data ingestion (01–05) → feature engineering (06–08) → model training/comparison (09–10) → Kalshi comparison and edge analysis (11–12)

**Archive:**
- `.planning/milestones/v1.0-ROADMAP.md`
- `.planning/milestones/v1.0-REQUIREMENTS.md`

---
