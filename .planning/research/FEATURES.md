# Feature Landscape

**Domain:** MLB pre-game win probability modeling
**Researched:** 2026-03-28

## Table Stakes

Features users (and competitive models) expect. Missing any of these = model underperforms trivially solvable baselines.

### Starting Pitcher Metrics

| Feature | Why Expected | Complexity | Data Source | Notes |
|---------|-------------|------------|-------------|-------|
| **ERA (season-to-date)** | Universal pitcher quality signal; every baseline model includes it | Low | pybaseball `pitching_stats()`, MLB Stats API | Use rolling season-to-date, not career. Noisy early season (<30 IP) |
| **FIP (Fielding Independent Pitching)** | Strips defense/luck from ERA; better true talent indicator. Correlates most strongly with in-season ERA | Low | pybaseball `pitching_stats()` via FanGraphs | Computed from K, BB, HBP, HR only. Available directly from FanGraphs columns |
| **xFIP (Expected FIP)** | Normalizes HR/FB rate to league average; SIERA and xFIP are the two most predictive season-to-season ERA forecasters (RMSE ~0.87) | Low | pybaseball FanGraphs columns | Slightly more predictive than FIP for forward-looking estimates |
| **K% (Strikeout Rate)** | Directly pitcher-controlled; strong signal of dominance | Low | pybaseball `pitching_stats()` | Use rate (K/PA), not raw count. Stabilizes ~70 batters faced |
| **BB% (Walk Rate)** | Directly pitcher-controlled; command indicator | Low | pybaseball `pitching_stats()` | Stabilizes ~170 batters faced |
| **WHIP** | Walks + Hits per IP; research consistently identifies as top-tier predictor. Disallowing traffic is the most important pitching consideration for winning | Low | pybaseball `pitching_stats()` | Strongly correlated with run prevention |
| **Starting Pitcher Differential** | Difference between home SP and away SP on key metrics (ERA, FIP, WHIP). Low multicollinearity with team offense features, meaningful correlation with outcome | Medium | Computed from above | FiveThirtyEight found SP adjustments worth ~1 percentage point in correct-call rate. Frame as home_SP minus away_SP |

### Team Offense Metrics

| Feature | Why Expected | Complexity | Data Source | Notes |
|---------|-------------|------------|-------------|-------|
| **wOBA (Weighted On-Base Average)** | Best single offensive metric; weights each outcome by run expectancy. More informative than OPS because it properly weights events | Low | pybaseball FanGraphs columns | League-calibrated each season. Stabilizes ~200 PA |
| **OPS (On-Base Plus Slugging)** | Ubiquitous offensive summary; every research paper uses it as a baseline feature | Low | pybaseball, Baseball Reference | Simpler than wOBA but still strong. Widely understood |
| **Run Differential (season-to-date)** | Foundation of Pythagorean expectation; Bill James showed RS^2/(RS^2+RA^2) predicts W% better than actual W%. Pythagorean expectation and Log5 are the most important features per PMC research | Low | pybaseball `team_game_logs()`, Baseball Reference | Calculate as runs scored minus runs allowed. Per-game average preferred over cumulative |
| **OBP (On-Base Percentage)** | Getting on base is fundamental; consistently selected in RFE feature selection across all 30 teams | Low | pybaseball `batting_stats()` | Stabilizes ~460 PA |
| **SLG (Slugging Percentage)** | Power proxy; extra-base hit production | Low | pybaseball `batting_stats()` | Use with OBP rather than relying on AVG |

### Game Context

