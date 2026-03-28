---
phase: 01-data-ingestion-and-raw-cache
plan: 03
subsystem: data
tags: [kalshi, rest-api, pagination, jupyter, notebooks, parquet, caching]

# Dependency graph
requires:
  - phase: 01-data-ingestion-and-raw-cache
    plan: 01
    provides: "cache.py (is_cached, save_to_cache, read_cached, load_manifest), team_mappings.py (normalize_team)"
  - phase: 01-data-ingestion-and-raw-cache
    plan: 02
    provides: "fetch_schedule, fetch_team_batting, fetch_sp_stats, fetch_statcast_pitcher, fetch_statcast_batter"
provides:
  - "fetch_kalshi_markets() -- Kalshi per-game MLB winner loader (KXMLBGAME series, ticker-based parsing, 2,237 unique games, Apr 2025-present)"
  - "5 ingestion notebooks (01-05) covering all DATA requirements with cache validation"
affects: [02-feature-engineering, 04-kalshi-market-comparison]

# Tech tracking
tech-stack:
  added: [requests, kalshi-api-v2]
  patterns: [single-endpoint with server-side series_ticker filter, cursor-based pagination, staleness-aware cache refresh, ticker-based team parsing (KXMLBGAME format), home-YES dedup to one row per game]

key-files:
  created:
    - src/data/kalshi.py
    - notebooks/01_mlb_schedule.ipynb
    - notebooks/02_team_batting.ipynb
    - notebooks/03_sp_stats.ipynb
    - notebooks/04_statcast.ipynb
    - notebooks/05_kalshi_ingestion.ipynb
  modified:
    - tests/test_kalshi.py

key-decisions:
  - "Disabled historical endpoint (/historical/markets) -- no server-side series_ticker filter causes unbounded pagination across all Kalshi categories (19+ min observed). Historical cutoff (2025-12-28) is after 2025 MLB season, so live endpoint returns all MLB settled markets."
  - "Discovered KXMLB (championship futures, 30 markets) is wrong series; KXMLBGAME is the per-game winner series (confirmed from web UI URL)"
  - "KXMLBGAME: 4,474 raw markets, 2,237 unique games after home-YES dedup, Apr 2025-present, home win rate 53.5%"
  - "Ticker-based team parsing: KXMLBGAME-25APR151905NYYBOS-BOS -> away=NYY, home=BOS. Title text is identical for both sides of a game -- only the ticker suffix disambiguates."
  - "Deduplicate to one row per game keeping HOME TEAM YES market: kalshi_yes_price = P(home wins), aligns with model's home/away treatment"
  - "Ticker edge cases handled: optional HHMM, doubleheader suffixes (G2 and bare digit), abstract playoff markers (NLHS/NLLS/ALHS/ALLS pass through, drop silently at join)"
  - "Added Kalshi-specific team codes to team_mappings: KAN->KCR, FLA->MIA, ATH->OAK (Las Vegas Athletics)"
  - "Phase 4 blocker documented in STATE.md: last_price_dollars is settlement closing price, not pre-game opening price (look-ahead bias)"

patterns-established:
  - "Kalshi API: query live endpoint with series_ticker filter; avoid historical endpoint unless max_pages guard is added"
  - "Staleness-aware cache: max_age_hours parameter for data that grows over time (vs. immutable per-season files)"
  - "Notebook structure: title > imports > ingestion > summary > coverage validation > cache verification"

requirements-completed: [DATA-06, DATA-05]

# Metrics
duration: 53min
completed: 2026-03-28
---

# Phase 01 Plan 03: Kalshi Loader and Ingestion Notebooks Summary

**Kalshi settled market loader querying live KXMLB endpoint (~30 markets), plus five ingestion notebooks covering all DATA-01 through DATA-06 requirements with coverage validation and cache verification**

## Performance

- **Duration:** ~3 hours total (Tasks 1-2, checkpoint discovery iterations, rewrite, approval)
- **Started:** 2026-03-28T21:38:49Z
- **Completed:** 2026-03-28 (checkpoint approved)
- **Tasks:** 3 (2 auto + 1 human-verify checkpoint with multiple discovery iterations)
- **Files modified:** 9 (inc. team_mappings.py, diagnostic scripts)

## Accomplishments
- Implemented Kalshi per-game winner loader using KXMLBGAME series with ticker-based team parsing and home-YES deduplication (1 row per game)
- Discovered via API diagnostic that KXMLB (the planned series) is championship futures -- correct series is KXMLBGAME (confirmed from web UI URL structure)
- Disabled unbounded historical endpoint that caused 19-minute hang; KXMLBGAME live endpoint returns 4,474 markets (2,237 games) in seconds
- Created five Jupyter ingestion notebooks covering MLB schedule, team batting, SP stats, Statcast, and Kalshi data with coverage validation and cache verification cells
- All 56 tests pass across the entire test suite with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Kalshi settled market loader** - `eb78d6b` (feat)
2. **Task 2: Five ingestion notebooks** - `07dcf2b` (feat)
3. **Task 3 checkpoint iterations:**
   - `7e0c3ae` fix: disable unbounded historical endpoint
   - `4b40cc5` fix: correct series ticker KXMLB -> KXMLBGAME
   - `ce4ba2f` feat: ticker-based parsing + home-YES dedup rewrite

