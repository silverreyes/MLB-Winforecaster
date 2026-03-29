# Feature Landscape: v2.0 Starting Pitcher Features

**Domain:** MLB pre-game win probability modeling -- SP feature expansion
**Researched:** 2026-03-29
**Scope:** Which SP-level features add predictive signal beyond the existing v1.0 team-level feature matrix

## Context: What v1.0 Already Has

The existing feature matrix (14 columns) includes:
- `sp_fip_diff`, `sp_xfip_diff`, `sp_k_pct_diff`, `sp_siera_diff` -- season-aggregate FanGraphs stats
- `sp_recent_era_diff` -- 30-day rolling ERA via MLB Stats API game logs
- `team_woba_diff`, `team_ops_diff`, `pyth_win_pct_diff` -- team offense
- `rolling_ops_diff` -- 10-game rolling team OPS
- `bullpen_era_diff`, `bullpen_fip_diff` -- reliever aggregates
- `is_home`, `park_factor` -- game context
- `log5_home_wp` -- derived matchup probability
- `xwoba_diff` -- **broken** (100% NaN due to ADVF-07 bug)

This research answers: what SP features should be ADDED, MODIFIED, or FIXED in v2.0?

---

## Table Stakes SP Features (Well-Evidenced, Include)

Features with strong sabermetric evidence that the current model is either missing or computing suboptimally.

### 1. xwOBA Differential (ADVF-07 Fix)

| Attribute | Detail |
|-----------|--------|
| **Feature name** | `xwoba_diff` (already exists, currently 100% NaN) |
| **Evidence** | xwOBA removes defense and batted-ball luck from offensive evaluation. Based on exit velocity + launch angle. Available from Baseball Savant since 2015. |
| **Confidence** | HIGH -- column names verified against live Baseball Savant CSV endpoint |
| **Action** | FIX, not add. Two bugs in `_add_advanced_features()`: |

**Bug 1 -- Column name:** The pybaseball `statcast_pitcher_expected_stats()` function returns a CSV from Baseball Savant where the xwOBA column is named `est_woba`, NOT `xwoba` or `xwOBA`. The current code looks for `xwoba` in the row index and finds nothing.

**Bug 2 -- Name join:** The CSV returns a single column called `last_name, first_name` (the comma is literally part of the column name). The current code tries to join on separate `last_name` and `first_name` columns, constructs `"First Last"` format, but the source data has `"Last, First"` as one column.

**Correct join strategy:**
```python
# The column name is literally 'last_name, first_name' (a single string with comma)
# Example value: "Cole, Gerrit"
# Schedule uses "Gerrit Cole" format
# Convert: split on ", ", reverse, rejoin with space
sc_df["Name"] = sc_df["last_name, first_name"].apply(
    lambda x: " ".join(reversed(x.split(", "))) if isinstance(x, str) else ""
)
# Then look up est_woba (not xwoba)
xwoba_val = row["est_woba"]
```

**Caveat:** Baseball Prospectus research found that xwOBA for pitchers is "little better -- and in some cases worse -- at isolating pitcher skills than FIP and DRA." Tom Tango (MLB Senior Database Architect) stated expected stats were designed to be descriptive, not predictive. Still worth including because: (a) it captures a different signal (batted-ball quality) than FIP/xFIP (K/BB/HR), and (b) XGBoost can learn to weight it appropriately. But do not expect xwOBA_diff alone to be a top feature.

**Source:** Baseball Savant CSV endpoint verified 2026-03-29 -- columns confirmed as `last_name, first_name`, `est_woba`, `woba`, `est_ba`, `est_slg`, `xera`.

### 2. K-BB% Differential (New)