| Feature | Why Expected | Complexity | Data Source | Notes |
|---------|-------------|------------|-------------|-------|
| **Home/Away Indicator** | Home teams win ~53.9% of games overall. Every model includes this. FiveThirtyEight assigns 24 Elo points for home field | Low | MLB Stats API schedule endpoint | Binary feature (1/0). Most basic and essential context variable |
| **Park Factor (runs)** | Coors Field inflates runs ~15-20% vs. league average; pitcher-friendly parks suppress ~10%. Three-year rolling average is standard. Physical ballpark dimensions + altitude + temperature drive the effect | Low | Baseball Savant Statcast park factors, FanGraphs park factors | Use 3-year rolling average (1 year is too noisy). Value of 100 = neutral; >100 = hitter-friendly. Apply as multiplicative adjustment to run expectations |
| **Win Percentage / Pythagorean W%** | Team quality baseline. Pythagorean W% strips luck from actual record. Research shows Win% is "vital" -- selected across all 30 team datasets | Low | Computed from run differential or from standings | Pythagorean W% preferred over actual W% as it is more predictive of future performance |

### Rolling / Recency Features

| Feature | Why Expected | Complexity | Data Source | Notes |
|---------|-------------|------------|-------------|-------|
| **10-day trailing team OBP, SLG, OPS** | Captures hot/cold streaks. Research settles on 10-day trailing as balancing recency vs. stability. Short-term rolling features (last 5-10 games) are "highly influential" | Medium | Computed from pybaseball `team_game_logs()` | Need to compute manually. Both SMA and EMA are viable; EMA weights recent games more heavily |
| **Rolling team ERA / WHIP (10-day)** | Staff-level recent form. Pitching is the most important determinant of wins after run differential | Medium | Computed from pybaseball `team_game_logs()` | Same rolling window as offense metrics for consistency |
| **Last 5/10 game win rate differential** | Proxy for recent team momentum. Found "highly influential" in multiple models | Medium | Computed from game logs | Calculate as home_team_last_N minus away_team_last_N. Susceptible to noise at small N |

## Differentiators

Features that meaningfully improve calibration over a table-stakes baseline. Not expected in every model, but valued when present.

### Advanced Pitcher Metrics

| Feature | Value Proposition | Complexity | Data Source | Notes |
|---------|-------------------|------------|-------------|-------|
| **SIERA (Skill-Interactive ERA)** | Most predictive forward-looking ERA estimator (lowest RMSE ~0.87). Unlike FIP/xFIP, accounts for batted ball quality (GB rate, etc.) | Medium | FanGraphs via pybaseball | Slight edge over xFIP but more complex. Use as primary "true talent" SP metric |
| **SP Recent Form (last 3 starts rolling)** | Captures hot/cold pitcher streaks within season. More granular than season-to-date | Medium | Computed from pitcher game logs | Rolling window over last 3 starts: ERA, FIP, K%, BB%. Must be careful to avoid leakage -- compute from starts BEFORE the current game |
| **Pitcher Handedness Matchup** | Platoon advantage is real: batters hit better vs. opposite-hand pitchers. LHP vs. RH-heavy lineup or RHP vs. LH-heavy lineup affects expected offense | Medium | MLB Stats API (pitcher hand), lineup data | Binary or categorical: same-side dominant vs. opposite-side dominant lineup. Sample size issues for individual splits; use aggregate platoon effect (~20 point wOBA difference) |
| **SP Pitch Mix / Stuff Quality (Statcast)** | Average fastball velocity, spin rate, whiff rate -- direct measures of stuff quality that stabilize faster than outcomes | High | pybaseball `statcast_pitcher()`, Baseball Savant | Stabilizes faster than ERA/FIP. Requires pitch-level data aggregation. Avg fastball velocity alone is strong |

### Advanced Team Features

| Feature | Value Proposition | Complexity | Data Source | Notes |
|---------|-------------------|------------|-------------|-------|
| **xwOBA (Expected Weighted OBA)** | Removes defense and park from offensive evaluation. Based on exit velocity and launch angle -- reflects true contact quality | Medium | Baseball Savant leaderboard, pybaseball | Better true-talent indicator than wOBA. Only available from 2015+ (Statcast era). Use team-aggregate xwOBA |
| **ISO (Isolated Power)** | Measures raw power (SLG minus AVG). Power differential between teams predicts run scoring variance | Low | pybaseball `batting_stats()` | Low multicollinearity with OBP. Useful alongside OBP as the two independent offensive components |
| **Team Baserunning (BsR / Sprint Speed)** | Post-2023 rule changes dramatically increased stolen base volume (2,486 in 2022 to 3,617 in 2024). Teams with speed advantages exploit larger bases and pitch clock limits | Medium | FanGraphs BsR, Statcast sprint speed leaderboard | More valuable post-2023 rule changes. Team-aggregate sprint speed is available from Statcast |

