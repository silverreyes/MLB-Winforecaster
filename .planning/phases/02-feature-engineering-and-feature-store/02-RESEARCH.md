# Phase 2: Feature Engineering and Feature Store - Research

**Researched:** 2026-03-28
**Domain:** Sports feature engineering, temporal safety, pandas rolling/shift operations, sabermetric formulas
**Confidence:** HIGH

## Summary

Phase 2 transforms Phase 1's raw Parquet caches into a single game-level feature matrix. The core challenge is twofold: (1) computing meaningful differential features from multiple data sources and joining them correctly, and (2) guaranteeing temporal safety so that no feature for game N uses information from game N or later. The project already has solid cache infrastructure and team normalization from Phase 1; Phase 2 builds on top of these with a new `src/features/` module and two new per-game data sources (team batting game logs and SP rolling form).

The critical technical risks are: look-ahead leakage in rolling features (mitigated by `shift(1)` discipline and unit tests), team abbreviation mismatches across data sources (mitigated by the existing `normalize_team()` function and the fact that pybaseball uses the same canonical codes as our project), and rate limiting for the 300-call `team_game_logs` scrape (mitigated by explicit delay/retry strategy). Park factors require a static lookup table since pybaseball has no built-in park_factors function -- this is the simplest reliable approach.

**Primary recommendation:** Build FeatureBuilder as a class in `src/features/feature_builder.py` that reads all raw Parquet files, computes features per-game with strict temporal ordering, and outputs a single feature matrix Parquet. Use `shift(1)` on all rolling computations and verify with unit tests that remove a game's outcome without changing its feature values.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Phase 1 only cached season-level stats. Rolling features require per-game data, fetched via a dedicated ingestion notebook.
- Per-game team batting: `pybaseball.team_game_logs(season, team)` for all 30 teams x 10 seasons (300 calls). Cached to Parquet in `data/raw/pybaseball/` using `is_cached()`/`save_to_cache()`.
- **Rate limiting is mandatory** for the 300-call scrape. Must be explicitly planned with delay/retry strategy.
- SP recent form: rolling 30-day ERA window via `pybaseball.pitching_stats_range(start_dt, end_dt)`. Simpler than last-N-starts tracking.
- Team offense rolling: true 10-game rolling window on team OPS from per-game batting logs. `rolling(10).mean()` with `shift(1)`.
- All rolling windows **reset at season start** -- no cross-season carry-over.
- Early-season games (games 1-9): rolling features are NaN, not imputed.
- Include 2020 games with `is_shortened_season=True` flag intact. Phase 3 decides whether to exclude.
- **TBD starters**: exclude game rows where either SP is TBD or unidentifiable.
- **Statcast/xwOBA gaps**: include all game rows; leave xwOBA columns as NaN for missing coverage.
- **Incomplete rolling windows**: NaN in rolling columns. No imputation at feature matrix level.
- Feature exploration notebook is standalone (separate from build notebook). Reads final Parquet.
- Exploration notebook checks: coverage table per feature per season, correlation with outcome (flag > 0.7 as potential leakage), temporal ordering spot-checks.

