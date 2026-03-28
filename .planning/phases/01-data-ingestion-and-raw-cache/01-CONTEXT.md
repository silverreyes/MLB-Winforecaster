# Phase 1: Data Ingestion and Raw Cache - Context

**Gathered:** 2026-03-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Fetch all raw data sources needed for the forecasting system — MLB schedules/confirmed starters, historical team batting stats, starting pitcher stats, Statcast metrics, and Kalshi game-winner market prices — and store them locally as Parquet files. Development should never re-scrape once data is cached. Feature engineering and modeling are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Code Structure
- Notebooks + `src/data/` Python modules: each data source gets a loader in `src/data/`, notebooks call the loaders
- One notebook per data source: MLB Stats API, pybaseball team batting, pybaseball SP stats, Statcast, Kalshi
- `src/data/` lives at repo root (standard Python layout — Phase 2's FeatureBuilder can import from it directly)
- `requirements.txt` at repo root for all dependencies — no `!pip install` cells inside notebooks

### Cache Layout
- `data/` at repo root, added to `.gitignore` — never committed
- Organized by source: `data/raw/mlb_api/`, `data/raw/pybaseball/`, `data/raw/statcast/`, `data/raw/kalshi/`
- One Parquet file per season per category: `team_batting_2015.parquet`, `sp_stats_2021.parquet`, etc.
- JSON manifest at `data/raw/cache_manifest.json` — tracks each file with: season, fetch date, row count. Notebooks check manifest before hitting any API.

### 2020 Season Handling
- Ingest 2020 like any other season — do NOT exclude from cache
- Add `is_shortened_season=True` (and `season_games=60`) column to ALL 2020 records: game logs, team batting, SP stats, Statcast
- Phase 2 and 3 decide whether to filter, weight, or include 2020 based on model results

### Kalshi Storage Format
- Parsed game-level table: one row per game with columns: `date`, `home_team`, `away_team`, `kalshi_yes_price`, `kalshi_no_price`, `result` (YES/NO), `market_ticker`
- Directly joinable on `(date, home_team, away_team)` in Phase 4
- Team name normalization: `src/data/team_mappings.py` maps Kalshi ticker abbreviations to canonical team names used by pybaseball/MLB Stats API — shared across all phases
- Kalshi auth: optional — if `KALSHI_API_KEY` env var is set, use it; otherwise fall back to public unauthenticated API (confirmed working for settled market data)

### Claude's Discretion
- Exact pybaseball function calls and parameters for each stat category
- Pagination and rate-limiting strategy for MLB Stats API
- Parquet compression settings and schema types
- Coverage validation logic inside each notebook (what constitutes "complete" for a season)
- Cache manifest update logic

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §DATA-01 through DATA-06 — all data ingestion acceptance criteria for this phase

### Roadmap
- `.planning/ROADMAP.md` §Phase 1 — goal, success criteria, pre-flight notes (Kalshi API verified, coverage starts 2025-04-16)

### No external specs
No ADRs or design docs yet — project is new. All requirements are captured in REQUIREMENTS.md and decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `check_kalshi_mlb.py` — pre-flight Kalshi verification script. Demonstrates: cursor-based pagination, series ticker filtering, market response structure, date parsing from API response fields. The Kalshi ingestion loader in `src/data/` should follow this same pattern. Base URL confirmed: `https://api.elections.kalshi.com/trade-api/v2`.

### Established Patterns
- No existing patterns yet — this is the first phase. Patterns established here become conventions for Phases 2–4.

### Integration Points
- `src/data/` created in this phase is the shared import surface for Phase 2's FeatureBuilder
- `data/raw/` directory structure and Parquet file naming established here is what all downstream phases read
- `src/data/team_mappings.py` created here is reused in Phase 4's Kalshi join logic

</code_context>

<specifics>
## Specific Ideas

No specific references — open to standard pybaseball and MLB Stats API patterns.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 01-data-ingestion-and-raw-cache*
*Context gathered: 2026-03-28*