### Bullpen Features

| Feature | Value Proposition | Complexity | Data Source | Notes |
|---------|-------------------|------------|-------------|-------|
| **Bullpen ERA (season-to-date)** | After the SP exits (~5-6 innings), the bullpen determines the final 3-4 innings. Bullpen quality is the second-largest pitching factor | Medium | pybaseball `pitching_stats()`, filter to RP role | Separate from SP stats. Use relievers only (GS = 0). Can also use FIP for bullpen |
| **Bullpen Usage / Fatigue (recent 3-day workload)** | Heavy recent usage degrades reliever performance. If top arms threw 2+ innings in each of the last 2 days, expected performance drops | High | Computed from pitcher game logs | Track innings pitched by top 3-4 relievers over last 3 days. Flag "heavy usage" when closer/setup pitched 2+ of last 3 days. Requires per-pitcher game log tracking |
| **Bullpen FIP** | Bullpen FIP removes luck from reliever outcomes, more predictive than bullpen ERA | Medium | pybaseball FanGraphs columns, filter to RP | Same computation as SP FIP but scoped to relievers |

### Environmental / Situational

| Feature | Value Proposition | Complexity | Data Source | Notes |
|---------|-------------------|------------|-------------|-------|
| **Temperature at Game Time** | Teams average ~4.2 runs/game below 60F vs. ~4.7+ above 80F. Ball travels farther in heat (less air density) | Medium | Weather APIs, historical weather data | ~0.5 run/game swing between cold and hot. Most impactful at extreme parks (Coors + heat = offensive explosion). Dome parks are neutral |
| **Wind Speed and Direction** | Wind out at 10+ mph significantly boosts offense; wind in suppresses scoring. Historically profitable over/under signal | Medium | Weather APIs, historical weather data | Encode as wind_out_speed (positive = blowing out, negative = blowing in). Only relevant for open-air parks |
| **Travel Distance / Jet Lag** | Research shows teams traveling east lose ~3.5% of home advantage. FiveThirtyEight penalizes up to ~4 Elo points for travel. Cross-timezone travel measurably degrades performance | Medium | Computed from schedule (city distances) | Formula: miles_traveled^(1/3) * -0.31 (FiveThirtyEight). Most impactful for coast-to-coast travel. Apply to team arriving from road trip |
| **Rest Days** | FiveThirtyEight credits 2.3 Elo points per rest day (up to 3). Teams with rest advantage after off-day perform measurably better | Low | Computed from schedule | Binary or count: days since last game (cap at 3). Simple to compute from schedule data |

### Meta / Derived Features

| Feature | Value Proposition | Complexity | Data Source | Notes |
|---------|-------------------|------------|-------------|-------|
| **Log5 Win Probability** | Bill James's method for estimating head-to-head win probability from each team's overall W%. Equivalent to Elo/Bradley-Terry/logistic model. Research ranks it alongside Pythagorean as most important feature | Low | Computed from team win percentages | P(A beats B) = (pA - pA*pB) / (pA + pB - 2*pA*pB). Use Pythagorean W% as input rather than actual W% |
| **Elo Rating Differential** | Team strength rating that updates after each game, mean-reverts between seasons. Captures momentum and strength of schedule implicitly | Medium | Computed (implement custom Elo system) | K-factor tuning is critical. FiveThirtyEight uses ~4 for MLB. Can blend with preseason projections (Steamer/ZiPS) at 67/33 weight |
| **Steamer/ZiPS Projected WAR (SP)** | Pre-season pitcher projections from FanGraphs. ZiPS uses 3 years weighted 8/5/4 for pitchers with DIPS theory. More stable than early-season stats | Medium | FanGraphs projections page, pybaseball | Most valuable early in season when sample sizes are small. Blend with actuals as season progresses using Bayesian updating |