### Claude's Discretion
- Exact `src/features/` module layout and class structure for FeatureBuilder
- Log5 win probability formula implementation
- Pythagorean win percentage formula and exponent choice (1.83 standard vs. 2)
- Park run factor: whether to use 3-year rolling average or a fixed lookup table
- Parquet schema details (column naming, dtypes)
- Exact output path for feature matrix

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FEAT-01 | SP differential (FIP, xFIP, K%) between confirmed home/away SPs | Phase 1 `sp_stats.py` already caches season-level FanGraphs pitcher stats with FIP, xFIP, K% columns. Join on pitcher name from schedule's `home_probable_pitcher`/`away_probable_pitcher`. |
| FEAT-02 | Team offensive differential (wOBA, OPS, Pythagorean win%) | Phase 1 `team_batting.py` caches season-level wOBA, OPS. Pythagorean requires R/RA from schedule or game logs. Use exponent 1.83 (Baseball-Reference standard). |
| FEAT-03 | Rolling 10-game team OPS differential | New per-game ingestion via `team_game_logs()` needed. `rolling(10).mean()` with `shift(1)` and season-boundary reset. |
| FEAT-04 | Bullpen ERA differential | Derive from `pitching_stats()` with `qual=0`: all pitchers minus those with GS >= threshold = relief pitchers. Aggregate team-level bullpen ERA/FIP. |
| FEAT-05 | Home/away indicator and 3-year rolling park run factor | Home/away is trivial from schedule. Park factors: use static lookup table scraped once or hardcoded -- pybaseball has no park_factors function. |
| FEAT-06 | SIERA differential, xwOBA differential, SP recent form (last 30-day ERA), Log5 win probability, bullpen FIP differential | SIERA available in `pitching_stats()` (334-column FanGraphs output). xwOBA from Phase 1 Statcast cache. SP recent form via `pitching_stats_range()`. Log5 formula: `P = pA*(1-pB) / (pA*(1-pB) + (1-pA)*pB)`. |
| FEAT-07 | Temporal safety: `shift(1)`, `as_of_date` parameter, leakage unit tests | `shift(1)` on all rolling features within season-grouped data. Unit test pattern: compute features, remove game outcome, recompute -- values must match. |
| FEAT-08 | Single Parquet output: one row per game, all features, outcome, Kalshi implied prob | Join all feature sources on `(game_date, home_team, away_team)`. Left-join Kalshi data (only 2025 coverage). Output to `data/features/feature_matrix.parquet`. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pandas | 2.2.3 | DataFrame operations, rolling windows, groupby | Already pinned in project; HARD PIN at 2.2.x due to pybaseball incompatibility |
| pybaseball | 2.2.7 | `team_game_logs()`, `pitching_stats_range()`, `pitching_stats()` | Already installed; provides per-game data and date-range pitching stats |
| pyarrow | 23.0.1 | Parquet I/O engine | Already installed; used by all Phase 1 cache operations |
| numpy | 2.4.3 | Numeric operations for formulas | Already installed as pandas dependency |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| matplotlib | >=3.7.0 | Feature distribution plots in exploration notebook | Already in requirements.txt |
| seaborn | >=0.13.0 | Correlation heatmaps, distribution plots | Already in requirements.txt |
| pytest | 8.1.1 | Leakage detection tests, FeatureBuilder unit tests | Already in requirements.txt |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Static park factor table | Live FanGraphs scrape | pybaseball has no park_factors function; scraping FanGraphs Guts page is fragile. Static table is simpler and park factors change slowly. |
| `pitching_stats_range()` for SP form | Last-N-starts tracking | Date-range approach (30-day window) is simpler and was explicitly chosen in CONTEXT.md. Both provide similar signal. |
| Custom team_game_logs caching | Direct pybaseball calls in FeatureBuilder | Must cache to Parquet first (300 calls); FeatureBuilder reads from cache only. Follows Phase 1 pattern. |

**Installation:**
```bash
# No new packages needed -- all dependencies already in requirements.txt
pip install -r requirements.txt
```

## Architecture Patterns

### Recommended Project Structure
```
src/
  data/             # Phase 1 (existing)
    cache.py
    team_mappings.py
    mlb_schedule.py
    team_batting.py
    sp_stats.py
    statcast.py
    kalshi.py
  features/         # Phase 2 (new)
    __init__.py
    feature_builder.py   # Main FeatureBuilder class
    formulas.py          # Log5, Pythagorean, park factors
    game_logs.py         # Per-game team batting log loader (new pybaseball calls)

notebooks/
  06_team_game_logs.ipynb     # Per-game data ingestion (new)
  07_feature_matrix.ipynb     # Build feature matrix via FeatureBuilder
  08_feature_exploration.ipynb # Standalone exploration/leakage check

data/
  raw/pybaseball/             # Per-game logs cached here (new)
    team_game_log_{season}_{team}.parquet
  features/                   # Feature matrix output (new)
    feature_matrix.parquet

tests/
  test_feature_builder.py     # FeatureBuilder unit tests
  test_formulas.py            # Formula correctness tests
  test_leakage.py             # Temporal safety / leakage detection tests
```

