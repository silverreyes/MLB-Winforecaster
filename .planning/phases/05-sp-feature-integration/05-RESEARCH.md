# Phase 5: SP Feature Integration - Research

**Researched:** 2026-03-29
**Domain:** Pandas feature engineering, MLB Stats API game logs, FanGraphs data, ID-based pitcher matching
**Confidence:** HIGH

## Summary

Phase 5 fixes two confirmed v1 bugs (xwOBA column name and name format), converts season-aggregate SP stats to temporally-safe season-to-date rolling features, adds new SP differential features (K-BB%, WHIP, ERA, recent FIP, pitch count, days rest), builds an ID-based pitcher cross-reference, and outputs `feature_store_v2.parquet`. All research questions from the pre-flight have been resolved through direct inspection of cached data, API response structures, and pybaseball source code.

The single most critical finding is that the MLB Stats API `gameLog` endpoint already returns `strikeOuts`, `baseOnBalls`, `homeRuns`, and `numberOfPitches` per game -- the existing `_fetch_pitcher_game_log()` in `sp_recent_form.py` simply discards these fields, extracting only `date`, `innings_pitched`, and `earned_runs`. Extending the game log extraction to include these four additional fields unlocks both SP-07 (30-day rolling FIP) and SP-08 (pitch count) with no new API calls required for cached pitchers. New game logs fetched going forward will include these fields; existing cached logs will need a one-time re-fetch.

The second critical finding is that the ID-based matching strategy (SP-02) should use a two-tier approach: (1) Chadwick Bureau register (via pybaseball) mapping `key_mlbam` to `key_fangraphs` as the primary bridge, then (2) accent-normalized name matching as the fallback. Direct testing shows Chadwick alone matches 83.2% of schedule SPs (missing recent call-ups), while accent-stripped name matching alone matches 99.5%. The two-tier approach covers both accurately and handles edge cases (name collisions, retired players with stale Chadwick entries). The existing v1 name-string matching fails on accented characters (Carlos Rodon vs Carlos Rodon, Jose Berrios vs Jose Berrios) which accounts for most of the ~17% NaN rate.

**Primary recommendation:** Extend `_fetch_pitcher_game_log()` to extract all stat fields from the already-rich API response, re-fetch existing cached logs, build a two-tier ID bridge (Chadwick + accent-normalization), then implement season-to-date rolling features using the established `shift(1)` pattern from `_add_rolling_features()`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **SP Stats Primary Source:** FanGraphs via pybaseball (confirmed working, 393 columns including ERA, FIP, xFIP, K/BB, WHIP, K%, BB%, SIERA)
- **Pitcher Game Log Cache:** Only 3 columns (date, innings_pitched, earned_runs); numberOfPitches, strikeouts, baseOnBalls, homeRunsAllowed NOT present in existing cache
- **ID-Based SP Name Matching:** Use mlb_player_id -> fangraphs_id cross-reference; eliminates ~17% NaN rate from name format mismatches
- **Temporal Safety Pattern:** cumsum + shift(1) per pitcher per season; no season-aggregate lookups for in-season features
- **Version Isolation:** feature_store_v2.parquet is new file; v1 preserved unchanged
- **Feature Set Constants:** TEAM_ONLY_FEATURE_COLS, SP_ENHANCED_FEATURE_COLS, V1_FULL_FEATURE_COLS must be exported from feature_sets.py
- **pandas 2.2.x pin:** No pandas 3.0 patterns

### Claude's Discretion
- Exact pandas groupby/cumsum/shift implementation (follow v1 rolling_ops pattern)
- Whether to add SP data as new columns to existing feature store or rebuild from scratch
- Test structure (follow v1 test patterns in tests/)
- Whether to add a data re-fetch script for richer game log hydration or inline it into the existing SP loader