| Attribute | Detail |
|-----------|--------|
| **Feature name** | `sp_k_bb_pct_diff` |
| **pybaseball column** | Compute as `K%` minus `BB%` from `pitching_stats()` |
| **Evidence** | K-BB% explains 17.92% of variance in future RA9, beating K/BB ratio (<10%). FanGraphs community research identifies K-BB% as "the premier metric when predicting future success." Stabilizes faster than ERA-based metrics because K% (70 BF) and BB% (170 BF) both stabilize quickly. |
| **Confidence** | HIGH -- multiple FanGraphs community analyses, consistent finding |
| **Multicollinearity risk** | MODERATE with existing `sp_k_pct_diff`. K-BB% = K% - BB%, so it is a linear combination of two metrics we partially already have (K% is already included; BB% is not). Recommendation: **replace `sp_k_pct_diff` with `sp_k_bb_pct_diff`** to capture both K% and BB% signal in a single feature, reducing feature count. Alternatively, add BB% as a separate feature and keep K% separate. |
| **Recommendation** | Add `sp_k_bb_pct_diff`. Drop `sp_k_pct_diff` to avoid redundancy. K-BB% is strictly more informative than K% alone. |

### 3. SP WHIP Differential (New)

| Attribute | Detail |
|-----------|--------|
| **Feature name** | `sp_whip_diff` |
| **pybaseball column** | `WHIP` from `pitching_stats()` |
| **Evidence** | WHIP consistently identified as a top-tier predictor of run prevention in feature selection studies. Measures walks + hits per IP -- directly quantifies baserunner traffic allowed, which is the most important pitching consideration for preventing wins. |
| **Confidence** | HIGH -- FanGraphs Sabermetrics Library, multiple MLB prediction papers |
| **Multicollinearity risk** | MODERATE with `sp_fip_diff` and `bullpen_era_diff`. WHIP and FIP both measure run prevention but through different lenses: WHIP is outcomes-based (actual H + BB), FIP is component-based (K, BB, HR only). Correlation is typically r~0.65-0.75, enough overlap to flag but not redundant. |
| **Recommendation** | Include. VIF should be checked after adding -- if VIF > 5 with existing features, consider dropping in favor of FIP. |

### 4. Season-to-Date ERA Differential (New Separate Feature)

| Attribute | Detail |
|-----------|--------|
| **Feature name** | `sp_era_diff` |
| **pybaseball column** | `ERA` from `pitching_stats()` |
| **Evidence** | ERA is the universal pitcher quality signal. FIP has the strongest in-season correlation with ERA (r=0.84 in 2017, r=0.80 in 2018), but ERA itself captures elements FIP ignores: BABIP management, sequencing, situational pitching. Including both ERA and FIP lets the model learn which matters more per context. |
| **Confidence** | MEDIUM -- ERA is noisy (BABIP stabilizes at 2000 BIP), but XGBoost handles this well |
| **Multicollinearity risk** | HIGH with `sp_fip_diff` (r~0.80+). This is the classic ERA/FIP overlap problem. |
| **Recommendation** | Include alongside FIP but monitor VIF. Tree-based models (RF, XGBoost) handle correlated features better than logistic regression. For LR, may need to drop one. Consider ERA-minus-FIP as a derived feature instead (captures "luck/skill residual"). |

---

## Differentiators (Moderate Evidence, Include with Caveats)

Features with plausible signal but weaker evidence or higher engineering complexity.

### 5. SP Recent Form: Rolling Window Optimization

| Attribute | Detail |
|-----------|--------|
| **Feature name** | `sp_recent_era_diff` (exists), potentially add `sp_recent_fip_diff` |
| **Current implementation** | 30-day calendar window via MLB Stats API game logs. Computes ERA = (ER * 9) / IP for starts in [date-31, date-1] |
| **Evidence on window size** | |

**Season-to-date vs. rolling window:**
Rolling windows are preferred for within-season prediction because season-to-date averages are diluted by April performance when predicting September games. Research consensus is that recent stats are "more impactful than lifetime statistics." However, very short windows (last 1-2 starts) are extremely noisy.

**Optimal window -- evidence synthesis:**
- FiveThirtyEight uses a rolling game score (rGS) that gives more weight to recent starts but never fully discards older ones (exponential decay, not hard cutoff)
- Academic research uses 10-day trailing averages for team stats
- The existing v1 30-day window for SP ERA typically captures 4-5 starts (SPs pitch every 5 days), which is a reasonable sample
- K% stabilizes at ~70 BF (~2 starts), BB% at ~170 BF (~5 starts), ERA takes multiple seasons