### Pattern 1: FeatureBuilder Class
**What:** Single class that orchestrates all feature computation from raw cached data.
**When to use:** Every time the feature matrix needs to be regenerated.
**Key design:**
```python
class FeatureBuilder:
    """Builds the game-level feature matrix from Phase 1 raw caches.

    All rolling features use shift(1) to prevent look-ahead leakage.
    Rolling windows reset at season boundaries.
    """

    def __init__(self, seasons: list[int], as_of_date: str | None = None):
        """
        Args:
            seasons: List of seasons to include (e.g., range(2015, 2025))
            as_of_date: Optional cutoff date (YYYY-MM-DD). If set, only
                        games before this date are used for rolling stats.
                        Critical for walk-forward evaluation in Phase 3.
        """
        self.seasons = seasons
        self.as_of_date = as_of_date

    def build(self) -> pd.DataFrame:
        """Build complete feature matrix. Returns one row per game."""
        schedule = self._load_schedule()         # backbone
        schedule = self._filter_tbd_starters(schedule)
        schedule = self._add_outcome_label(schedule)
        schedule = self._add_sp_features(schedule)       # FEAT-01, FEAT-06
        schedule = self._add_offense_features(schedule)   # FEAT-02
        schedule = self._add_rolling_features(schedule)   # FEAT-03
        schedule = self._add_bullpen_features(schedule)   # FEAT-04, FEAT-06
        schedule = self._add_park_features(schedule)      # FEAT-05
        schedule = self._add_advanced_features(schedule)   # FEAT-06
        schedule = self._add_kalshi_features(schedule)     # FEAT-08
        return schedule
```

### Pattern 2: Temporal Safety via shift(1) with Season Reset
**What:** All rolling features use `shift(1)` within season-grouped data to prevent using current game's data.
**When to use:** Every rolling feature computation.
**Example:**
```python
# Correct: shift(1) prevents current game's OPS from leaking
def _compute_rolling_ops(self, game_logs: pd.DataFrame) -> pd.DataFrame:
    """Compute 10-game rolling OPS per team per season with temporal safety."""
    game_logs = game_logs.sort_values(["season", "team", "game_date"])

    # Group by team and season (resets at season boundary)
    game_logs["rolling_ops_10"] = (
        game_logs
        .groupby(["team", "season"])["OPS"]
        .transform(lambda x: x.shift(1).rolling(10, min_periods=10).mean())
    )
    # Games 1-9 of each season will be NaN (incomplete window)
    return game_logs
```

### Pattern 3: Differential Features (Home minus Away)
**What:** All features are computed as home_value minus away_value differentials.
**When to use:** Every feature that has both a home and away component.
**Example:**
```python
# SP FIP differential: positive means home SP has higher (worse) FIP
df["sp_fip_diff"] = df["home_sp_fip"] - df["away_sp_fip"]

# Team OPS differential: positive means home team has higher (better) OPS
df["team_ops_diff"] = df["home_team_ops"] - df["away_team_ops"]
```

### Pattern 4: Cache-Then-Compute for Per-Game Data
**What:** New per-game data sources follow the same cache-check-then-fetch pattern as Phase 1 loaders.
**When to use:** The 300-call `team_game_logs` scrape and `pitching_stats_range` calls.
**Example:**
```python
# In src/features/game_logs.py
def fetch_team_game_log(season: int, team: str) -> pd.DataFrame:
    """Fetch per-game batting log for one team-season. Cache-aware."""
    key = f"team_game_log_{season}_{team}"
    parquet_path = f"pybaseball/team_game_log_{season}_{team}.parquet"

    if is_cached(key):
        return read_cached(key)

    df = team_game_logs(season, team, log_type="batting")
    # Add metadata columns
    df["team"] = team
    df["season"] = season
    df["is_shortened_season"] = season == 2020

    save_to_cache(df, key, parquet_path, season)
    return df
```

