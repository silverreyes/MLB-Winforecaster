# Milestones

## v2.1 Dashboard UX / Contextual Clarity (Shipped: 2026-03-31)

**Phases completed:** 3 phases (10–12) · 3 plans
**Timeline:** 2026-03-30 (single day)
**Git commits:** 22 · **Files changed:** 31 · **Lines:** +3,012 / -84
**Requirements:** 15/15 shipped

**Key accomplishments:**
1. Backend `game_time` field (UTC ISO or null) added to PredictionResponse; `_build_schedule_lookup()` joins MLB Stats API `game_datetime` to predictions; ET-formatted time ("7:05 PM ET" / "Time TBD") displayed on every game card with responsive CSS
2. `useEasternClock` hook with drift-corrected `setInterval` (setTimeout aligns to wall-clock second boundary); header clockRow shows today's date, live ET clock updating every second, and next pipeline run time (10 AM / 1 PM / 5 PM ET, "tomorrow" after 5 PM)
3. Collapsible `<details>`/`<summary>` "About the Models" section (zero JS) explaining LR/RF/XGBoost in plain English, calibration, PRE/POST-LINEUP distinction, and Kalshi mechanics with 7% fee disclosure and explicit no-trading-advice disclaimer
4. Reusable `Tooltip` component (CSS-only hover/focus-visible, keyboard accessible via tabIndex + aria-label) wired to EdgeBadge (?) icons explaining Buy Yes/No contract mechanics

**Archive:**
- `.planning/milestones/v2.1-ROADMAP.md`
- `.planning/milestones/v2.1-REQUIREMENTS.md`
- `.planning/milestones/v2.1-MILESTONE-AUDIT.md`

---

## v2.0 Live Platform (Shipped: 2026-03-30)

**Phases completed:** 5 phases (5–9) · 16 plans
**Timeline:** 2026-03-28 → 2026-03-30 (3 days)
**Git commits:** ~180 · **Python LOC:** ~5,322 · **TypeScript/CSS LOC:** ~1,087
**Requirements:** 45/45 shipped

**Key accomplishments:**
1. Fixed 100% NaN xwOBA bug (wrong Statcast column name + merged name join) and built 5-tier SP name resolution chain with Chadwick Register MLB→FanGraphs ID bridge — eliminating ~17% NaN rate from name mismatches between MLB Stats API and FanGraphs
2. 8 new SP differential features computed with full temporal safety (cumsum+shift(1)): season-to-date ERA/K-BB%/WHIP, 30-day rolling FIP, pitch count last start, days rest, xFIP, plus cold-start cascade to prev-season then league-average constants
3. Retrained 6 model artifacts (LR/RF/XGB × TEAM_ONLY/SP_ENHANCED); SP_ENHANCED beats TEAM_ONLY by 0.004–0.005 Brier; best aggregate: LR sp_enhanced (0.2331); v2 RF SP_ENHANCED beats Kalshi market (0.2371 vs 0.2434 on 2,128-game 2025 out-of-sample set)
4. Three-run daily prediction pipeline (10am/1pm/5pm ET) with psycopg3 Postgres persistence, Kalshi live edge signal at insert time, APScheduler BlockingScheduler, and OOM-resistant retry logic with stale-run cleanup
5. React 19 + Vite + FastAPI dashboard at mlbforecaster.silverreyes.net — dark/amber aesthetic, pre/post-lineup predictions side-by-side, 60-second visibilityState polling, explicit offline error state
6. Production infrastructure: multi-stage Docker build, Docker Compose with explicit memory limits (api 512M, worker 1536M, db 512M), Nginx reverse proxy + Certbot SSL, daily pg_dump backups with 7-day retention — deployed on Hostinger KVM2 on Opening Day 2026

**Archive:**
- `.planning/milestones/v2.0-ROADMAP.md`
- `.planning/milestones/v2.0-REQUIREMENTS.md`

---

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