**Recommendation for v2.0:**
- **Keep the 30-day calendar window (4-5 starts)** for ERA recent form. This is well-balanced: 2 starts is too noisy, full season is too diluted.
- **Add a parallel `sp_recent_fip_diff`** using the same 30-day window. FIP from recent starts uses only K/BB/HR from those starts and is more stable than ERA at small sample sizes. Requires computing FIP from game log components (K, BB, HR, IP), not just looking up a season aggregate.
- **Consider last-3-starts window as alternative** to calendar-based 30 days. Start-count windows normalize for schedule irregularities (rainouts, skipped starts). 3 starts = ~150-200 BF, approaching K% stability.

**Temporal safety:** The current implementation correctly uses `log["date"] < date_dt` (strictly before). This is safe. Any new rolling feature must follow the same pattern.

**Confidence:** MEDIUM -- window size optimization is not definitively settled in literature; 30 days is a reasonable default.

### 6. Pitches Thrown Last Start (Workload)

| Attribute | Detail |
|-----------|--------|
| **Feature name** | `sp_pitch_count_last_diff` |
| **Data source** | MLB Stats API game log includes `numberOfPitches` per game |
| **Evidence** | Published research (Journal of Strength & Conditioning, 2012) found each pitch thrown in the preceding game increases ERA by 0.007 in the next game. Cumulative pitching load (average pitches over last 5 and 10 games) has a larger effect than single-game count. Virtually linear negative relationship between past pitches and future performance. |
| **Confidence** | MEDIUM -- effect is real but small (~0.7 ERA points per 100 extra pitches). Signal-to-noise may be low for game-outcome prediction. |
| **Cold-start handling** | See section below. |
| **Recommendation** | Include as a differentiator. Compute as pitch count from the SP's most recent start (before the game being predicted). Use shift(1) on the pitcher's start log sorted by date. For the first start of the season, use NaN (impute with league-average ~93 pitches). |

### 7. Days Rest

| Attribute | Detail |
|-----------|--------|
| **Feature name** | `sp_days_rest_diff` |
| **Data source** | Computed from pitcher game log dates |
| **Evidence** | Research is mixed. FanGraphs community analysis found "no significant difference in starting a pitcher on short rest vs. normal rest vs. extended rest." However, a 2023 season study found optimal performance at 5 days rest (Modified FIP premium of 0.144 vs. 0.239 at 4 days and 0.291 at 6 days). The effect is small and may be confounded by pitcher quality (aces get normal rest, mop-up arms get extended rest). |
| **Confidence** | LOW -- conflicting evidence, small effect size |
| **Recommendation** | Include but cap at useful range. Encode as integer days since last start, capped at [3, 7]. Below 3 or above 7 is rare and noisy. Most starts are 4-5 days rest, so variance is low. This feature may not survive feature importance analysis but is cheap to compute. |
| **Cold-start:** First start of season: use NaN (impute with 5, the modal rest period). |

---

## Anti-Features (Noisy, Avoid)

Features that seem useful but add noise or create problems.

### Home/Away Splits for Individual SPs

| Attribute | Detail |
|-----------|--------|
| **Why tempting** | Some pitchers have dramatic home/road splits. Anecdotally, Coors Field inflates road ERA for all pitchers. |
| **Why avoid** | |

**Sample size analysis:**
- A typical SP makes 30-33 starts per season, split roughly 15-17 home and 15-16 away.
- That is ~400 BF home and ~400 BF away per season.
- K% stabilizes at 70 BF (adequate), BB% at 170 BF (adequate), but ERA-based splits need far more data.
- BABIP requires 2000 BIP to stabilize -- a single season of home/away starts provides ~200-250 BIP per split. BABIP is almost pure noise at this sample.
- FanGraphs Sabermetrics Library states: "Some splits are simply a product of random variation... if you carve performance up into [groups], you will find differences simply due to fluctuation."
- Career H/A splits accumulate more data (3-5 seasons = ~1200-2000 BF per split), but are contaminated by park changes (trades, free agency), aging effects, and era shifts.