### Anti-Patterns to Avoid
- **Computing rolling features across season boundaries:** Off-season roster changes, rest, and rule changes invalidate prior-season rolling stats. Always groupby season.
- **Using `rolling(10).mean()` without `shift(1)`:** This includes the current game's outcome in the rolling window -- classic look-ahead leakage.
- **Imputing NaN rolling features for early-season games:** Early-season NaN is correct behavior. Imputation introduces assumptions that belong in Phase 3.
- **Joining on pitcher name without handling None/TBD:** Schedule rows with TBD starters must be excluded BEFORE joining SP stats. A TBD value joining on Name will silently produce NaN features.
- **Computing features inside notebooks instead of `src/features/`:** Feature logic must live in importable modules so Phase 3 can reuse the same FeatureBuilder for walk-forward evaluation (project constraint: FeatureBuilder shared between backtest and live pipelines).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rolling window statistics | Manual loop over games | `pandas.DataFrame.groupby().transform(lambda x: x.shift(1).rolling())` | Handles NaN, edge cases, vectorized performance |
| Parquet I/O | Custom serialization | `pandas.DataFrame.to_parquet()` / `pd.read_parquet()` with pyarrow | Already standardized in cache.py; handles compression, dtypes |
| Team name normalization | Per-source mapping dicts | `src.data.team_mappings.normalize_team()` | Already handles 50+ variants; single source of truth |
| Pythagorean win% | Custom formula from scratch | Simple function but use the 1.83 exponent (Baseball-Reference standard) | The exponent matters -- 2.0 is less accurate than 1.83 |
| Log5 probability | Complex probability model | Standard Bill James formula: `pA*(1-pB) / (pA*(1-pB) + (1-pA)*pB)` | Proven equivalent to Bradley-Terry/Elo; no need to reinvent |

**Key insight:** The formulas (Log5, Pythagorean) are simple enough to implement as pure functions. The complexity is in the data pipeline (correct joins, temporal ordering, season boundaries), not the math.

## Common Pitfalls

### Pitfall 1: Baseball Reference Team Codes in team_game_logs
**What goes wrong:** `pybaseball.team_game_logs()` uses Baseball Reference team codes as the `team` parameter, which mostly match our canonical codes but may differ for some historical names.
**Why it happens:** Different data sources use different abbreviation conventions.
**How to avoid:** Verified that pybaseball's `first_season_map` in `utils.py` uses the same codes as our project's canonical codes (WSN, KCR, TBR, SDP, SFG, CHW). The `team` parameter for `team_game_logs()` accepts these codes directly. Always pass canonical codes from our TEAM_MAP, not raw codes from other sources.
**Warning signs:** Empty DataFrames returned from `team_game_logs()` for specific teams.

### Pitfall 2: Rate Limiting for 300-Call Scrape
**What goes wrong:** pybaseball's `team_game_logs()` scrapes Baseball Reference HTML pages. 300 rapid requests (30 teams x 10 seasons) will trigger rate limiting or IP bans.
**Why it happens:** Baseball Reference has anti-scraping protections. pybaseball has internal caching but it is session-only.
**How to avoid:** Add explicit `time.sleep(2.0)` between calls (150 calls/5 min = safe rate). Use progress logging. Implement retry with exponential backoff on HTTP errors. Cache to Parquet after each successful call so partial runs resume cleanly.
**Warning signs:** HTTP 429 errors, connection timeouts, empty or error responses.