## Anti-Features

Features that seem useful but add noise, data leakage risk, or reduce calibration.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Season-end / full-season batting average (AVG)** | AVG is the least informative batting metric; does not distinguish walk-drawing ability from hit types. wOBA strictly dominates | Use wOBA or OPS. AVG adds no marginal information once OBP/SLG are included |
| **Raw win-loss record (actual W%)** | Actual W% is noisy -- influenced by bullpen luck, one-run game variance, sequencing. Pythagorean W% is strictly more predictive of future performance | Use Pythagorean W% (run-differential based). Only use actual W% for Log5 if Pythagorean unavailable |
| **Fielding percentage / defensive assists / putouts** | Traditional fielding stats have minimal variation between teams (all are 97-99%) and consistently *reduce* model accuracy when included. One practitioner confirmed these features "consistently reduced accuracy" | Use DRS or OAA at team level only if defensive differentiation is needed. Even then, defense is a minor predictor relative to pitching/offense |
| **Batter vs. Pitcher (BvP) historical matchups** | Sample sizes are almost always too small (most batter-pitcher pairs face each other 5-15 times). Massive noise, false patterns, and overfitting risk. "Reverse platoon" effects confound analysis | Use aggregate platoon splits (LHP vs. RHB differential) instead of individual BvP. For pre-game model, team-level metrics dominate |
| **Individual game box score stats from current game** | TARGET LEAKAGE: the most dangerous pitfall. If season averages are updated to include the game being predicted, the model gets "future knowledge." One practitioner found this inflated accuracy dramatically until fixed | Rigorous temporal alignment: all features must be computed from data BEFORE the current game. Use lag-1 game logs. Verify with a timestamp audit |
| **Pitcher days since last start** | Seems logical but research found this feature "did not improve models' performance nor impact predictions." Standard 5-day rotation normalizes rest; deviations are rare and captured by other signals | Omit unless modeling bullpen games or unusual rest scenarios. The FiveThirtyEight rest-day adjustment (2.3 pts/day) is for teams, not individual SPs |
| **Strikeout-to-walk ratio (K/BB)** | Redundant with K% and BB% already in model. Adding a ratio of features already present introduces multicollinearity without new information | Keep K% and BB% as separate features. Drop K/BB |
| **Stolen base stats (individual)** | Individual stolen base counts are noisy and have low correlation with game outcomes. Team-level sprint speed is better | Use team aggregate sprint speed or BsR if baserunning matters. Individual SB counts are noise |
| **Lineup batting order position** | While sabermetrics influence lineup construction, the marginal effect of batting order optimization vs. a random reasonable lineup is ~5-15 runs per season (~0.03 runs/game). Not worth the feature engineering complexity | Use team-aggregate offensive stats (wOBA, OPS) which capture lineup quality without order sensitivity |

## Feature Dependencies

```
Park Factor --> adjusts run-based metrics (ERA, run differential, wOBA context)
  |
  v
Run Differential --> feeds Pythagorean W%
  |
  v
Pythagorean W% --> feeds Log5 matchup probability
  |
  v
Log5 Probability --> strong standalone prediction baseline

Starting Pitcher Metrics (ERA, FIP, xFIP, SIERA, K%, BB%, WHIP)
  |-- All require: pitcher identified (confirmed starter)
  |-- Season-to-date requires: minimum IP threshold (suggest 10+ IP, else fall back to projections)
  |-- Recent form (3-start rolling) requires: 3+ starts this season
  |
  v
SP Differential = home_SP_metric - away_SP_metric (requires both pitchers)

Team Offense (wOBA, OPS, OBP, SLG, ISO, xwOBA)
  |-- Season-to-date: available after game 1
  |-- Rolling (10-day): requires 3+ games in window
  |-- xwOBA: requires Statcast era (2015+)
  |
  v
Team Offense Differential = home_team - away_team

Bullpen Metrics (ERA, FIP, usage)
  |-- Season-to-date: available after ~5 games (relievers accumulate IP slowly)
  |-- Usage/fatigue: requires last 3 days of game logs
  |-- Depends on: knowing who is NOT starting (whole bullpen minus SP)

Weather / Environment
  |-- Temperature + Wind: available day-of from weather APIs
  |-- Independent of other features
  |-- Only applies to outdoor parks (exclude dome stadiums)

Elo Ratings
  |-- Requires: game results from all previous games (sequential update)
  |-- Preseason initialization requires: projection systems (Steamer/ZiPS/PECOTA)
  |-- Independent of per-game pitcher/team features (different signal)
```