**Conclusion:** Career H/A splits are too noisy at typical SP sample sizes for reliable per-pitcher feature engineering. The park factor feature already captures venue effects at the game level. Adding SP-level H/A splits would introduce noise without adding signal.

**Confidence:** HIGH -- FanGraphs stabilization data is authoritative, and the math on BF per split is straightforward.

**What to do instead:** The existing `park_factor` and `is_home` features already capture venue and home-field effects at the team level, which is where the signal actually lives.

### K/BB Ratio (vs. K-BB%)

| Attribute | Detail |
|-----------|--------|
| **Why avoid** | K/BB ratio uses K/BB as a ratio. When BB is small, K/BB becomes unstable (1 walk difference swings the ratio enormously). K-BB% uses a common denominator (PA), making it more stable and more predictive: K-BB% explains 17.92% of variance in future RA9 vs. <10% for K/BB. The article "Stop using K/BB!" (Beyond the Box Score) makes the definitive case. |
| **What to do instead** | Use K-BB% (`K%` minus `BB%`) as recommended above. |

### Individual Batter vs. Pitcher Matchups

| Attribute | Detail |
|-----------|--------|
| **Why avoid** | Confirmed anti-feature from v1.0 research. Most BvP pairs have 5-15 career PA. This is pure noise. Already listed in PROJECT.md Out of Scope. |

### Pitcher Win-Loss Record

| Attribute | Detail |
|-----------|--------|
| **Why avoid** | Pitcher W-L is heavily influenced by run support, bullpen performance, and sequencing. FIP/xFIP/SIERA capture pitcher skill; W-L adds no signal beyond what team W% already provides. |

### xERA from Statcast

| Attribute | Detail |
|-----------|--------|
| **Why avoid** | Available in the same Baseball Savant CSV as `est_woba` (column name: `xera`). However, Baseball Prospectus found expected Statcast metrics for pitchers are "little better -- and in some cases worse" than FIP for prediction. xERA's noise from quality-of-contact variability dwarfs the skill signal for most pitchers. Adding both xwOBA_diff and xERA_diff introduces redundancy (they measure the same batted-ball signal). |
| **What to do instead** | Include `est_woba` (xwOBA) as the single Statcast-derived SP metric. Do not add xERA on top. |

---

## Feature Engineering Patterns for Temporal Safety

### Pattern 1: Season-Aggregate Lookup (Current Pattern, Keep)

Used for: `sp_fip_diff`, `sp_xfip_diff`, `sp_k_pct_diff`, `sp_siera_diff`

```
For each (season, pitcher_name):
    lookup[(season, name)] = season_aggregate_stat
    # This uses the FULL SEASON aggregate from FanGraphs
```

**Temporal safety concern:** This uses the full-season aggregate, which includes games AFTER the game being predicted. This is a known limitation of v1.0 -- season-end FIP includes all starts, not just those before the prediction date.

**v2.0 fix recommendation:** Convert to season-to-date computation using pitcher game logs:
1. Fetch per-game log for each SP (already done for recent form)
2. For each game_date, aggregate stats from starts BEFORE that date only
3. Use shift(1) equivalent: only include starts where `start_date < game_date`

This is SP-02's core engineering challenge. It transforms the lookup from a simple season dictionary to a date-indexed cumulative computation.

### Pattern 2: Rolling Calendar Window (Current Pattern, Keep)

Used for: `sp_recent_era_diff` (30-day window)

```python
window = log[(log["date"] >= window_start) & (log["date"] < date_dt)]
```

**Temporal safety:** Already correct. The `< date_dt` (strictly less than) prevents leakage. Keep this pattern for any new rolling SP features.

### Pattern 3: Shift(1) on Sorted Game Logs (For New Workload Features)

Used for: new `sp_pitch_count_last_diff`, `sp_days_rest_diff`