### Pitfall 3: Pitcher Name Matching Across Sources
**What goes wrong:** Schedule has pitcher names from MLB Stats API ("Gerrit Cole"). SP stats have names from FanGraphs ("Gerrit Cole"). These usually match but edge cases exist (accents, suffixes like Jr./III, traded mid-season players appearing under different team codes).
**Why it happens:** Different APIs use different name formats and team assignment timing.
**How to avoid:** Join on `(pitcher_name, season)` not just pitcher_name. For the feature matrix, a missing match produces NaN SP features -- acceptable per CONTEXT.md NaN policy. Log and count mismatches for quality monitoring.
**Warning signs:** High NaN rate in SP feature columns for specific seasons.

### Pitfall 4: Season Boundary in Rolling Windows
**What goes wrong:** A rolling(10) window at the start of a new season uses games from the previous season.
**Why it happens:** pandas rolling() operates on contiguous rows regardless of grouping unless explicitly grouped.
**How to avoid:** Always use `groupby(["team", "season"])` before any rolling operation. Early-season NaN is the correct output.
**Warning signs:** Game 1 of a season having non-NaN rolling features; suspiciously smooth transitions at season boundaries.

### Pitfall 5: Bullpen Stats Derivation
**What goes wrong:** No direct "bullpen ERA" field exists in pybaseball. Must be derived from all pitchers minus starting pitchers.
**Why it happens:** FanGraphs provides individual pitcher stats, not pre-aggregated bullpen stats.
**How to avoid:** Use `pitching_stats(season, qual=0)` to get ALL pitchers. Filter to relievers (GS == 0 or GS < threshold). Aggregate by team to get team-level bullpen ERA and FIP. Alternative: `team_game_logs(season, team, log_type="pitching")` provides game-level team pitching totals.
**Warning signs:** Bullpen ERA values that seem too low (accidentally including SP stats) or too high (missing key relievers).

### Pitfall 6: Kalshi Join Coverage
**What goes wrong:** Left-joining Kalshi data produces all-NaN Kalshi columns for 2015-2024 games (Kalshi coverage starts Apr 2025 only).
**Why it happens:** The Kalshi data is 2025-only; the feature matrix covers 2015-2025.
**How to avoid:** This is expected behavior. The Kalshi columns should be NaN for pre-2025 games. Phase 4 filters to 2025-only for the market comparison. Document this clearly in the Parquet schema.
**Warning signs:** Non-NaN Kalshi values for pre-2025 games would indicate a join error.

## Code Examples

### Log5 Win Probability
```python
def log5_probability(p_home: float, p_away: float) -> float:
    """Compute Log5 win probability for home team.

    Formula: P(home wins) = pA*(1-pB) / (pA*(1-pB) + (1-pA)*pB)
    where pA = home team win%, pB = away team win%.

    Both inputs should be winning percentages (0-1 range).
    Returns probability that home team wins (0-1 range).

    Source: Bill James, 1981 Baseball Abstract.
    Equivalent to Bradley-Terry model / Elo rating system.
    """
    numerator = p_home * (1 - p_away)
    denominator = p_home * (1 - p_away) + (1 - p_home) * p_away
    if denominator == 0:
        return 0.5  # Both teams have 0% or 100% -- degenerate case
    return numerator / denominator
```

### Pythagorean Win Percentage
```python
def pythagorean_win_pct(runs_scored: float, runs_allowed: float,
                         exponent: float = 1.83) -> float:
    """Compute Pythagorean expected winning percentage.

    Formula: W% = RS^exp / (RS^exp + RA^exp)

    Default exponent 1.83 is the Baseball-Reference standard,
    more accurate than the original exponent of 2.

    Source: Bill James, refined by Baseball-Reference.com
    """
    if runs_scored <= 0 and runs_allowed <= 0:
        return 0.5
    rs_exp = runs_scored ** exponent
    ra_exp = runs_allowed ** exponent
    if rs_exp + ra_exp == 0:
        return 0.5
    return rs_exp / (rs_exp + ra_exp)
```

