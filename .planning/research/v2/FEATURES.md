# Feature Landscape — v2.0 (SP Features + Live Dashboard)

**Domain:** MLB pre-game win probability model with live prediction dashboard
**Researched:** 2026-03-29
**Scope:** NEW features for v2.0 only. v1 features (team batting, rolling form, park factors, bullpen ERA, Log5, Kalshi comparison) are validated and not re-assessed here.

---

## Table Stakes

Features users expect from a live prediction dashboard. Missing = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Today's games with win probabilities | Core value proposition -- this is what the dashboard exists to show | Med | Requires daily pipeline + MLB Stats API schedule fetch |
| Pre-lineup and post-lineup prediction versions | PROJECT.md explicitly requires two daily runs showing both versions side-by-side | Med | Two pipeline runs (10am/1pm ET), both stored in Postgres |
| Starting pitcher display per game | SP is the #1 pre-game predictor; hiding it would be a glaring omission | Low | MLB Stats API `schedule(sportId=1, date=today)` returns probablePitchers |
| Model confidence/probability shown per game | Raw win% is the core output; must be front-and-center | Low | Three model probabilities displayed (LR, RF, XGBoost) |
| Kalshi price comparison | v1's edge analysis is the differentiating value; dashboard must surface it | Med | Requires Kalshi API integration in pipeline + storage |
| SP feature integration in models | v2's primary analytical improvement; models without SP features are v1 | High | Full feature matrix expansion + walk-forward retrain |
| Mobile-responsive layout | Checking game predictions on a phone is the most common use case | Low | CSS/Tailwind -- standard responsive design |
| Dark theme | PROJECT.md specifies "dark cinematic + amber aesthetic" | Low | Cosmetic but specified as a requirement |

## Differentiators

Features that set this dashboard apart from generic MLB prediction sites.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Edge signal (BUY_YES / BUY_NO / NO_EDGE) | Shows where model disagrees with Kalshi market -- unique for a personal tool | Med | `|model_prob - kalshi_price| > threshold` with fee adjustment |
| Pre-lineup vs post-lineup delta | Shows HOW MUCH the prediction changes when SPs are confirmed -- quantifies pitcher impact | Low | Simple diff: `post_lineup_prob - pre_lineup_prob` |
| SP uncertainty flag | Gracefully handles scratched/unconfirmed starters -- most sites just show stale data | Med | Fallback to team-only prediction with visual indicator |
| Browser change notifications | Alerts when post-lineup predictions are ready (client-side polling, no push/email) | Med | `setInterval` polling + Notification API. No server-side push infrastructure. |
| Historical model accuracy tracker | Shows model Brier scores over time -- builds trust in predictions | Low | Query stored predictions vs actual outcomes |
| Fee-adjusted P&L display | Shows hypothetical profit/loss if you followed edge signals, after Kalshi's 7% fee | Low | Already computed in v1 edge analysis; surface in dashboard |

## Anti-Features

Features to explicitly NOT build in v2.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Automated Kalshi trade execution | PROJECT.md out-of-scope. Regulatory/financial risk. Analysis tool only. | Display edge signals for manual decision-making |
| In-game live win probability | Different problem domain (real-time pitch-by-pitch state). Not pre-game prediction. | Keep scope to pre-game only |
| User accounts / authentication | Single-user personal tool. Auth adds complexity for no value. | Public dashboard or simple shared secret if needed |
| Email/SMS notifications | Push infrastructure (SMTP/Twilio) is overengineered for one user. | Browser Notification API with client-side polling |
| Player prop predictions | Requires per-player modeling with tiny sample sizes. Out of scope. | Stick to game outcome (win/loss) only |
| Batter-vs-pitcher matchup features | PROJECT.md explicitly notes "overfitting trap in MLB prediction literature". Sample sizes too small. | Use team-level offense + SP-level pitching features |
| Real-time Kalshi price streaming | WebSocket connection to Kalshi for live price updates. Overkill for twice-daily pipeline. | Fetch Kalshi prices during pipeline runs (10am/1pm ET) |
| Complex user-facing model comparison UI | Showing all three models' internals (feature importance, calibration curves) in the dashboard | Keep model comparison in Jupyter notebooks; dashboard shows final probabilities only |

## SP Feature Specifics (Track 1)

### Required SP Stats per Pitcher-Season

