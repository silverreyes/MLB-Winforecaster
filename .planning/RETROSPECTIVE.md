# Retrospective

Living document. One section per milestone, updated on completion.

---

## Milestone: v1.0 MVP

**Shipped:** 2026-03-29
**Phases:** 4 | **Plans:** 10 | **Timeline:** 2 days | **Commits:** 81

### What Was Built

- Parquet cache infrastructure + 4 pybaseball/statsapi loaders (team batting, SP stats, Statcast, schedule) + Kalshi KXMLBGAME market loader with ticker-based parsing
- FeatureBuilder: 14 differential features (SP, offense, rolling OPS, bullpen, park, Log5, Pythagorean, SIERA, xwOBA) with verified shift(1) temporal safety
- Walk-forward backtest (5 folds, 2015–2024) with per-fold isotonic calibration; LR/RF/XGBoost evaluated on Brier score + calibration curves
- Phase 4 library: predict_2025(), fetch_kalshi_open_prices() via candlestick API, compute_edge_signals(), compute_fee_adjusted_pnl()
- 12-notebook pipeline: ingestion (01–05) → features (06–08) → models (09–10) → Kalshi comparison + edge analysis (11–12)
- 120 passing tests across all subsystems

### What Worked

- **Phase-plan-notebook pattern**: Each phase split into a library plan (pure Python, testable) and a notebook plan (thin wrappers). Made verification clean — test library, then run notebooks.
- **TDD for pure functions**: Sabermetric formulas (Log5, Pythagorean, park factors) written test-first. Zero defects found in those modules later.
- **Wave 0 stubs**: Writing importorskip stubs before implementation kept the test suite runnable at every stage and made the acceptance criteria explicit.
- **Cache-before-compute pattern**: Every expensive operation (pybaseball, statsapi, Kalshi API, backtest) checks cache first. Development never re-hit external APIs after initial pull.
- **Ticker-based Kalshi parsing**: Ignoring title text (identical for both sides of a game) and parsing exclusively from the ticker suffix was the right call — robust to all observed edge cases.
- **Atomic commits per task**: Clean history made git log readable; each commit is a meaningful unit.
- **human-verify checkpoints**: Pausing at notebooks (Phase 2 Plan 03, Phase 3 Plan 02, Phase 4 Plan 02) before marking complete caught real issues early.

### What Was Inefficient

- **BRef 403 discovery was late**: The pybaseball BRef scraper failing with Cloudflare 403 was only discovered when running notebook 06 in Phase 2 Plan 03 — required an unplanned mid-plan pivot to MLB Stats API. Could have been caught earlier with a pre-phase API smoke test.
- **xwOBA exclusion was late**: The 100% NaN on xwoba_diff wasn't confirmed until Phase 3 Plan 01 execution. Root cause (statcast column naming) wasn't fully diagnosed until after Phase 3. A pre-flight check on statcast column names in Phase 2 would have caught this.
- **Kalshi historical endpoint dead end**: ~19 minutes of observation time before deciding to disable the historical endpoint and use the live endpoint with series_ticker filter. Worth documenting the pattern earlier.
- **Park factors were estimated**: FanGraphs Guts page was inaccessible during Phase 2; used RESEARCH.md approximations. Acceptable for v1 but should be live-fetched in v2.

### Patterns Established

- `cache-check-then-fetch`: `is_cached() → read_cached()` or `fetch() → save_to_cache()` — universal across all loaders
- `import X as pybaseball_X`: Module-level aliasing for clean mock patching in tests
- `shift(1) + groupby(['team', 'season'])`: Non-negotiable temporal safety pattern for all rolling features
- `dict-lookup-then-map`: Build `{(season, name): stats}` once, then `df.apply(lambda)` for O(1) feature joins
- `model-factory-per-fold`: Fresh model instantiated each fold via callable — no state leakage between folds
- `two-track evaluation language`: 2015–2024 primary backtest always separate from 2025 Kalshi partial benchmark
- `standalone notebook pattern`: Notebooks that load from Parquet never import training code — decoupled
- `thin-wrapper notebooks`: Notebooks call library functions, don't contain business logic

### Key Lessons

1. **Identify external API reliability risks upfront**: Check that all data sources respond with expected schemas before Phase 1 is marked complete. BRef 403 and Kalshi endpoint behavior both required mid-execution pivots.
2. **xwOBA-type column mapping bugs hide as NaN**: 100% NaN on a feature is always a code bug, not a data issue. Add an assertion in the feature pipeline that no engineered feature is >50% NaN.
3. **Kalshi API docs underspecify the live vs historical distinction**: The series_ticker filter only works on the live endpoint. Historical endpoint paginates everything. Document this in CONTEXT.md for v2 work.
4. **Two-track evaluation framing pays dividends**: Establishing the "partial benchmark" language early meant no confusion at analysis time. The Brier score comparison is valid but clearly labeled.
5. **120 tests in 10 plans is achievable**: The TDD/stub pattern kept test count high without slowing execution — most tests were written concurrent with implementation, not after.

### Cost Observations

- **Model mix:** opus for execution, sonnet for verification/checking — appropriate for this complexity
- **Sessions:** ~4 sessions across 2 days
- **Notable:** Phase 2 Plan 03 took 34min (vs avg 7min) due to BRef 403 diagnosis + human checkpoint. All other plans ran 3–10min. Checkpoints added calendar time but no wasted agent execution.

---

## Cross-Milestone Trends

| Milestone | Days | Commits | Plans | Tests | Key Risk |
|-----------|------|---------|-------|-------|----------|
| v1.0 MVP | 2 | 81 | 10 | 120 | External API reliability (BRef, Kalshi) |
