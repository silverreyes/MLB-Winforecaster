# Phase 2: Feature Engineering and Feature Store - Context

**Gathered:** 2026-03-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Transform raw Phase 1 Parquet caches into a single game-level feature matrix with verified temporal safety. Outputs one Parquet file with one row per historical game containing all differential features (SP, offense, bullpen, park, rolling form, advanced), the outcome label, and Kalshi implied probability where available. Modeling, backtesting, and Kalshi comparison are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Per-game data ingestion (new in Phase 2)
- Phase 1 only cached season-level stats (team batting, SP stats). Rolling features require per-game data.
- A dedicated ingestion notebook fetches and caches per-game team batting logs and SP rolling stats BEFORE FeatureBuilder runs. Consistent with Phase 1's notebook-per-source pattern.
- Per-game team batting: `pybaseball.team_game_logs(season, team)` for all 30 teams × 10 seasons (300 calls). Must be cached to Parquet in `data/raw/pybaseball/` using the same `is_cached()` / `save_to_cache()` pattern as Phase 1 loaders.
- **Rate limiting is mandatory**: the plan must explicitly address request pacing for the 300-call scrape. Do not proceed without a documented delay/retry strategy.
- SP recent form: rolling 30-day ERA window via `pybaseball.pitching_stats_range(start_dt, end_dt)`. Simpler than last-N-starts tracking; similar signal.

### Rolling feature design
- Team offense rolling: true 10-game rolling window on team OPS from per-game batting logs. `rolling(10).mean()` with `shift(1)` for temporal safety (FEAT-07).
- All rolling windows **reset at season start** — no cross-season carry-over. Off-season roster changes, rest, and rule changes make prior-season stats a poor predictor of game 1 form.
- Early-season games (games 1–9 of a season, where the 10-game window is incomplete): rolling features are NaN, not imputed or partially filled. Phase 3 decides whether to drop or allow partial windows during model training.

### 2020 season treatment
- Include 2020 games in the feature matrix with the `is_shortened_season=True` flag intact (already set by Phase 1 loaders).
- Season-boundary resets apply to 2020 the same as all other seasons.
- Phase 3 can test with and without 2020 during backtesting; the matrix itself does not pre-judge.

### Feature coverage & NaN policy
- **TBD starters**: exclude any game row where either team's starting pitcher is TBD or unidentifiable. Pre-game predictions require confirmed starters — these rows are not actionable.
- **Statcast / xwOBA gaps**: include all game rows; leave xwOBA and related Statcast columns as NaN for seasons or pitchers with no Statcast coverage. Models train only on available data; Phase 3 documents coverage gaps.
- **Incomplete rolling windows** (early-season games): NaN in rolling feature columns. Not dropped at this stage — Phase 3 controls filtering.
- No imputation at the feature matrix level. NaN means "not available" and should propagate cleanly to downstream consumers.

### Feature exploration notebook
- Standalone notebook (separate from the build notebook). Reads the final feature Parquet and explores it.
- Primary purpose: **sanity check and leakage detection** before modeling:
  1. Coverage table: % non-null per feature per season
  2. Correlation of each feature with home-win outcome (flag anything suspiciously high, e.g., > 0.7 raw correlation — in a noisy sports prediction problem, 0.3 is a legitimate strong signal, not leakage; only near-perfect correlations warrant investigation)
  3. Temporal ordering spot-checks: verify `shift(1)` is working — confirm a game's feature values do not change if that game's outcome is removed
- Notebook should be runnable independently without re-building the matrix.

### Claude's Discretion
- Exact `src/features/` module layout and class structure for FeatureBuilder
- Log5 win probability formula implementation (standard sabermetric formula)
- Pythagorean win percentage formula and exponent choice (1.83 standard vs. 2)
- Park run factor: whether to use 3-year rolling average or a fixed lookup table
- Parquet schema details (column naming conventions, dtypes)
- Exact output path for feature matrix (e.g., `data/features/feature_matrix.parquet`)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §FEAT-01 through FEAT-08 — all feature engineering acceptance criteria for this phase

### Roadmap
- `.planning/ROADMAP.md` §Phase 2 — goal, success criteria, dependency on Phase 1

### Phase 1 context (patterns to follow)
- `.planning/phases/01-data-ingestion-and-raw-cache/01-CONTEXT.md` — cache infrastructure decisions, file naming conventions, notebook structure pattern, team normalization approach

### No external specs
No ADRs or design docs yet. Requirements fully captured in REQUIREMENTS.md and decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/data/cache.py` — `is_cached()`, `save_to_cache()`, `read_cached()`, `update_manifest()`: Phase 2's per-game ingestion notebook and FeatureBuilder should use this same cache infrastructure
- `src/data/team_mappings.py` — canonical team name normalization; all per-game logs must go through `normalize_team()` before join
- `src/data/team_batting.py`, `sp_stats.py`, `mlb_schedule.py` — patterns for pybaseball calls with cache-check-then-fetch; rate limiting approach here is the template for Phase 2's 300-call scrape
- `src/data/mlb_schedule.py` — `schedule_{season}.parquet` has `home_team`, `away_team`, `game_date`, `home_probable_pitcher`, `away_probable_pitcher`, `winning_team` columns — this is the backbone the feature matrix is built on

### Established Patterns
- Cache key naming: `{source}_{season}` or `{source}_{season}_mings{N}` — Phase 2 per-game keys should follow e.g., `team_game_log_{season}_{team}`
- 2020 short-season flag is set at cache time by Phase 1 loaders — FeatureBuilder can filter on `is_shortened_season` if needed but should keep rows by default
- Notebooks use `src/data/` via direct import (repo root in sys.path); Phase 2 notebooks will use `src/features/` the same way

### Integration Points
- FeatureBuilder reads from `data/raw/` Parquet files (Phase 1 output + new per-game Parquets)
- Feature matrix output is consumed by Phase 3 model training and Phase 4 Kalshi join
- Join key to Kalshi data is `(date, home_team, away_team)` — column names must match Phase 1 Kalshi Parquet exactly
- Phase 3 requires walk-forward splits by season — feature matrix must include `season` and `game_date` columns

</code_context>

<specifics>
## Specific Ideas

- Rate limiting for the 300-call per-game data scrape must be explicitly planned — not left to implementation discretion. The Phase 3 plan noted that unbounded pagination caused a 19-min timeout in Phase 1; same risk applies here.
- Feature exploration notebook should flag correlations > 0.3 with the outcome variable as potential leakage candidates — not automatic failures, but require explanation.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 02-feature-engineering-and-feature-store*
*Context gathered: 2026-03-28*