```python
# Sort pitcher's starts by date
pitcher_log = pitcher_log.sort_values("date")
# shift(1) gives the PREVIOUS start's value
pitcher_log["prev_pitch_count"] = pitcher_log["numberOfPitches"].shift(1)
pitcher_log["days_since_last"] = pitcher_log["date"].diff().dt.days
```

**Temporal safety:** shift(1) on date-sorted data guarantees no look-ahead. This is the same pattern used for `rolling_ops_diff` in v1.0.

### Pattern 4: Season-to-Date Cumulative (New Pattern for v2.0)

For converting season-aggregate features to proper season-to-date:

```python
# For FIP computation from game logs:
# FIP = ((13*HR + 3*(BB+HBP) - 2*K) / IP) + FIP_constant
pitcher_log = pitcher_log.sort_values("date")
pitcher_log["cum_k"] = pitcher_log.groupby("season")["strikeouts"].cumsum().shift(1)
pitcher_log["cum_bb"] = pitcher_log.groupby("season")["walks"].cumsum().shift(1)
pitcher_log["cum_hr"] = pitcher_log.groupby("season")["homeRuns"].cumsum().shift(1)
pitcher_log["cum_ip"] = pitcher_log.groupby("season")["innings_pitched"].cumsum().shift(1)
# Compute FIP from cumulative components
```

**Key:** The `shift(1)` after `cumsum()` ensures the cumulative total excludes the current game.

---

## Cold-Start Handling (Concrete Recommendations)

### Scenario 1: First Start of Season

**Problem:** No season-to-date stats, no recent form window, no prior pitch count.

**Recommendation:**
- Season-to-date features (FIP, xFIP, K-BB%, WHIP, ERA): Use **previous season's full-season value** as the initial prior. If no previous season data exists (rookie), use **league-average** values.
- Recent form (30-day ERA/FIP): Return **NaN**. The model's imputation strategy (median fill or indicator variable) handles this. Do not fabricate a recent-form value from prior-year data.
- Pitch count last start: Return **NaN**. Impute with league-average ~93 pitches.
- Days rest: Return **NaN**. Impute with 5 (modal rest period).

**Implementation:**
```python
# In season-to-date lookup:
if cum_ip == 0 or cum_ip is NaN:
    # Fall back to previous season
    prev_season_stats = sp_lookup.get((season - 1, pitcher_name))
    if prev_season_stats:
        return prev_season_stats[stat]
    else:
        return LEAGUE_AVERAGE[stat]  # e.g., FIP ~4.20, K-BB% ~10%, WHIP ~1.30
```

### Scenario 2: SP Changed (Scratched Starter)

**Problem:** Model prediction was generated with Pitcher A's features, but Pitcher B actually starts.