### Deferred Ideas (OUT OF SCOPE)
- Home/away SP splits per pitcher (deferred to v3 -- sample size insufficient)
- xERA from Statcast (deferred -- redundant with xwOBA)
- Weather features, Elo ratings, bullpen fatigue (v3)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SP-01 | Fix two bugs in _add_advanced_features(): (1) statcast name column is 'last_name, first_name' as single merged column, (2) xwOBA column is 'est_woba' not 'xwoba' | VERIFIED: statcast_pitcher_2024.parquet confirms columns are `'last_name, first_name'` (single column) and `'est_woba'`. Current code at line 440 checks for separate `last_name`/`first_name` columns which do not exist. See Code Examples section for exact fix. |
| SP-02 | Build mlb_player_id -> fangraphs_id cross-reference for ID-based SP name matching | VERIFIED: Chadwick Register via `pybaseball.playerid_lookup.chadwick_register()` returns `key_mlbam` and `key_fangraphs`. Coverage: 83.2% of schedule SPs via ID bridge; 99.5% with accent-strip fallback. Two-tier approach recommended. |
| SP-03 | Convert season-aggregate SP stats to season-to-date rolling (cumsum + shift(1)) | Pattern confirmed from `_add_rolling_features()` and `_compute_cumulative_win_pct()`. Requires game-level stats from either extended game logs or season-aggregate decomposition. |
| SP-04 | Compute sp_k_bb_pct_diff; remove sp_k_pct_diff | VERIFIED: FanGraphs pitching_stats has `'K-BB%'` as a pre-computed column (value: 0.265 for Chris Sale 2024). Also computable from `K%` - `BB%`. |
| SP-05 | Compute sp_whip_diff | VERIFIED: FanGraphs pitching_stats has `'WHIP'` column (value: 1.01 for Chris Sale 2024). |
| SP-06 | Compute sp_era_diff (season-to-date ERA from per-game rolling) | Requires per-game ER and IP from extended game logs; cumsum(ER)*9/cumsum(IP) with shift(1). |
| SP-07 | Compute sp_recent_fip_diff (30-day rolling FIP from game logs) | RESOLVED: MLB Stats API gameLog DOES return `strikeOuts`, `baseOnBalls`, `homeRuns`, `numberOfPitches` per game. Extending the existing parser to extract these fields enables FIP computation. No new API endpoint needed. |
| SP-08 | Compute sp_pitch_count_last_diff and sp_days_rest_diff | RESOLVED: `numberOfPitches` IS in the MLB Stats API gameLog response (verified: 62 for Gerrit Cole's first 2024 start). Existing cache must be re-fetched to include this field. |
| SP-09 | Define TEAM_ONLY_FEATURE_COLS, SP_ENHANCED_FEATURE_COLS, V1_FULL_FEATURE_COLS in feature_sets.py | Current file at `src/models/feature_sets.py` has FULL_FEATURE_COLS (14 cols) and CORE_FEATURE_COLS. Must add three new constants. |
| SP-10 | SP cold-start: previous-season aggregate as prior; league-average for rookies | FanGraphs season-level data provides previous-season fallback. League-average constants computed from per-season aggregates. |
| SP-11 | Save as feature_store_v2.parquet, preserve v1 unchanged | Standard file I/O; feature store built by FeatureBuilder.build() pipeline. |
| SP-12 | Temporal safety tests for all new SP columns | Existing test_leakage.py pattern (shift(1) verification, season boundary reset, NaN for early games) must be extended to new SP columns. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pandas | 2.2.3 (pinned) | All feature computation, groupby/cumsum/shift | Project-wide pin; pybaseball incompatible with 3.0 |
| pybaseball | 2.2.7 | FanGraphs pitching_stats, Chadwick register, Statcast expected stats | Already used in v1; chadwick_register() provides ID bridge |
| MLB-StatsAPI (statsapi) | 1.9.0 | Pitcher game logs, pitcher ID maps, schedules | Already used in v1; official MLB API |
| numpy | 2.2.x | NaN handling, numeric operations | Required by pandas |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| unicodedata (stdlib) | built-in | Accent/diacritic stripping for name normalization | Fallback name matching when Chadwick ID bridge fails |
| pytest | installed | Unit and integration testing | All new feature tests |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Chadwick Register ID bridge | Accent-strip name matching only | Simpler but fails on name collisions (two "Luis Ortiz" in MLB API); ID bridge is more robust |
| FanGraphs pitching_stats for game-level data | MLB Stats API gameLog | FanGraphs only returns season aggregates; game-level data MUST come from MLB Stats API |
| Re-computing K-BB% from K% - BB% | Using FanGraphs pre-computed K-BB% column | Both are equivalent; pre-computed column is cleaner but manual computation works for rolling |

## Architecture Patterns

### Recommended Project Structure Changes
```
src/
  data/
    sp_stats.py             # Existing FanGraphs loader (unchanged)
    sp_id_bridge.py         # NEW: Chadwick + accent-strip ID cross-reference
    cache.py                # Existing cache infra (unchanged)
    statcast.py             # Existing statcast loader (unchanged)
    team_mappings.py        # Existing (unchanged)
  features/
    feature_builder.py      # MODIFIED: extended _add_sp_features(), fixed _add_advanced_features()
    feature_sets.py         # MOVED from src/models/ or NEW: three named feature set constants
    sp_recent_form.py       # MODIFIED: extended to extract K/BB/HR/numberOfPitches from game logs
    game_logs.py            # Existing team game logs (unchanged)
    formulas.py             # Existing (add FIP formula)
  models/
    feature_sets.py         # EXISTING location - update in place
tests/
  test_feature_builder.py   # EXTENDED: new SP feature tests
  test_leakage.py           # EXTENDED: temporal safety for new SP columns
  test_sp_id_bridge.py      # NEW: ID bridge unit tests
  test_sp_recent_form.py    # NEW: extended game log extraction tests
```

### Pattern 1: Season-to-Date Rolling with shift(1)
**What:** For each pitcher-season, compute cumulative stats game-by-game, then shift(1) so each game row sees only prior-game stats.
**When to use:** All season-to-date SP features (ERA, K-BB%, WHIP, SIERA, FIP, xFIP).
**Example:**
```python
# Source: existing _add_rolling_features() pattern in feature_builder.py line 328-333
# Applied to pitcher stats instead of team OPS

# Per-game log sorted by date within pitcher-season
logs = logs.sort_values(["pitcher_id", "season", "date"])

# Cumulative sums for ERA computation
logs["cum_er"] = logs.groupby(["pitcher_id", "season"])["earned_runs"].cumsum()
logs["cum_ip"] = logs.groupby(["pitcher_id", "season"])["innings_pitched"].cumsum()

# shift(1) so game N sees only stats through game N-1
logs["prev_cum_er"] = logs.groupby(["pitcher_id", "season"])["cum_er"].shift(1)
logs["prev_cum_ip"] = logs.groupby(["pitcher_id", "season"])["cum_ip"].shift(1)

# Season-to-date ERA as of each game (excluding that game)
logs["std_era"] = (logs["prev_cum_er"] * 9) / logs["prev_cum_ip"]
```

### Pattern 2: 30-Day Rolling Window with shift(1)
**What:** For each game date, slice the pitcher's log to the 30-day window [date-31, date-1] and aggregate.
**When to use:** sp_recent_fip_diff (SP-07), sp_recent_era_diff (existing).
**Example:**
```python
# Source: existing sp_recent_form.py lines 199-215
# Extended to include FIP computation

window = log[(log["date"] >= window_start) & (log["date"] < date_dt)]
if window.empty:
    continue
total_ip = window["innings_pitched"].sum()
total_k = window["strikeouts"].sum()
total_bb = window["base_on_balls"].sum()
total_hr = window["home_runs"].sum()
if total_ip > 0:
    # Raw FIP without constant (constant cancels in differential)
    fip = ((13 * total_hr) + (3 * total_bb) - (2 * total_k)) / total_ip
```

### Pattern 3: Two-Tier ID Bridge
**What:** Build a cross-reference mapping MLB Stats API player_id to FanGraphs IDfg using Chadwick Register as primary source and accent-normalized name matching as fallback.
**When to use:** All SP name matching between schedule data (MLB Stats API names) and FanGraphs season stats.
**Example:**
```python
import unicodedata
from pybaseball.playerid_lookup import chadwick_register

def build_sp_id_bridge(season: int) -> dict[int, int]:
    """Return {mlb_player_id: fangraphs_id} for all pitchers."""
    # Tier 1: Chadwick Register
    table = chadwick_register()
    valid = table[(table["key_mlbam"] != -1) & (table["key_fangraphs"] != -1)]
    bridge = dict(zip(valid["key_mlbam"].astype(int), valid["key_fangraphs"].astype(int)))
    return bridge

def strip_accents(s: str) -> str:
    """Remove diacritical marks for name normalization fallback."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", s)
        if not unicodedata.combining(c)
    )
```

### Pattern 4: Differential Feature Computation
**What:** All new SP features are home_value - away_value differentials matching v1 convention.
**When to use:** Every new SP feature column.
**Example:**
```python
# Existing pattern from _add_sp_features() line 165-168
df["sp_k_bb_pct_diff"] = df["home_sp_k_bb_pct"] - df["away_sp_k_bb_pct"]
df["sp_whip_diff"] = df["home_sp_whip"] - df["away_sp_whip"]
df["sp_era_diff"] = df["home_sp_era"] - df["away_sp_era"]
# Drop intermediate columns after computing differentials
```

### Anti-Patterns to Avoid
- **Season-aggregate lookup for in-season features:** v1 uses `sp_lookup[(season, name)]` which gives each game the full-season stat. This causes temporal leakage where a June game sees September stats. Always use per-game rolling with shift(1).
- **Name-string matching without normalization:** Direct string comparison fails on accented characters. Always normalize (accent-strip) or use ID bridge.
- **Computing xwOBA from a column named 'xwoba':** The Statcast expected stats CSV uses `'est_woba'` for xwOBA. The column `'xwoba'` does not exist in the data.
- **Checking for separate 'last_name' and 'first_name' columns:** Baseball Savant returns a single merged column `'last_name, first_name'` (the comma-space is part of the column name). Do not check for separate columns.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MLB player ID to FanGraphs ID mapping | Hand-built CSV or manual scraping | `pybaseball.playerid_lookup.chadwick_register()` | Maintained by Chadwick Bureau; 20,727 valid entries; covers 2015-2024 |
| Pitcher game log stats | Custom MLB API wrapper | Existing `sp_recent_form._fetch_pitcher_game_log()` (extended) | Already handles caching, rate limiting, IP string parsing |
| FIP computation constant (cFIP) | Scrape FanGraphs leaderboards per year | Omit cFIP entirely | Since we compute differentials (home - away), the constant cancels out |
| Accent/diacritic removal | Custom regex for each character | `unicodedata.normalize('NFKD', s)` + `combining()` filter | Standard library; handles all Unicode diacritical marks |
| Season-to-date cumulative stats | Custom loop with manual accumulation | `pandas.DataFrame.groupby().cumsum()` + `shift(1)` | Vectorized, tested pattern already in v1 codebase |

**Key insight:** The MLB Stats API already returns rich per-game pitcher statistics (60+ fields including K, BB, HR, numberOfPitches per game). The v1 code threw away all but 3 fields. Extending the parser is a small code change, not a new data source.

## Common Pitfalls

### Pitfall 1: Temporal Leakage in Season-Aggregate SP Stats
**What goes wrong:** v1 `_add_sp_features()` builds a lookup `{(season, pitcher_name): stats}` from FanGraphs season totals. A game on June 15 sees stats that include starts from July through September.
**Why it happens:** FanGraphs `pitching_stats(season)` returns end-of-season aggregates. The lookup key is (season, name) with no date dimension.
**How to avoid:** Use per-game stats from MLB Stats API game logs. Compute cumsum + shift(1) per pitcher per season. For season-to-date metrics (ERA, K-BB%, WHIP), accumulate from game-1 through game-N-1.
**Warning signs:** A pitcher's season-to-date ERA is identical across all their starts within a season (constant value = season aggregate, not rolling).

### Pitfall 2: xwOBA Bug -- Two Separate Issues
**What goes wrong:** `xwoba_diff` is 100% NaN in v1. Two bugs compound:
1. Code checks for `"last_name" in sc_df.columns and "first_name" in sc_df.columns` (line 440) but the actual column is a single merged column named `'last_name, first_name'` (verified in statcast_pitcher_2024.parquet).
2. Code reads `row["xwoba"]` (line 447) but the actual column is `'est_woba'` (verified in statcast_pitcher_2024.parquet).
**Why it happens:** The Baseball Savant CSV format changed (or was always different from what the code assumed). The column `'last_name, first_name'` looks like two columns but is one.
**How to avoid:** Use the verified column names: `df['last_name, first_name']` and `df['est_woba']`. Split the merged name column on `", "` and reverse to get "First Last" format.
**Warning signs:** 100% NaN rate on xwoba_diff.

### Pitfall 3: Chadwick Register Missing Recent Players
**What goes wrong:** The Chadwick Bureau register CSV (via pybaseball's `chadwick_register()`) does not include many 2023-2024 MLB debuts like Paul Skenes, Spencer Arrighetti, Mitchell Parker.
**Why it happens:** The register is community-maintained and updated periodically. New debuts take time to appear.
**How to avoid:** Use the two-tier approach: Chadwick ID bridge first, accent-normalized name matching as fallback. Never rely solely on the Chadwick register for recent players.
**Warning signs:** `key_fangraphs == -1` for recent call-ups; 83.2% match rate vs 99.5% with fallback.

### Pitfall 4: Cached Game Logs Missing Fields After Extension
**What goes wrong:** Existing ~3,795 cached pitcher game log files have only 3 columns (date, innings_pitched, earned_runs). After extending the parser to extract more fields, cached data still has only 3 columns because the cache returns stale data.
**Why it happens:** The cache check (`is_cached(key)`) returns True for existing files, so the extended parser never runs for already-cached pitchers.
**How to avoid:** Either (a) delete all existing `pitcher_game_log_*.parquet` files and re-fetch, or (b) add a cache version suffix to the key (e.g., `pitcher_game_log_v2_{season}_{player_id}`), or (c) check column count on read and re-fetch if missing columns.
**Warning signs:** New fields (strikeouts, base_on_balls, home_runs, number_of_pitches) are NaN or missing after code update but before re-fetch.

### Pitfall 5: FIP Constant Cancellation Assumption
**What goes wrong:** Attempting to compute exact FIP with the year-specific FIP constant (cFIP) adds complexity and fragility.
**Why it happens:** FIP = ((13*HR) + (3*(BB+HBP)) - (2*K)) / IP + cFIP, where cFIP varies by year.
**How to avoid:** Since all features are differentials (home_sp - away_sp), cFIP cancels out in subtraction. Compute raw FIP without cFIP: `raw_fip = ((13*HR) + (3*BB) - (2*K)) / IP`. The differential `raw_fip_home - raw_fip_away` equals `fip_home - fip_away` exactly.
**Warning signs:** Unnecessarily scraping FanGraphs for annual FIP constants.

### Pitfall 6: Cold-Start Division by Zero
**What goes wrong:** Season-to-date ERA = (cumsum(ER) * 9) / cumsum(IP). If IP = 0 (first start of season, before shift(1) provides data), this divides by zero.
**Why it happens:** shift(1) on the first game of a season returns NaN for the "previous" value. cumsum starts at 0 before any games.
**How to avoid:** After shift(1), the first game of each season naturally becomes NaN. This is correct behavior -- use previous-season aggregate stats (from FanGraphs season data) as the cold-start fallback. For rookies with no prior season, use league-average values.
**Warning signs:** Inf or -Inf values in ERA/FIP columns; all NaN for first game of season without fallback.

### Pitfall 7: Accent Character Name Matching for Schedule -> FanGraphs Join
**What goes wrong:** MLB Stats API uses accented names (Jose Berrios, Carlos Rodon, Pablo Lopez) while FanGraphs uses ASCII-only names (Jose Berrios, Carlos Rodon, Pablo Lopez). Direct string comparison fails.
**Why it happens:** FanGraphs strips diacritical marks; MLB Stats API preserves them.
**How to avoid:** Apply `unicodedata.normalize('NFKD', name)` + combining character removal before name comparison. Verified: this reduces mismatches from 27 FG names to 2 (only "Louie/Louis Varland" and "Luis L. Ortiz" remain).
**Warning signs:** NaN SP features for Latin American players with accented names.

## Code Examples

### Fix 1: xwOBA Bug in _add_advanced_features() (SP-01)
```python
# Source: direct inspection of statcast_pitcher_2024.parquet
# Current broken code (feature_builder.py lines 440-447):
#   if "last_name" in sc_df.columns and "first_name" in sc_df.columns:
#       ... row["xwoba"]  # Neither column exists

# Fixed code:
xwoba_lookup: dict[tuple[int, str], float] = {}
for season in self.seasons:
    try:
        sc_df = fetch_statcast_pitcher(season)
        # Baseball Savant column is 'last_name, first_name' (single merged column)
        # xwOBA column is 'est_woba' (not 'xwoba')
        name_col = "last_name, first_name"
        xwoba_col = "est_woba"
        if name_col in sc_df.columns and xwoba_col in sc_df.columns:
            for _, row in sc_df.iterrows():
                raw_name = str(row[name_col]).strip()
                # Format: "Webb, Logan" -> "Logan Webb"
                if ", " in raw_name:
                    parts = raw_name.split(", ", 1)
                    name = f"{parts[1]} {parts[0]}"
                else:
                    name = raw_name
                xwoba_val = row[xwoba_col]
                if pd.notna(xwoba_val):
                    xwoba_lookup[(season, name)] = xwoba_val
    except Exception as e:
        logger.debug(f"No Statcast data for season {season}: {e}")
```

### Fix 2: Extended Pitcher Game Log Extraction (SP-07, SP-08)
```python
# Source: MLB Stats API response for person/hydrate=stats(type=gameLog)
# Verified 2026-03-29: Gerrit Cole game log includes all needed fields

# Current code in sp_recent_form.py (line 122-127) extracts only 3 fields:
#   rows.append({
#       "date": ..., "innings_pitched": ..., "earned_runs": ...
#   })

# Extended extraction (same API response, no additional calls):
rows.append({
    "date": pd.to_datetime(s.get("date")),
    "innings_pitched": _parse_ip(stat.get("inningsPitched", "0.0")),
    "earned_runs": int(stat.get("earnedRuns", 0)),
    # New fields for SP-07 and SP-08:
    "strikeouts": int(stat.get("strikeOuts", 0)),
    "base_on_balls": int(stat.get("baseOnBalls", 0)),
    "home_runs": int(stat.get("homeRuns", 0)),
    "number_of_pitches": int(stat.get("numberOfPitches", 0)),
    "games_started": int(stat.get("gamesStarted", 0)),
})
```

### Example 3: Season-to-Date ERA with Cold Start (SP-03, SP-06, SP-10)
```python
# Pattern: cumsum + shift(1) per pitcher per season, with cold-start fallback

def _compute_std_era(logs: pd.DataFrame, prev_season_stats: dict) -> pd.DataFrame:
    """Compute season-to-date ERA with shift(1) temporal safety."""
    logs = logs.sort_values(["pitcher_id", "season", "date"])

    # Cumulative within pitcher-season
    logs["cum_er"] = logs.groupby(["pitcher_id", "season"])["earned_runs"].cumsum()
    logs["cum_ip"] = logs.groupby(["pitcher_id", "season"])["innings_pitched"].cumsum()

    # shift(1): each game sees only prior-game totals
    logs["prev_er"] = logs.groupby(["pitcher_id", "season"])["cum_er"].shift(1)
    logs["prev_ip"] = logs.groupby(["pitcher_id", "season"])["cum_ip"].shift(1)

    # ERA = (ER * 9) / IP; NaN where IP == 0 or first game of season
    logs["std_era"] = np.where(
        logs["prev_ip"] > 0,
        (logs["prev_er"] * 9) / logs["prev_ip"],
        np.nan,
    )

    # Cold start: fill first-game NaN with previous-season aggregate
    # prev_season_stats = {pitcher_id: {"ERA": 3.50, ...}}
    mask = logs["std_era"].isna()
    for idx in logs[mask].index:
        pid = logs.loc[idx, "pitcher_id"]
        prev = prev_season_stats.get(pid, {})
        logs.loc[idx, "std_era"] = prev.get("ERA", LEAGUE_AVG_ERA)

    return logs
```

### Example 4: Raw FIP Differential (SP-07)
```python
# FIP without constant (cancels in differential)
# Formula: ((13 * HR) + (3 * BB) - (2 * K)) / IP

def compute_raw_fip(k: float, bb: float, hr: float, ip: float) -> float:
    """Compute raw FIP (without cFIP constant).

    cFIP cancels out in home-away differentials, so raw FIP is sufficient.
    """
    if ip <= 0:
        return np.nan
    return ((13 * hr) + (3 * bb) - (2 * k)) / ip
```

### Example 5: ID Bridge Construction (SP-02)
```python
# Two-tier approach: Chadwick ID -> accent-strip fallback
import unicodedata
from pybaseball.playerid_lookup import chadwick_register

def build_mlb_to_fg_bridge() -> tuple[dict[int, int], dict[str, str]]:
    """Build MLB player ID -> FanGraphs ID bridge.

    Returns:
        (id_bridge, name_bridge):
        id_bridge: {mlb_player_id: fangraphs_id}
        name_bridge: {normalized_name: fg_name} for fallback
    """
    # Tier 1: Chadwick Register
    table = chadwick_register()
    valid = table[(table["key_mlbam"] != -1) & (table["key_fangraphs"] != -1)]
    id_bridge = dict(zip(
        valid["key_mlbam"].astype(int),
        valid["key_fangraphs"].astype(int),
    ))

    # Tier 2: Accent-normalized name bridge (built from FanGraphs data)
    # This catches the ~17% that Chadwick misses (recent call-ups)
    name_bridge = {}  # populated during feature computation from FG data

    return id_bridge, name_bridge

def strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", s)
        if not unicodedata.combining(c)
    )
```

## State of the Art

| Old Approach (v1) | Current Approach (v2) | When Changed | Impact |
|--------------------|-----------------------|--------------|--------|
| Season-aggregate SP stats from FanGraphs | Season-to-date rolling from MLB Stats API game logs | Phase 5 | Eliminates temporal leakage; June game no longer sees September stats |
| Name-string matching (17% NaN) | ID-based bridge + accent-normalized fallback (0.5% NaN) | Phase 5 | Reduces SP feature NaN rate from ~17% to ~0.5% |
| `row["xwoba"]` column access | `row["est_woba"]` column access | Phase 5 | Fixes 100% NaN rate on xwoba_diff |
| 3-column game log cache | 8-column game log cache | Phase 5 | Enables FIP, pitch count, and days rest features |
| `sp_fip_diff` + `sp_xfip_diff` + `sp_k_pct_diff` | `sp_siera_diff` + `sp_k_bb_pct_diff` (drop redundant FIP/xFIP/K%) | Phase 5 | K-BB% explains 17.92% of future RA9 variance vs <10% for K% alone; SIERA dominates FIP/xFIP |

**Deprecated/outdated:**
- `sp_fip_diff`: Removed -- redundant with SIERA (RMSE 0.964 vs FIP 1.010)
- `sp_xfip_diff`: Removed -- nearly identical to SIERA for prediction
- `sp_k_pct_diff`: Removed -- replaced by sp_k_bb_pct_diff (strictly more informative)

## Open Questions

1. **Game Log Re-fetch Strategy**
   - What we know: ~3,795 cached pitcher game logs have only 3 columns. The extended parser needs 8 columns.
   - What's unclear: Whether to delete all cached files and re-fetch (clean but slow, ~19 minutes at 0.3s/call), or use a versioned cache key.
   - Recommendation: Use a versioned cache key (`pitcher_game_log_v2_{season}_{player_id}`) so old cache remains as a reference. Re-fetch all pitcher-seasons with a batch script. The re-fetch only needs to happen once. Alternatively, provide a `--force-refetch` flag on the game log loader.

2. **feature_sets.py Location**
   - What we know: Currently at `src/models/feature_sets.py`. Phase 5 context says it should be at `src/features/feature_sets.py`.
   - What's unclear: Whether to move the file or update in place.
   - Recommendation: Update in place at `src/models/feature_sets.py` to avoid breaking imports across the codebase. Moving is optional cleanup.

3. **Columns to Drop from v2 Feature Set**
   - What we know: Research recommends dropping `sp_fip_diff`, `sp_xfip_diff`, `sp_k_pct_diff` (redundant).
   - What's unclear: Whether to drop them in Phase 5 (feature engineering) or Phase 6 (model retrain after VIF/SHAP analysis).
   - Recommendation: Keep all columns in `feature_store_v2.parquet`. Define `SP_ENHANCED_FEATURE_COLS` without the redundant columns. The VIF/SHAP analysis in Phase 6 provides the final empirical validation for dropping.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (installed, working) |
| Config file | None (uses defaults; pytest.ini could be added in Wave 0) |
| Quick run command | `python -m pytest tests/test_feature_builder.py tests/test_leakage.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SP-01 | xwOBA fix: est_woba column, name split/reverse | unit | `python -m pytest tests/test_feature_builder.py::test_xwoba_fix -x` | No -- Wave 0 |
| SP-02 | ID bridge matches schedule SPs to FG stats | unit | `python -m pytest tests/test_sp_id_bridge.py -x` | No -- Wave 0 |
| SP-03 | Season-to-date rolling eliminates leakage | integration | `python -m pytest tests/test_leakage.py::test_sp_std_no_leakage -x` | No -- Wave 0 |
| SP-04 | sp_k_bb_pct_diff computed, sp_k_pct_diff removed | unit | `python -m pytest tests/test_feature_builder.py::test_k_bb_pct_diff -x` | No -- Wave 0 |
| SP-05 | sp_whip_diff computed | unit | `python -m pytest tests/test_feature_builder.py::test_whip_diff -x` | No -- Wave 0 |
| SP-06 | sp_era_diff from season-to-date rolling | unit | `python -m pytest tests/test_feature_builder.py::test_era_diff -x` | No -- Wave 0 |
| SP-07 | sp_recent_fip_diff from 30-day game logs | unit | `python -m pytest tests/test_feature_builder.py::test_recent_fip_diff -x` | No -- Wave 0 |
| SP-08 | sp_pitch_count_last_diff, sp_days_rest_diff | unit | `python -m pytest tests/test_feature_builder.py::test_pitch_count_days_rest -x` | No -- Wave 0 |
| SP-09 | Three named feature set constants | unit | `python -m pytest tests/test_feature_builder.py::test_feature_set_constants -x` | No -- Wave 0 |
| SP-10 | Cold-start: prev season fallback, rookie league avg | unit | `python -m pytest tests/test_feature_builder.py::test_cold_start -x` | No -- Wave 0 |
| SP-11 | feature_store_v2.parquet saved correctly | integration | `python -m pytest tests/test_feature_builder.py::test_v2_parquet_output -x` | No -- Wave 0 |
| SP-12 | Temporal safety: new SP columns change game-to-game | integration | `python -m pytest tests/test_leakage.py::test_sp_temporal_safety -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_feature_builder.py tests/test_leakage.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_sp_id_bridge.py` -- covers SP-02 (ID bridge unit tests)
- [ ] New test functions in `tests/test_feature_builder.py` -- covers SP-01, SP-04 through SP-11
- [ ] New test functions in `tests/test_leakage.py` -- covers SP-03, SP-12
- [ ] `tests/test_sp_recent_form.py` -- covers extended game log extraction (K/BB/HR/pitches)

## Verified Data Structures

### Statcast Pitcher Expected Stats (statcast_pitcher_2024.parquet)
**Verified 2026-03-29 from cached file**
- Shape: 855 rows x 20 columns
- Name column: `'last_name, first_name'` (single merged column, e.g., "Webb, Logan")
- xwOBA column: `'est_woba'` (NOT 'xwoba')
- Player ID column: `'player_id'` (numeric, likely MLB Stats API ID)
- Other relevant: `'woba'`, `'est_ba'`, `'est_slg'`, `'xera'`

### FanGraphs Pitching Stats (sp_stats_2024_mings1.parquet)
**Verified 2026-03-29 from cached file**
- Shape: 370 rows x 396 columns
- Player ID column: `'IDfg'` (FanGraphs integer ID, e.g., 10603 for Chris Sale)
- Player name column: `'Name'` (e.g., "Chris Sale" -- ASCII, no accents)
- Key stat columns: `'ERA'`, `'FIP'`, `'xFIP'`, `'SIERA'`, `'WHIP'`, `'K%'`, `'BB%'`, `'K-BB%'`
- K-BB% is pre-computed: value 0.265 for Chris Sale 2024
- Team column: `'Team'` (FanGraphs abbreviations)

### MLB Stats API Pitcher Game Log (per game)
**Verified 2026-03-29 via live API call (Gerrit Cole, 2024)**
- Available stat fields per game (60+ total), including:
  - `strikeOuts`: integer (e.g., 5)
  - `baseOnBalls`: integer (e.g., 1)
  - `homeRuns`: integer (e.g., 0)
  - `numberOfPitches`: integer (e.g., 62)
  - `earnedRuns`: integer (e.g., 2)
  - `inningsPitched`: string (e.g., "4.0" where .Y is outs not tenths)
  - `gamesStarted`: integer (1 for starts)
  - `hits`, `atBats`, `battersFaced`, `whip`, `era`, etc.

### MLB Stats API Pitcher ID Map (pitcher_id_map_2024.parquet)
**Verified 2026-03-29 from cached file**
- Shape: 802 rows x 2 columns (`name`, `player_id`)
- Name format: "First Last" with accented characters (e.g., "Jose Berrios", "Carlos Rodon")
- Player ID: MLB Stats API numeric ID (e.g., 543037 for Gerrit Cole)

### Chadwick Bureau Register (via pybaseball)
**Verified 2026-03-29 via live API call**
- Shape: 25,901 rows x 8 columns
- Columns: `name_last`, `name_first`, `key_mlbam`, `key_retro`, `key_bbref`, `key_fangraphs`, `mlb_played_first`, `mlb_played_last`
- Both IDs valid (not -1): 20,727 entries
- Players active 2015+: 4,019 entries, 3,561 with both IDs
- LIMITATION: Missing many 2023-2024 debuts (Paul Skenes, Spencer Arrighetti, etc.)

### Existing Pitcher Game Log Cache
**Verified 2026-03-29 from cached file**
- ~3,795 files in `data/raw/mlb_api/pitcher_game_log_{season}_{player_id}.parquet`
- Columns: `date`, `innings_pitched`, `earned_runs` (ONLY 3 columns)
- Must be re-fetched to include extended fields

## Name Matching Coverage Analysis

| Approach | Match Rate (2024 Schedule SPs) | Notes |
|----------|-------------------------------|-------|
| v1 name-string (no normalization) | ~83% | Fails on all accented Latin American names |
| Chadwick ID bridge only | 83.2% (307/369) | Missing recent call-ups (Paul Skenes, etc.) |
| Accent-stripped name match only | 99.5% (367/369) | Misses: "Louie/Louis Varland", "Luis L. Ortiz" |
| Two-tier: Chadwick ID + accent fallback | ~99.5% | Best coverage; ID bridge handles collisions |
| Two-tier + manual overrides (2 names) | 100% | Handle the 2 edge cases with a small lookup dict |

## Sources

### Primary (HIGH confidence)
- `data/raw/statcast/statcast_pitcher_2024.parquet` -- Direct file inspection confirmed `'last_name, first_name'` and `'est_woba'` column names
- `data/raw/pybaseball/sp_stats_2024_mings1.parquet` -- Direct file inspection confirmed 396 columns including `'IDfg'`, `'K-BB%'`, `'WHIP'`, `'SIERA'`
- `data/raw/mlb_api/pitcher_game_log_2015_112526.parquet` -- Direct file inspection confirmed 3-column structure
- MLB Stats API live response (Gerrit Cole 2024) -- Confirmed 60+ stat fields per game including strikeOuts, baseOnBalls, homeRuns, numberOfPitches
- `pybaseball.playerid_lookup` source code -- Confirmed Chadwick Register columns: key_mlbam, key_fangraphs
- Chadwick Register live load -- Confirmed 25,901 entries; 20,727 with both IDs; 3,561 for 2015+ players
- Existing codebase: `feature_builder.py`, `sp_recent_form.py`, `feature_sets.py`, `game_logs.py`, `statcast.py`

### Secondary (MEDIUM confidence)
- FanGraphs Sabermetrics Library (from milestone research) -- K-BB% explains 17.92% of future RA9 variance
- Pitcher List (from milestone research) -- SIERA RMSE 0.964 vs FIP 1.010 for year-to-year prediction

### Tertiary (LOW confidence)
- None. All critical findings verified through direct data inspection and live API calls.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in use in v1; versions pinned
- Architecture: HIGH -- patterns taken directly from existing v1 code (shift(1) on cumsum, differential computation)
- Data structures: HIGH -- all verified through direct file inspection and live API response
- ID matching: HIGH -- end-to-end coverage tested with actual 2024 data (99.5% match rate)
- Pitfalls: HIGH -- all identified from direct code inspection and data verification

**Research date:** 2026-03-29
**Valid until:** 2026-04-28 (30 days -- stable domain; data formats unlikely to change mid-season)