## Feature Engineering Strategy

### Rolling Window Recommendations

| Window | Use Case | Rationale |
|--------|----------|-----------|
| **Season-to-date** | Primary signal for stable metrics (FIP, wOBA, OPS) | Full sample maximizes stability |
| **Last 10 games / 10 days** | Recency weighting for team offense/pitching | Balances recency vs. noise (research consensus) |
| **Last 3 starts** | SP recent form | Captures pitcher-specific hot/cold streaks |
| **Last 3 days** | Bullpen fatigue | Reliever usage degrades performance over short windows |
| **Exponential Moving Average** | Alternative to SMA for all rolling features | Weights recent observations more heavily; useful for capturing streaks |

### Differential Framing

All features should be framed as differentials (home minus away) rather than raw values for each team separately. This:
- Halves the feature count (reduces overfitting risk)
- Directly encodes the matchup comparison
- Is the standard approach in research (SVM model with 11 differential features achieved ~60% accuracy with 13.95% ROI)

### Early-Season Cold Start

Before ~20 games into the season, sample sizes are too small for stable rolling stats. Strategy:
1. **Weeks 1-2**: Lean heavily on preseason projections (Steamer/ZiPS WAR, projected ERA) and prior-year Elo
2. **Weeks 3-4**: Blend projections with early actuals using Bayesian weighting (e.g., 60% projection / 40% actual)
3. **May onward**: Shift to primarily actual season-to-date stats with projection as prior

### Feature Count Guidance

Research shows diminishing returns and overfitting risk above ~15 features for game-level binary classification. The best-performing practical model used 11 features. Recommended target: **10-15 differential features** plus home/away indicator and park factor.

## MVP Recommendation

Prioritize these features for V1 (achieves competitive ~58-62% accuracy baseline):

1. **Home/Away indicator** -- trivial to implement, foundational
2. **Starting Pitcher differential (FIP or xFIP)** -- single strongest per-game predictor
3. **Team wOBA or OPS differential (season-to-date)** -- best single offensive summary
4. **Pythagorean W% differential** -- captures overall team quality from run differential
5. **Park factor (runs, 3-year average)** -- adjusts expectations for venue
6. **Rolling 10-game team OPS differential** -- captures recent form
7. **Bullpen ERA or FIP differential** -- second-tier pitching signal
8. **SP K% differential** -- pitcher dominance indicator, low multicollinearity with FIP

Defer for V2:
- **Weather features**: Require external weather API integration, only relevant for outdoor parks (~21 of 30 venues), marginal gain (~0.5 runs/game at extremes)
- **Bullpen fatigue tracking**: Requires per-pitcher game log pipeline, complex to engineer correctly
- **xwOBA / Statcast-derived offense**: Requires Statcast data pipeline, only available 2015+
- **Travel distance penalty**: Requires computing city-to-city distances from schedule, small effect (~3.5% home advantage reduction)
- **Elo rating system**: Requires implementing sequential update system, blending with projections; powerful but architectural complexity

Defer indefinitely:
- **Individual BvP matchups**: Noise, sample size issues, overfitting risk
- **Lineup batting order**: Marginal effect, high complexity
- **Fielding stats**: Consistently hurts model accuracy