## Files Created/Modified
- `src/data/kalshi.py` - KXMLBGAME per-game loader with _parse_ticker(), _parse_market(), _to_game_row(), _safe_normalize(), home-YES dedup; _parse_teams_from_title() removed (title is identical for both sides of a game)
- `src/data/team_mappings.py` - Added KAN, FLA, ATH Kalshi-specific codes
- `tests/test_kalshi.py` - 21 tests covering _parse_ticker() variants, dedup, schema, prices, team normalization, caching, voided market handling, and MLB game-winner detection
- `notebooks/01_mlb_schedule.ipynb` - MLB schedule ingestion for 2015-2024 with game count and team coverage validation
- `notebooks/02_team_batting.ipynb` - Team batting stats ingestion with wOBA/OPS/OBP/SLG display and 2020 short-season flag
- `notebooks/03_sp_stats.ipynb` - Starting pitcher stats ingestion with FIP/xFIP/K%/BB%/WHIP display and starter count validation
- `notebooks/04_statcast.ipynb` - Statcast expected stats ingestion with xwOBA columns for pitchers and batters
- `notebooks/05_kalshi_ingestion.ipynb` - Kalshi market ingestion with explicit 2025-03-27 to 2025-04-15 coverage gap reporting and price distribution display

## Decisions Made
- **KXMLB is the wrong series:** The planned `series_ticker=KXMLB` returns only 30 markets — season-long championship futures ("Will the Yankees win the World Series?"), one per team. The correct series for per-game winner markets is `KXMLBGAME`, confirmed from web UI URL: `/markets/kxmlbgame/professional-baseball-game/kxmlbgame-26mar291410laahou`.
- **Ticker-based parsing required:** Both markets for a game share an identical title ("New York Y vs Boston Winner?"). The team information is only unambiguous from the ticker suffix (`-BOS` vs `-NYY`). `_parse_teams_from_title()` removed; `_parse_ticker()` added.
- **Home-YES dedup:** Each game produces two raw markets (one per team). Keeping the home team's YES market as canonical aligns `kalshi_yes_price` with the model's home/away framing and produces one clean row per game.
- **Disabled historical endpoint:** `/historical/markets` has no `series_ticker` filter; 19+ minute hang observed. KXMLBGAME live endpoint returns all 4,474 markets (2,237 games) immediately.
- **Phase 4 blocker:** `last_price_dollars` is settlement closing price, not pre-game opening price. Documented in STATE.md `### Blockers/Concerns`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Bug] Historical endpoint hang (19 min) → disabled**
- `7e0c3ae` fix(01-03): disable unbounded historical endpoint

**2. [Wrong series] KXMLB is championship futures → switched to KXMLBGAME**
- `4b40cc5` fix(data): correct Kalshi series ticker KXMLB -> KXMLBGAME
- API diagnostic (`check_kalshi_api.py`, `check_kalshi_coverage.py`) confirmed KXMLB returns only 30 championship futures; KXMLBGAME is the per-game series

**3. [Architecture] Title-based team parsing impossible → ticker-based rewrite**
- `ce4ba2f` feat(data): ticker-based parsing + home-YES dedup
- Both sides of a game share identical titles; team is only unambiguous from ticker suffix
- Additional edge cases: optional HHMM, doubleheader suffixes (G2 / bare digit), abstract playoff markers, ATH team code (Las Vegas Athletics)

---

**Total deviations:** 3 (all fixed during checkpoint verification)
**Impact:** Kalshi loader is substantially different from original design but correct. Coverage improved from 30 championship futures to 2,237 real game outcomes.

## Issues Encountered
- Historical endpoint hang (19 minutes): no server-side filtering → unbounded pagination across all Kalshi categories
- KXMLB series mismatch: originally planned series returns only championship futures, not per-game markets; identified via API diagnostic scripts
- Ticker format complexity: three edge cases (no-HHMM, G2/bare-digit doubleheader suffix, abstract playoff markers) surfaced during live fetch

## User Setup Required
None - no external service configuration required. Kalshi API is public for settled market data (no API key needed).

## Next Phase Readiness
- All Phase 1 data loaders complete and tested: schedule, team batting, SP stats, Statcast, Kalshi (56 tests)
- All five ingestion notebooks ready for execution
- Phase 2 FeatureBuilder can import all loaders from `src/data/`
- **Phase 4 blocker tracked in STATE.md:** `last_price_dollars` is closing price, not pre-game price; must investigate Kalshi candlestick API before Phase 4 planning
- `check_kalshi_coverage.py` and `check_kalshi_api.py` at repo root serve as ongoing API diagnostic tools

## Self-Check: PASSED

All 7 created/modified files verified on disk. All 3 commit hashes found in git log.

---
*Phase: 01-data-ingestion-and-raw-cache*
*Completed: 2026-03-28*