### Park Factor Lookup (Static Table)
```python
# 3-year average park run factors (2022-2024), source: FanGraphs Guts
# Normalized to 100 = league average. Values > 100 = hitter-friendly.
# FanGraphs already halves their park factors for use on full-season stats.
PARK_FACTORS = {
    "COL": 116, "ARI": 107, "TEX": 106, "CIN": 105, "BOS": 104,
    "CHC": 103, "KCR": 102, "MIL": 102, "PHI": 101, "BAL": 101,
    "ATL": 100, "MIN": 100, "NYY": 100, "DET": 100, "CHW": 100,
    "HOU": 99,  "LAA": 99,  "STL": 99,  "TOR": 99,  "WSN": 99,
    "SFG": 98,  "NYM": 98,  "PIT": 98,  "CLE": 97,  "LAD": 97,
    "SDP": 97,  "TBR": 96,  "SEA": 96,  "MIA": 95,  "OAK": 95,
}

def get_park_factor(team: str) -> int:
    """Return park run factor for team's home park. Default 100 if unknown."""
    return PARK_FACTORS.get(team, 100)
```

**Note on park factors:** These values should be verified against FanGraphs Guts at implementation time. The exact values shown above are approximate; the implementer should scrape or manually transcribe current 3-year averages from https://www.fangraphs.com/tools/guts?type=pf. Using a static dict is intentional -- pybaseball has no park_factors function (confirmed via GitHub issue #409), and park factors change slowly enough that a static table is adequate for a 10-season backtest.

### Leakage Detection Unit Test
```python
def test_no_leakage_on_outcome_removal():
    """Verify that removing a game's outcome does not change its features.

    This is the canonical leakage test: if features change when we remove
    the current game's result, those features are using future information.
    """
    builder = FeatureBuilder(seasons=[2023])
    full_matrix = builder.build()

    # Pick a mid-season game (not early-season where rolling is NaN)
    test_game = full_matrix.iloc[500]
    game_date = test_game["game_date"]
    home_team = test_game["home_team"]

    # Remove this game's outcome from the source data
    # and rebuild features
    builder_without = FeatureBuilder(seasons=[2023])
    # Mask out the specific game before computing
    matrix_without = builder_without.build_excluding(game_date, home_team)

    # Same game's features should be identical
    matching_row = matrix_without[
        (matrix_without["game_date"] == game_date) &
        (matrix_without["home_team"] == home_team)
    ]

    feature_cols = [c for c in full_matrix.columns
                    if c not in ("home_win", "winning_team", "losing_team")]
    pd.testing.assert_frame_equal(
        test_game[feature_cols].to_frame().T.reset_index(drop=True),
        matching_row[feature_cols].reset_index(drop=True),
        check_dtype=False,
    )
```