**Recommendation for the live pipeline (PIPE-03):**
1. **Pre-lineup prediction (10am ET):** Uses team-level features only. SP features set to team-average SP stats (similar to FiveThirtyEight's opener handling: "that team will use its average pitcher adjustment").
2. **Post-lineup prediction (1pm ET):** Uses confirmed SP features.
3. **Late scratch (after 1pm ET):** Flag the prediction with `sp_confirmed = False`. Optionally re-run with the replacement SP's features if known, or fall back to team-average SP features. Do NOT use the scratched pitcher's features.

**Recommendation for the backtest pipeline:**
The existing `_filter_tbd_starters()` drops games with missing SPs. For the backtest, this is correct -- we only evaluate games where both SPs were confirmed. No change needed.

### Scenario 3: Rookie / No Historical Data

**Problem:** Pitcher has no FanGraphs season stats and no prior-season data.

**Recommendation:**
- Use league-average replacement-level stats (FanGraphs "replacement level" pitcher is roughly: ERA ~5.00, FIP ~4.70, K% ~18%, BB% ~9%, WHIP ~1.50).
- This is better than NaN because replacement-level SPs are genuinely worse than average, and the model should reflect that.
- FiveThirtyEight assigns "below-average rGS" to new pitchers, which is equivalent.

---

## Multicollinearity Analysis: SP Features vs. Existing Team Features

### Known High-Correlation Pairs

| Feature A | Feature B | Expected r | Risk | Action |
|-----------|-----------|-----------|------|--------|
| `sp_fip_diff` | `sp_xfip_diff` | ~0.85-0.90 | HIGH | These measure nearly the same thing (xFIP = FIP with normalized HR/FB). **Drop one.** Recommendation: keep `sp_xfip_diff` (more predictive forward-looking) and drop `sp_fip_diff`. |
| `sp_fip_diff` | `sp_siera_diff` | ~0.75-0.85 | HIGH | SIERA uses batted-ball data that FIP ignores, so there is independent signal. But overlap is substantial. **Keep SIERA, drop FIP.** SIERA is the most predictive forward-looking metric (RMSE 0.964 vs FIP's 1.010). |
| `sp_xfip_diff` | `sp_siera_diff` | ~0.80-0.88 | HIGH | Very high overlap. Both are forward-looking ERA estimators. **Pick one.** Recommendation: keep `sp_siera_diff` (slightly better RMSE) and drop `sp_xfip_diff`. OR keep both and let XGBoost handle it (trees are robust to multicollinearity). |
| `sp_era_diff` (new) | `sp_fip_diff` | ~0.65-0.80 | MODERATE | ERA includes BABIP/sequencing signal that FIP strips out. Some independent information. Acceptable for tree-based models. |
| `sp_k_bb_pct_diff` (new) | `sp_k_pct_diff` | ~0.85+ | HIGH | K-BB% is literally K% minus a new term. **Replace sp_k_pct_diff with sp_k_bb_pct_diff.** |
| `sp_whip_diff` (new) | `sp_fip_diff` | ~0.65-0.75 | MODERATE | Different construction (outcomes vs. components). Acceptable. |
| `sp_fip_diff` | `team_ops_diff` | ~0.15-0.30 | LOW | SP quality and team offense are largely independent. Low multicollinearity. Good. |
| `sp_fip_diff` | `bullpen_era_diff` | ~0.20-0.40 | LOW | SP and bullpen are different pitcher pools. Some team-level correlation (good teams have both). Acceptable. |
| `sp_recent_era_diff` | `sp_era_diff` (new) | ~0.50-0.65 | MODERATE | Recent form vs. full season -- these are deliberately different time windows. Both add value. Keep both. |

### Recommended v2.0 SP Feature Set (After Multicollinearity Pruning)

**For XGBoost and Random Forest (tree-based, multicollinearity-tolerant):**

| # | Feature | Source | Replaces | Rationale |
|---|---------|--------|----------|-----------|
| 1 | `sp_siera_diff` | FanGraphs `pitching_stats()` SIERA | Keep from v1 | Most predictive forward-looking ERA estimator |
| 2 | `sp_k_bb_pct_diff` | Computed: K% - BB% | Replaces `sp_k_pct_diff` | Strictly more informative; captures both K and BB signal |
| 3 | `sp_whip_diff` | FanGraphs `pitching_stats()` WHIP | New | Top-tier run prevention predictor, independent signal from FIP-family |
| 4 | `sp_era_diff` | FanGraphs or season-to-date computation | New | Universal quality signal; captures BABIP/sequencing FIP misses |
| 5 | `sp_recent_era_diff` | MLB Stats API game logs (30-day) | Keep from v1 | Recent form signal, different time window than season aggregate |
| 6 | `sp_recent_fip_diff` | Computed from game log K/BB/HR/IP | New | More stable than recent ERA at small samples |
| 7 | `xwoba_diff` | Baseball Savant `est_woba` | Fix ADVF-07 | Batted-ball quality signal orthogonal to FIP-family |
| 8 | `sp_pitch_count_last_diff` | MLB Stats API game logs | New | Workload signal (small but real) |
| 9 | `sp_days_rest_diff` | Computed from game log dates | New | Cheap to compute; may not survive feature selection |

**Drop from v1:**
- `sp_fip_diff` -- redundant with SIERA (SIERA strictly dominates for prediction)
- `sp_xfip_diff` -- redundant with SIERA (nearly identical forward-looking value)
- `sp_k_pct_diff` -- replaced by `sp_k_bb_pct_diff`

**For Logistic Regression (multicollinearity-sensitive):**
Use a reduced set: `sp_siera_diff`, `sp_k_bb_pct_diff`, `sp_recent_era_diff`, `xwoba_diff`. Drop WHIP (overlaps SIERA), ERA (overlaps SIERA), and workload features (weak signal).

---

## Feature Dependencies

```
pitcher game logs (MLB Stats API)
  |
  +-- Season-to-date cumulative stats (shift(1) on cumsum)
  |     |
  |     +-- sp_era_diff (season-to-date)
  |     +-- sp_k_bb_pct_diff (from cumulative K%, BB%)
  |     +-- sp_whip_diff (from cumulative H, BB, IP)
  |
  +-- Rolling 30-day window
  |     |
  |     +-- sp_recent_era_diff (existing)
  |     +-- sp_recent_fip_diff (new: K, BB, HR, IP in window)
  |
  +-- Shift(1) on start sequence
  |     |
  |     +-- sp_pitch_count_last_diff
  |     +-- sp_days_rest_diff
  |
  +-- Cold-start fallback
        |
        +-- Previous season FanGraphs aggregate
        +-- League-average replacement level

Baseball Savant expected stats (separate data source)
  |
  +-- xwoba_diff (est_woba column, last_name first_name join)
  +-- Uses season aggregate (not game-level)
  +-- Cold-start: previous season or league average
```

---

## Implementation Priority

### Phase 1: Fix and Low-Hanging Fruit
1. **ADVF-07 fix** -- `xwoba_diff` column name and join fix. Highest ROI: zero new data, just fix the existing pipeline.
2. **`sp_k_bb_pct_diff`** -- trivial to compute from existing `pitching_stats()` data (K% and BB% are already fetched).
3. **`sp_whip_diff`** -- WHIP is already in `pitching_stats()` output, just not used.

### Phase 2: Season-to-Date Conversion
4. **Convert season-aggregate SP features to proper season-to-date** using pitcher game logs with cumulative shift(1). This is the biggest engineering lift but the most important temporal safety improvement.
5. **`sp_era_diff`** (season-to-date) -- comes naturally from the season-to-date conversion.

### Phase 3: Workload and Recent Form Expansion
6. **`sp_recent_fip_diff`** -- requires computing FIP from game log components within the 30-day window.
7. **`sp_pitch_count_last_diff`** -- requires adding `numberOfPitches` to the pitcher game log fetch.
8. **`sp_days_rest_diff`** -- trivial computation from game log dates.

### Phase 4: Validation
9. **VIF analysis** on the full expanded feature set. Drop any feature with VIF > 10.
10. **Feature importance ranking** from XGBoost after retrain. Drop features with near-zero gain.
11. **Ablation study** -- retrain with and without SP features to quantify the Brier score improvement.

---

## Data Availability for New Features

| Feature | Data Source | pybaseball / API Function | Already Cached? | Additional Fetches? |
|---------|------------|--------------------------|----------------|-------------------|
| `xwoba_diff` (fix) | Baseball Savant | `statcast_pitcher_expected_stats(season)` | YES (cached as `statcast_pitcher_{season}`) | None -- just fix column parsing |
| `sp_k_bb_pct_diff` | FanGraphs | `pitching_stats(season)` | YES (cached as `sp_stats_{season}`) | None -- K% and BB% already present |
| `sp_whip_diff` | FanGraphs | `pitching_stats(season)` | YES | None -- WHIP already present |
| `sp_era_diff` (STD) | MLB Stats API | `person` endpoint with gameLog hydrate | YES (cached as `pitcher_game_log_{season}_{id}`) | None -- ER and IP in existing logs |
| `sp_recent_fip_diff` | MLB Stats API | Same game log | PARTIAL -- logs have ER and IP but may lack K/BB/HR per game | May need to re-fetch with additional stat fields |
| `sp_pitch_count_last_diff` | MLB Stats API | Same game log | UNKNOWN -- need to check if `numberOfPitches` is in cached logs | May need to re-fetch or add field |
| `sp_days_rest_diff` | MLB Stats API | Same game log | YES -- `date` column exists | None -- pure computation |

---

## Sources

- [FanGraphs Sabermetrics Library: Sample Size](https://library.fangraphs.com/principles/sample-size/) -- K% stabilizes at 70 BF, BB% at 170 BF, BABIP at 2000 BIP (HIGH confidence)
- [FanGraphs Sabermetrics Library: Splits](https://library.fangraphs.com/principles/split/) -- Small-sample split instability analysis (HIGH confidence)
- [Going Deep: The Relative Value of FIP, xFIP, SIERA (Pitcher List)](https://pitcherlist.com/going-deep-the-relative-value-of-fip-xfip-and-siera/) -- SIERA RMSE 0.964 vs FIP 1.010 for year-to-year prediction (HIGH confidence)
- [The Relative Value of FIP, xFIP, SIERA, and xERA Pt. II (Pitcher List)](https://pitcherlist.com/the-relative-value-of-fip-xfip-siera-and-xera-pt-ii/) -- xFIP and SIERA most predictive (HIGH confidence)
- [A Brief Analysis of Predictive Pitching Metrics (FanGraphs Community)](https://community.fangraphs.com/a-brief-analysis-of-predictive-pitching-metrics/) -- xFIP r=0.520, SIERA r=0.517, FIP r=0.462, ERA r=0.382 with future ERA (HIGH confidence)
- [FiveThirtyEight MLB Methodology](https://fivethirtyeight.com/methodology/how-our-mlb-predictions-work/) -- SP adjustment worth ~1% correct-call improvement; formula: 4.7*(pitcher_rGS - team_rGS) (HIGH confidence)
- [The Effect of Rest Days on Starting Pitcher Performance (FanGraphs Community)](https://community.fangraphs.com/the-effect-of-rest-days-on-starting-pitcher-performance/) -- No significant difference across rest categories (MEDIUM confidence -- single study)
- [Impact of Pitch Counts and Days of Rest (JSCR, 2012)](https://pubmed.ncbi.nlm.nih.gov/22344048/) -- Each pitch increases next-game ERA by 0.007; cumulative load matters more (HIGH confidence -- peer-reviewed)
- [Exploring and Selecting Features to Predict MLB Outcomes (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC8871522/) -- RFE feature selection, cumulative accumulation method (HIGH confidence -- peer-reviewed)
- [Properly Diving Into Expected Stats (FanGraphs Community)](https://community.fangraphs.com/properly-diving-into-expected-stats/) -- K-BB% explains 17.92% of future RA9 variance; "premier predictive metric" (MEDIUM confidence)
- [Baseball Prospectus: Siren Song of Expected Metrics](https://www.baseballprospectus.com/news/article/40026/prospectus-feature-siren-song-statcasts-expected-metrics/) -- xwOBA/xERA not better than FIP for pitcher prediction (MEDIUM confidence -- single analysis)
- [Stop using K/BB! (Beyond the Box Score)](https://www.beyondtheboxscore.com/2012/11/25/3686732/stop-using-k-bb) -- K-BB% strictly superior to K/BB ratio (HIGH confidence)
- [Baseball Savant Expected Statistics CSV](https://baseballsavant.mlb.com/leaderboard/expected_statistics?type=pitcher&year=2024&position=&team=&filterType=pa&min=50&csv=true) -- Confirmed column names: `last_name, first_name`, `est_woba`, `woba`, `xera` (HIGH confidence -- primary source verified 2026-03-29)
- [pybaseball GitHub: statcast_pitcher.py](https://github.com/jldbc/pybaseball/blob/master/pybaseball/statcast_pitcher.py) -- Function fetches from Baseball Savant CSV endpoint (HIGH confidence)
