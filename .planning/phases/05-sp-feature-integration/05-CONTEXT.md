# Phase 5: SP Feature Integration — Context

**Gathered:** 2026-03-29
**Status:** Ready for planning
**Source:** Pre-flight verification by user before planning session

<domain>
## Phase Boundary

This phase fixes two v1 data bugs (xwOBA column names), converts season-aggregate SP stats to season-to-date rolling to eliminate temporal leakage, adds new SP differential features, builds the ID-based SP name matching cross-reference, and produces `feature_store_v2.parquet`. Phase 5 produces no model artifacts — it ends when the feature store is verified correct and temporally safe. Phase 6 (model retrain) starts from that artifact.

</domain>

<decisions>
## Implementation Decisions

### SP Stats Primary Source — FanGraphs via pybaseball (LOCKED)

`pybaseball.pitching_stats()` is confirmed working: returns 52 rows, 393 columns including ERA, FIP, xFIP, K/BB, WHIP, K%, BB%, SIERA. This is the primary source for season-level SP features. The v1 code already calls this endpoint; it is reliable as of 2026-03-29.

Design around FanGraphs as the primary SP stats source. ID-based matching (not name string matching) is the approach for joining MLB Stats API pitcher names to FanGraphs data.

### Pitcher Game Log Cache — Sparse (LOCKED)

The cached pitcher game log has only 3 columns: `date`, `innings_pitched`, `earned_runs`. The following fields are NOT present in the current cache:
- `numberOfPitches` (needed for sp_pitch_count_last_diff — SP-08)
- `strikeouts`, `baseOnBalls`, `homeRunsAllowed` (needed for per-game FIP computation — SP-07 sp_recent_fip_diff)

This is a hard constraint that affects SP-07 and SP-08. The research and planning phase must resolve:

**Decision point for SP-07 (sp_recent_fip_diff):** 30-day rolling FIP requires K/BB/HR/IP per game. The current cache has IP and ER but not K/BB/HR. Options:
  - (A) Re-fetch game logs with richer MLB Stats API hydration parameters (`stats?stats=gameLog&group=pitching` with additional `fields` parameter) and extend the cache
  - (B) Use 30-day rolling ERA instead of FIP (ER and IP are available; ERA = 9 * (ER/IP)); weaker signal but zero re-fetch cost
  - (C) Drop sp_recent_fip_diff entirely for Phase 5

**Decision point for SP-08 (sp_pitch_count_last_diff):** `numberOfPitches` is not in the current cache. Options:
  - (A) Re-fetch game logs with richer hydration (same re-fetch as SP-07 option A)
  - (B) Drop pitch count feature; use only sp_days_rest_diff

The research agent should determine whether the MLB Stats API `stats/v1/people/{id}/stats` or `stats/v1/people/{id}/stats?stats=gameLog` endpoint supports a `fields` parameter or equivalent hydration that returns K, BB, HR, and numberOfPitches per game. If yes, a single re-fetch populates both SP-07 and SP-08. If the MLB Stats API game log structure is fixed and cannot return these fields, drop both features or fall back to ERA-based rolling for SP-07.

### ID-Based SP Name Matching (LOCKED)

Use mlb_player_id → fangraphs_id cross-reference for joining SP names between MLB Stats API (game schedules) and FanGraphs data (pitching_stats). The research agent must determine the best source for this mapping: pybaseball `playerid_lookup()`, the Chadwick Bureau register CSV, or a maintained mapping table. The cross-reference must cover players from 2015–2024 including retired pitchers.

### Temporal Safety Pattern (LOCKED)

All season-to-date SP features use the established v1 pattern: cumsum over sorted game-by-game data, then shift(1) so each game row sees only stats through the previous game. No season-aggregate lookups for in-season features. This eliminates the leakage in v1 where a game on day N saw full-season stats including games N+1 through end-of-season.

### Version Isolation (LOCKED)

`feature_store_v2.parquet` is a new file. `feature_store_v1.parquet` (or the existing file name) is preserved unchanged. Phase 6 trains on v2; historical v1 comparison uses v1.

### Feature Set Constants (LOCKED)

`feature_sets.py` must export:
- `TEAM_ONLY_FEATURE_COLS` — team-level features only (safe for pre-lineup prediction)
- `SP_ENHANCED_FEATURE_COLS` — full feature set including all new SP columns
- `V1_FULL_FEATURE_COLS` — v1 feature set preserved for apples-to-apples Brier comparison

### Claude's Discretion

- Exact pandas groupby/cumsum/shift implementation (follow v1 rolling_ops pattern)
- Whether to add SP data as new columns to the existing feature store or rebuild from scratch
- Test structure (follow v1 test patterns in tests/)
- Whether to add a data re-fetch script for richer game log hydration or inline it into the existing SP loader

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing SP Feature Code
- `src/features/feature_builder.py` — existing `_add_sp_features()` method; this is what gets extended, not replaced
- `src/data/sp_stats.py` — FanGraphs pitching_stats loader; already fetches season-level data
- `src/data/sp_recent_form.py` — existing 30-day ERA loader using pitching_stats_range(); examine the rolling pattern here
- `src/features/feature_sets.py` — existing CORE_FEATURE_COLS and related constants; new constants added here

### Game Log Cache
- `data/cache/` — Parquet cache directory; inspect actual pitcher game log file to confirm 3-column structure
- `src/data/game_logs.py` (if exists) — existing game log loader; examine hydration parameters

### v1 Rolling Pattern Reference
- `src/features/feature_builder.py` — `_add_rolling_features()` method; uses shift(1) on rolling window; replicate this pattern for season-to-date SP features

### ID Mapping
- `src/data/team_mappings.py` — existing name normalization patterns; reference for understanding the current mismatch approach

### Requirements
- `.planning/REQUIREMENTS.md` — SP-01 through SP-12 (this phase's requirements)
- `.planning/ROADMAP.md` — Phase 5 success criteria

### Test Patterns
- `tests/` — existing test structure; new SP feature tests must follow same patterns
- Any existing SP stat tests for reference

</canonical_refs>

<specifics>
## Specific Constraints

- `pybaseball.pitching_stats(start_dt, end_dt)` returns season-level aggregates per pitcher (not game-by-game) — it is NOT suitable for rolling window computation. Rolling must come from game logs.
- The existing game log cache columns confirmed as: `date`, `innings_pitched`, `earned_runs` only.
- `numberOfPitches` is confirmed NOT present in the current game log cache.
- pybaseball version is confirmed working for FanGraphs season stats as of 2026-03-29.
- pandas 2.2.x is pinned — no pandas 3.0 patterns.
- All new features must be differentials (home_sp_value - away_sp_value) matching v1 convention.

</specifics>

<deferred>
## Deferred

- Home/away SP splits per pitcher (deferred to v3 — sample size insufficient)
- xERA from Statcast (deferred — redundant with xwOBA)
- Weather features, Elo ratings, bullpen fatigue (v3)

</deferred>

---
*Phase: 05-sp-feature-integration*
*Context gathered: 2026-03-29 from pre-flight verification*