### Rate-Limited Per-Game Ingestion
```python
import time
import logging

logger = logging.getLogger(__name__)

RATE_LIMIT_DELAY = 2.0  # seconds between Baseball Reference requests

def fetch_all_team_game_logs(seasons: list[int], teams: list[str]) -> None:
    """Fetch and cache per-game batting logs for all team-seasons.

    300 calls (30 teams x 10 seasons) at 2-second intervals = ~10 minutes.
    Cached calls skip the delay (instant return from Parquet).
    """
    total = len(seasons) * len(teams)
    fetched = 0
    for season in seasons:
        for team in teams:
            key = f"team_game_log_{season}_{team}"
            if is_cached(key):
                continue  # Already cached, no delay needed

            try:
                fetch_team_game_log(season, team)
                fetched += 1
                logger.info(f"Fetched {team} {season} ({fetched}/{total})")
                time.sleep(RATE_LIMIT_DELAY)
            except Exception as e:
                logger.error(f"Failed {team} {season}: {e}")
                time.sleep(RATE_LIMIT_DELAY * 2)  # Back off on error
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Exponent=2 for Pythagorean | Exponent=1.83 | ~2003 | More accurate expected win% by ~1 win/season |
| FIP only for pitcher quality | FIP + xFIP + SIERA ensemble | ~2010 | SIERA adds batted ball profile; better at identifying luck vs. skill |
| Raw stats as features | Differential features (home minus away) | Standard practice | Models learn relative strength, not absolute levels |
| Random train/test splits | Walk-forward temporal splits | Standard in time series | Prevents temporal leakage in evaluation |

**Deprecated/outdated:**
- Using exponent=2 for Pythagorean: Use 1.83 (Baseball-Reference standard)
- Season-level-only features: Per-game rolling features capture recent form, which season averages miss
- `pandas 3.0`: DO NOT upgrade. pybaseball incompatible with PyArrow string dtype defaults.

## Open Questions

1. **Baseball Reference team codes for `team_game_logs()`**
   - What we know: pybaseball's `utils.py` uses the same canonical codes as our project (WSN, KCR, TBR, etc.)
   - What's unclear: Whether all 30 teams x 10 seasons (2015-2024) return valid data via `team_game_logs()`. Some franchise relocations (OAK -> Athletics rebranding) may cause issues for 2025.
   - Recommendation: Test a few sample calls during implementation. The ingestion notebook should log and handle any failures gracefully.

2. **Exact columns returned by `team_game_logs()`**
   - What we know: Returns a DataFrame from Baseball Reference team game log page. Columns include Game, Home (boolean), OppStart, PitchersUsed, plus batting stats.
   - What's unclear: Whether OPS is a direct column or must be computed from OBP+SLG. Whether R (runs scored) and RA (runs allowed) are included.
   - Recommendation: Call `team_game_logs(2023, "NYY")` in the ingestion notebook and inspect `.columns`. Compute OPS from OBP+SLG if not directly available.

3. **Bullpen stats derivation approach**
   - What we know: No pre-aggregated bullpen stats in pybaseball. Can derive from `pitching_stats(season, qual=0)` by filtering to relievers (GS==0).
   - What's unclear: Whether filtering on GS==0 misses "openers" (relievers who start but pitch 1-2 innings). Edge case for 2018-2019 Tampa Bay.
   - Recommendation: Use GS < 3 as reliever threshold to catch openers. Aggregate team-level ERA and FIP.

4. **Park factor accuracy for historical seasons**
   - What we know: Park factors change slowly. A static 3-year average table works for most parks.
   - What's unclear: New parks (e.g., Texas Globe Life Field opened 2020) may need year-specific factors.
   - Recommendation: Use a single static table for v1. Document the approximation. Phase 3 can test sensitivity.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.1.1 |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `pytest tests/test_feature_builder.py tests/test_formulas.py tests/test_leakage.py -x -q` |
| Full suite command | `pytest -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FEAT-01 | SP differential computed correctly (FIP, xFIP, K%) | unit | `pytest tests/test_feature_builder.py::test_sp_differential -x` | -- Wave 0 |
| FEAT-02 | Team offensive differential (wOBA, OPS, Pythagorean) | unit | `pytest tests/test_feature_builder.py::test_offense_differential -x` | -- Wave 0 |
| FEAT-03 | Rolling 10-game OPS with shift(1) and season reset | unit | `pytest tests/test_feature_builder.py::test_rolling_ops -x` | -- Wave 0 |
| FEAT-04 | Bullpen ERA differential | unit | `pytest tests/test_feature_builder.py::test_bullpen_differential -x` | -- Wave 0 |
| FEAT-05 | Home/away indicator and park factor | unit | `pytest tests/test_feature_builder.py::test_park_features -x` | -- Wave 0 |
| FEAT-06 | Advanced features (SIERA, xwOBA, SP form, Log5, bullpen FIP) | unit | `pytest tests/test_feature_builder.py::test_advanced_features -x` | -- Wave 0 |
| FEAT-07 | Temporal safety: shift(1), no leakage | unit | `pytest tests/test_leakage.py -x` | -- Wave 0 |
| FEAT-08 | Single Parquet output, one row per game, all columns | integration | `pytest tests/test_feature_builder.py::test_output_schema -x` | -- Wave 0 |
| -- | Log5 formula correctness | unit | `pytest tests/test_formulas.py::test_log5 -x` | -- Wave 0 |
| -- | Pythagorean formula correctness | unit | `pytest tests/test_formulas.py::test_pythagorean -x` | -- Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_feature_builder.py tests/test_formulas.py tests/test_leakage.py -x -q`
- **Per wave merge:** `pytest -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_feature_builder.py` -- covers FEAT-01 through FEAT-06, FEAT-08
- [ ] `tests/test_formulas.py` -- covers Log5, Pythagorean formula correctness
- [ ] `tests/test_leakage.py` -- covers FEAT-07 temporal safety
- [ ] `src/features/__init__.py` -- module initialization
- [ ] `src/features/feature_builder.py` -- main FeatureBuilder class
- [ ] `src/features/formulas.py` -- sabermetric formulas
- [ ] `src/features/game_logs.py` -- per-game data loader with caching
- [ ] `data/features/` directory -- output location for feature matrix

## Sources

### Primary (HIGH confidence)
- pybaseball GitHub repository (https://github.com/jldbc/pybaseball) -- `team_game_logs.py` source code, `utils.py` team abbreviation mappings, `docs/team_game_logs.md`, `docs/pitching_stats_range.md`, `docs/fangraphs.md`
- Existing project codebase -- `src/data/cache.py`, `src/data/team_mappings.py`, `src/data/mlb_schedule.py`, `src/data/sp_stats.py`, `src/data/statcast.py`, `src/data/kalshi.py`, all Phase 1 tests
- pybaseball installed version: 2.2.7 (verified via pip show)
- pandas installed version: 2.2.3 (verified via pip show)

### Secondary (MEDIUM confidence)
- Log5 formula: Wikipedia (https://en.wikipedia.org/wiki/Log5), SABR (https://sabr.org/journal/article/matchup-probabilities-in-major-league-baseball/)
- Pythagorean formula: MLB.com Glossary (https://www.mlb.com/glossary/advanced-stats/pythagorean-winning-percentage), Baseball-Reference (https://www.baseball-reference.com/bullpen/Pythagorean_Theorem_of_Baseball)
- Park factors: FanGraphs Sabermetrics Library (https://library.fangraphs.com/principles/park-factors/), confirmed 1.83 exponent as Baseball-Reference standard
- Temporal safety / rolling features: Multiple sources on look-ahead bias (https://medium.com/@kyle-t-jones/data-leakage-lookahead-bias-and-causality-in-time-series-analytics-76e271ba2f6b)

### Tertiary (LOW confidence)
- Exact Baseball Reference team game log columns -- could not access BR directly (403). Column list should be verified at implementation time by calling `team_game_logs()` and inspecting output.
- Park factor exact values -- FanGraphs Guts page blocked (403). Values in static table are approximate and should be verified at implementation time.
- pybaseball Issue #409 confirms no built-in park_factors function (https://github.com/jldbc/pybaseball/issues/409)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all packages already installed and verified; no new dependencies needed
- Architecture: HIGH -- follows established Phase 1 patterns (cache infrastructure, team normalization, module layout); FeatureBuilder class design is standard
- Pitfalls: HIGH -- rate limiting, temporal leakage, team code mismatches are well-documented risks with clear mitigations
- Formulas: HIGH -- Log5 and Pythagorean are standard sabermetric formulas with extensive documentation
- Per-game data columns: MEDIUM -- pybaseball `team_game_logs()` output not fully verified; need runtime inspection
- Park factors: MEDIUM -- exact values need verification; approach (static table) is sound

**Research date:** 2026-03-28
**Valid until:** 2026-04-28 (stable domain; pybaseball and pandas versions pinned)
