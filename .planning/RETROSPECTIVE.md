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

## Milestone: v2.0 — Live Platform

**Shipped:** 2026-03-30
**Phases:** 5 (5–9) | **Plans:** 16 | **Timeline:** 3 days | **Commits:** ~99 (v2.0 range)

### What Was Built

- 5-tier SP name resolution chain (exact → override → accent-strip → Chadwick ID bridge → FG name lookup) eliminating ~17% NaN rate; fixed 100% NaN xwOBA bug
- 8 new temporally-safe SP differential features (season-to-date ERA/K-BB%/WHIP, 30-day rolling FIP, pitch count, days rest) with cold-start cascade to prev-season then league-average constants
- 6 model artifacts (LR/RF/XGB × TEAM_ONLY/SP_ENHANCED) trained walk-forward 2015–2024; v2 SP_ENHANCED beats Kalshi market on 2025 out-of-sample (Brier 0.2371 vs 0.2434)
- Postgres schema with ENUM types + CHECK constraints; three-run daily pipeline (10am/1pm/5pm ET) via APScheduler; Kalshi live edge signal at insert time; OOM-resistant retry + stale-run cleanup
- FastAPI with lifespan model loading + 5 endpoints; React 19 dashboard with dark/amber aesthetic, side-by-side pre/post-lineup cards, 60s visibilityState polling, explicit offline error state
- Multi-stage Docker build, Docker Compose with memory limits, Nginx + Certbot SSL, daily pg_dump backups — deployed on Hostinger KVM2 on Opening Day 2026

### What Worked

- **Strict dependency ordering (5→6→7→8→9)**: No phase touched infrastructure before the one above it was solid. Phase 9 deploy was smooth because local validation was complete.
- **DB-level invariant for PIPE-07**: Encoding "no post_lineup without confirmed SP" as a CHECK constraint rather than trusting application code meant the invariant couldn't be bypassed by bugs. The constraint caught nothing — but that's the point.
- **Bind-mounted model artifacts**: Not baking artifacts into the Docker image kept the image small and model updates decoupled from container rebuilds.
- **LiveFeatureBuilder delegating to FeatureBuilder internals**: Pragmatic coupling that avoided duplicating all feature logic. Accepted consciously with a comment and tech debt note.
- **Pre-warming Chadwick register in Dockerfile**: Saving the CSV at build time eliminated a cold-start OOM crash that would have silently killed the first pipeline run post-deploy.

### What Was Inefficient

- **Opening Day NaN bug was a production surprise**: The `xwoba_diff`, `sp_recent_era_diff`, and `sp_recent_fip_diff` features are NaN early in the season (no current-year game logs yet) and the lookup uses `r["season"]` directly — missing prior-year data. This wasn't caught in local testing because local tests didn't simulate a day-0-of-season live prediction. Required a same-day hotfix on Opening Day.
- **OOM crash loop required three iterations**: Cold-start pybaseball memory spike → OOM kill → stale "running" rows → retry logic required three separate fixes (pre-warm in Dockerfile, retry loop in run_pipeline, mark_stale_runs_failed at startup). Each was diagnosed only after seeing it in production.
- **Worker memory limit required tuning in production**: Started at 1024M, bumped to 1536M after OOM kills on VPS. A memory profiling step before deploy (not just `docker stats` sanity check) would have predicted the right value.
- **`created_at` not updated on upsert**: Dashboard showed stale "last updated" timestamp because ON CONFLICT UPDATE didn't refresh `created_at`. Simple fix, but only noticed after deploy.

### Patterns Established

- `NaN-impute-at-build-time`: For live predictions, fill any `*_diff` feature that is NaN with 0.0 (neutral prior) after feature extraction — prevents silent model skip when early-season data is missing
- `mark-stale-runs-at-startup`: Always call `mark_stale_runs_failed()` at process startup to clean up rows left open by OOM-killed runs
- `retry-on-cold-start`: Wrap the entire pipeline in a retry loop (MAX_RETRIES=3) for the first post-build run when caches are cold
- `pre-warm-in-dockerfile`: For any data file that causes OOM on first fetch (Chadwick register, large pybaseball CSVs), `RUN python -c "fetch(); save=True"` in the Dockerfile layer
- `enum-plus-check-constraint`: DB-level invariants for state machine transitions (prediction_version × prediction_status) — trust the DB, not application code
- `bind-mount-artifacts-read-only`: Model artifacts outside the image; bind-mounted at runtime — separates model versioning from container versioning

### Key Lessons

1. **Test live features against a simulated day-0 of season**: Opening Day NaN bugs only appear when current-year data (Statcast, game logs) doesn't exist yet. Add a pre-deploy test that builds features for a game with `season=current_year` and no prior game logs, and assert no `*_diff` is NaN.
2. **Memory budget the worker before choosing mem_limit**: `docker stats` on a running container shows steady state. But first-run memory (cold pybaseball fetch + model load + feature build) can spike 2–3x. Profile peak memory, not steady state.
3. **`if not probs: return` is a silent failure**: Any code path that drops work without logging or fallback is a production bug. Post-lineup fallback to team_only on empty probs was the right fix — never silently swallow a result.
4. **Dashboard timestamp freshness requires explicit `created_at = NOW()` on upsert**: ON CONFLICT DO UPDATE doesn't automatically update `created_at` unless you add it to the SET clause. Learned from production.
5. **VIF + SHAP before training saves iteration**: Running both analyses on the candidate feature set (not after training) identified 3 redundant features before any model weights were computed. No retrain needed.

### Cost Observations

- **Sessions:** ~6 sessions across 3 days
- **Notable:** Phase 9 (deploy) took the longest calendar time but the shortest execution time — most time was SSH / VPS operations, not agent work. The 4 post-deploy bugfix commits were all single-issue, single-fix — well-isolated.

---

## Cross-Milestone Trends

| Milestone | Days | Commits | Plans | Tests | Key Risk |
|-----------|------|---------|-------|-------|----------|
| v1.0 MVP | 2 | 81 | 10 | 120 | External API reliability (BRef, Kalshi) |
| v2.0 Live Platform | 3 | ~99 | 16 | — | Production cold-start OOM; Opening Day NaN features |