| Stat | Source | Available 2015-2024? | Notes |
|------|--------|---------------------|-------|
| ERA | FanGraphs (pybaseball) or MLB Stats API | Yes | Both sources reliable |
| FIP | FanGraphs (pybaseball) | Yes | NOT available from MLB Stats API. Must use FanGraphs or compute manually. |
| xFIP | FanGraphs (pybaseball) | Yes | NOT available from MLB Stats API. Requires fly ball data for manual computation. |
| K% | FanGraphs (pybaseball) or computed from MLB Stats API (SO/TBF) | Yes | Computable from raw stats |
| BB% | FanGraphs (pybaseball) or computed from MLB Stats API (BB/TBF) | Yes | Computable from raw stats |
| WHIP | FanGraphs (pybaseball) or MLB Stats API | Yes | Both sources reliable |
| Home ERA / Away ERA | MLB Stats API (statSplits) | Yes | Use splits endpoint, NOT FanGraphs |
| xwOBA against | Baseball Savant (pybaseball Statcast) | Yes (2015+) | Via `statcast_pitcher_expected_stats()`. Already partially implemented in v1 (ADVF-07 bug). |
| xERA | Baseball Savant (pybaseball Statcast) | Yes (2015+) | Available from expected stats CSV |

### Feature Matrix Integration

The FeatureBuilder must produce these differential features per game:

| Feature | Formula | Dependencies |
|---------|---------|-------------|
| `sp_fip_diff` | `home_sp_fip - away_sp_fip` | FanGraphs season-level SP stats |
| `sp_xfip_diff` | `home_sp_xfip - away_sp_xfip` | FanGraphs season-level SP stats |
| `sp_kpct_diff` | `home_sp_kpct - away_sp_kpct` | FanGraphs or computed from MLB API |
| `sp_bbpct_diff` | `home_sp_bbpct - away_sp_bbpct` | FanGraphs or computed from MLB API |
| `sp_whip_diff` | `home_sp_whip - away_sp_whip` | FanGraphs or MLB Stats API |
| `sp_era_30d_diff` | `home_sp_era_30d - away_sp_era_30d` | MLB Stats API game logs (already in v1) |
| `sp_home_away_era_diff` | `home_sp_home_era - away_sp_away_era` | MLB Stats API splits |
| `sp_xwoba_diff` | `home_sp_xwoba - away_sp_xwoba` | Baseball Savant expected stats (ADVF-07 fix) |
| `sp_xera_diff` | `home_sp_xera - away_sp_xera` | Baseball Savant expected stats |

**Temporal safety:** All SP season-level stats use the PRIOR completed season for games before the all-star break of a new season, then transition to current-season stats once sample size is sufficient (30+ IP in current season). Rolling 30-day ERA already uses `shift(1)` via the existing implementation.

## Feature Dependencies

```
MLB Stats API schedule (game dates, probable pitchers)
  --> SP name resolution (name -> player_id map)
    --> SP game logs (30-day rolling ERA) [already in v1]
    --> SP season stats from FanGraphs (FIP, xFIP, K%, BB%, WHIP) [new in v2]
    --> SP Statcast expected stats (xwOBA, xERA) [ADVF-07 fix in v2]
    --> SP home/away splits from MLB Stats API [new in v2]
      --> FeatureBuilder differential features
        --> Feature store (Parquet)
          --> Model retrain (LR, RF, XGBoost)

Daily pipeline:
  10am ET: schedule + team features only --> pre-lineup predictions
  1pm ET: schedule + confirmed SP + full features --> post-lineup predictions
    --> Postgres storage
      --> React dashboard display
```

## MVP Recommendation

### Phase 1: SP Data + Model Retrain (Track 1)
Prioritize:
1. FanGraphs SP stats acquisition (all 10 seasons, cache to Parquet)
2. ADVF-07 fix (xwOBA column pipeline correction)
3. Home/away splits via MLB Stats API
4. FeatureBuilder expansion with SP differential features
5. Walk-forward retrain of all three models

### Phase 2: Pipeline + Dashboard (Track 2)
Prioritize:
1. Docker Compose stack (Postgres + FastAPI + scheduler + nginx)
2. Daily prediction pipeline (scheduler -> MLB API -> model predict -> Postgres)
3. React dashboard with today's games + probabilities
4. Kalshi edge display
5. Browser notifications (polish feature, do last)

**Defer:** Historical accuracy tracker and fee-adjusted P&L display. These are nice-to-have analytics that can be added after the core dashboard is live.

---

## Sources

- [PROJECT.md](../../PROJECT.md) -- v2.0 requirements (SP-01 through DASH-04, INFRA-01/02)
- [FanGraphs FIP/xFIP definitions](https://library.fangraphs.com/pitching/fip/)
- [MLB Stats API pitcher stat fields](https://appac.github.io/mlb-data-api-docs/)
- [Baseball Savant expected stats](https://baseballsavant.mlb.com/leaderboard/expected_statistics?type=pitcher)
- v1 codebase analysis: `src/data/sp_stats.py`, `src/features/sp_recent_form.py`, `src/data/statcast.py`, `src/features/feature_builder.py`