## Data Availability Summary

| Feature Category | Primary Source | pybaseball Function | Pre-Game Available? |
|------------------|---------------|--------------------|--------------------|
| SP season stats (ERA, FIP, xFIP, K%, BB%, WHIP) | FanGraphs | `pitching_stats(season)` | Yes -- computed from prior games |
| SP Statcast (velocity, spin, whiff) | Baseball Savant | `statcast_pitcher(start_dt, end_dt, player_id)` | Yes -- aggregated from prior outings |
| Team offense (wOBA, OPS, OBP, SLG) | FanGraphs | `batting_stats(season)` or `team_batting_bref(team, season)` | Yes -- season-to-date |
| Team game logs (for rolling calcs) | Baseball Reference | `team_game_logs(season, team)` | Yes -- all prior games |
| Park factors | Baseball Savant, FanGraphs | Manual download or scrape | Yes -- static per season |
| Probable starters | MLB Stats API | `statsapi.schedule()` | Yes -- confirmed day-of |
| Bullpen stats | FanGraphs | `pitching_stats(season)` filtered to RP | Yes -- season-to-date |
| Weather | External weather API | Not in pybaseball | Yes -- day-of forecast |
| Projections (Steamer/ZiPS) | FanGraphs | `pitching_stats(season, stat_columns='proj')` | Yes -- preseason, updated daily |

## Sources

- [Exploring and Selecting Features to Predict the Next Outcomes of MLB Games (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC8871522/) -- Feature selection with RFE across 30 teams, SVM achieving 65.75%
- [How I Beat the Sportsbook in Baseball with ML (Zheng)](https://medium.com/@40alexz.40/how-i-beat-the-sportsbook-in-baseball-with-machine-learning-0387f25fbdd8) -- 11-feature SVM, data leakage discovery, 13.95% ROI
- [Predicting Win Probability for MLB Games (Faddis)](https://medium.com/@nfadd/predicting-win-probability-for-mlb-games-with-machine-learning-a4c2ad993496) -- XGBoost with rolling averages, 61.46% accuracy
- [FiveThirtyEight MLB Elo Methodology](https://fivethirtyeight.com/methodology/how-our-mlb-predictions-work/) -- Elo adjustments for SP, home field, travel, rest
- [The Relative Value of FIP, xFIP, SIERA (Pitcher List)](https://pitcherlist.com/the-relative-value-of-fip-xfip-and-siera-pt-ii/) -- SIERA most predictive forward-looking ERA metric
- [Forecasting Outcomes of MLB Games Using ML (Wharton Thesis)](https://fisher.wharton.upenn.edu/wp-content/uploads/2020/09/Thesis_Andrew-Cui.pdf) -- 10-day trailing differentials, SP ERA differential properties
- [FanGraphs Sabermetrics Library](https://library.fangraphs.com/) -- Metric definitions, stabilization rates, split analysis
- [Baseball Savant Statcast Park Factors](https://baseballsavant.mlb.com/leaderboard/statcast-park-factors) -- Park factor data
- [AI Model Calibration for Sports Betting](https://www.sports-ai.dev/blog/ai-model-calibration-brier-score) -- Calibration-optimized models generate 69.86% higher returns than accuracy-optimized
- [Machine Learning for Sports Betting: Accuracy vs Calibration (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S266682702400015X) -- Calibration-based model selection yields +34.69% ROI vs -35.17% for accuracy-based
- [MLB 2023 Rule Changes Impact](https://www.bleedcubbieblue.com/2023/10/2/23900127/mlb-new-rules-improvements-game-times-stolen-bases-2023) -- Stolen base volume increase post-rule changes
- [Science.org Jet Lag Study](https://www.science.org/content/article/jet-lag-puts-baseball-players-their-game) -- Travel direction affects home advantage by ~3.5%
- [FanGraphs Projection Systems](https://library.fangraphs.com/principles/projections/) -- Steamer, ZiPS methodology and predictive value
