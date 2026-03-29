---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: completed
stopped_at: Completed 04-02-PLAN.md (v1 milestone complete)
last_updated: "2026-03-29T17:00:29.748Z"
last_activity: 2026-03-29 -- Completed 04-02-PLAN.md (Phase 4 notebooks)
progress:
  total_phases: 4
  completed_phases: 4
  total_plans: 10
  completed_plans: 10
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-29 after v1.0 milestone)

**Core value:** Produce well-calibrated win probability estimates that can be rigorously compared against Kalshi market prices, surfacing where models agree, disagree, and where edges may exist.
**Current focus:** v1.0 shipped. Next: `/gsd:new-milestone` for v2 (live prediction pipeline + advanced features)

## Current Position

Phase: 4 of 4 (Kalshi Market Comparison and Edge Analysis)
Plan: 2 of 2 in current phase (all complete)
Status: v1 milestone complete -- all 22 requirements satisfied
Last activity: 2026-03-29 -- Completed 04-02-PLAN.md (Phase 4 notebooks)

Progress: [==========] 100% (10/10 plans overall)

## Performance Metrics

**Velocity:**
- Total plans completed: 10
- Average duration: 14min
- Total execution time: 2.3 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
| Phase 01 P01 | 9min | 3 tasks | 17 files |
| Phase 01 P02 | 3min | 2 tasks | 5 files |
| Phase 01 P03 | 53min | 3 tasks | 7 files |
| Phase 02 P01 | 4min | 3 tasks | 6 files |
| Phase 02 P02 | 7min | 2 tasks | 4 files |
| Phase 02 P03 | 34min | 3 tasks | 5 files |
| Phase 03 P01 | 5min | 3 tasks | 8 files |
| Phase 03 P02 | 10min | 2 tasks | 3 files |
| Phase 04 P01 | 5min | 2 tasks | 6 files |
| Phase 04 P02 | 5min | 3 tasks | 2 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Four-phase structure following strict data pipeline dependency chain (ingest -> features -> models -> market comparison)
- [Roadmap]: Live prediction pipeline deferred to v2 (requires all v1 components proven first)
- [Roadmap]: MODEL and EVAL requirements combined into Phase 3 (evaluation is inseparable from training -- together they answer "do the models work?")
- [Phase 01]: Upgraded pyarrow from 14.0.2 to >=15.0.0 due to numpy 2.x incompatibility
- [Phase 01]: Anchored /data/ in .gitignore to avoid matching src/data/
- [Phase 01]: Created full cache.py in Task 1 because verification required importable functions
- [Phase 01 P02]: Import aliases match test mock targets for clean patching (pybaseball_team_batting, etc.)
- [Phase 01 P02]: sp_stats cache key includes _mings{min_gs} suffix to prevent stale data across filter thresholds
- [Phase 01 P03]: Disabled Kalshi historical endpoint -- no series_ticker filter causes unbounded pagination (19+ min). KXMLBGAME live endpoint returns all 4,474 raw markets (2,237 games) in seconds.
- [Phase 01 P03]: KXMLB (championship futures, 30 markets) is wrong series -- correct series is KXMLBGAME (confirmed from web UI URL). Coverage: 2,237 unique games, Apr 2025-present, home win rate 53.5%.
- [Phase 01 P03]: Ticker-based team parsing -- both sides of a game share identical title text; team unambiguous only from ticker suffix (KXMLBGAME-25APR15NYYBOS-BOS -> home=BOS, away=NYY). One row per game via home-YES dedup.
- [Phase 01 P03]: last_price_dollars is settlement closing price, not pre-game opening price -- Phase 4 blocker documented in Blockers/Concerns
- [Phase 02 P01]: Used RESEARCH.md park factor estimates (FanGraphs Guts approximations) since FanGraphs was inaccessible for live verification
- [Phase 02 P01]: fetch_all_team_game_logs returns list[tuple[int, str]] of failures for caller surfacing without log inspection
- [Phase 02 P01]: Wave 0 stubs use module-level importorskip -- entire module skipped when feature_builder not yet implemented
- [Phase 02 P02]: SP recent form uses pitching_stats_range() for 30-day ERA window per CONTEXT.md locked decision (not season ERA)
- [Phase 02 P02]: Bullpen relievers identified by GS < 3 AND IP >= 5 (excludes position players who pitched in blowouts)
- [Phase 02 P02]: Log5 win probability derived from game-by-game cumulative win% with shift(1), not season-level W-L aggregate
- [Phase 02 P02]: Pythagorean win% uses schedule-derived runs (home_score/away_score per team per season)
- [Phase 02 P02]: Statcast xwOBA joined via first_name + last_name concatenation to match schedule pitcher names
- [Phase 02 P03]: Replaced pybaseball BRef scraper with MLB Stats API (statsapi) for team game logs -- BRef now behind Cloudflare JS-challenge (HTTP 403)
- [Phase 02 P03]: OPS column resolution in _add_rolling_features() uses lowercase 'ops' with fallback to uppercase and obp+slg computation for backward compatibility
- [Phase 03 P01]: Used IsotonicRegression directly instead of deprecated CalibratedClassifierCV(cv='prefit') for sklearn 1.8.0 compatibility
- [Phase 03 P01]: Omitted penalty= from LogisticRegression (deprecated sklearn 1.8.0) and use_label_encoder from XGBClassifier (removed xgboost 2.x)
- [Phase 03 P01]: Excluded xwoba_diff from all feature sets (100% NaN); core set differentiates on sp_recent_era_diff only. Root cause confirmed post-Phase 3: two bugs in feature_builder.py _add_advanced_features() -- (1) pybaseball statcast_pitcher_expected_stats returns a single column named 'last_name, first_name' (not separate 'last_name'/'first_name' cols), so both branch conditions are always False and xwoba_lookup is never populated; (2) xwOBA column is 'est_woba' not 'xwoba'/'xwOBA'. Decision: leave excluded; fix deferred to post-Phase 4 iteration or V2 to avoid Phase 3/Phase 4 feature set inconsistency.
- [Phase 03 P01]: XGBoost early stopping uses last 20% of training window (temporal split), not calibration season
- [Phase 03 P01]: feature_set_name is explicit string parameter, not derived from column contents
- [Phase 03 P02]: No new decisions -- notebooks follow established thin-wrapper pattern from Phases 1 and 2
- [Phase 04 P01]: predict_2025 follows exact backtest.py pattern: rolling_ops_diff NaN filter, XGBoost early stopping on temporal 20% split, isotonic calibration
- [Phase 04 P01]: fetch_kalshi_open_prices groups requests by date for batch candlestick API efficiency (one call per game day)
- [Phase 04 P01]: Fixed np.True_ identity check in test assertions (use == instead of is for numpy booleans)
- [Phase 04 P02]: No new decisions -- notebooks follow established thin-wrapper pattern and use library code from Plan 01

### Pending Todos

None yet.

### Blockers/Concerns

- [Research]: pandas must stay at 2.2.x (not 3.0) due to pybaseball incompatibility with PyArrow string dtypes
- [Research]: Kalshi historical data only available from 2025 -- Phase 4 comparison limited to ~1 season
- [Research]: 2020 60-game season may need exclusion or era-flagging -- decision needed during Phase 1
- [Phase 4 Blocker -- RESOLVED]: fetch_kalshi_open_prices() now fetches pre-game opening price via batch candlestick API (GET /markets/candlesticks with period_interval=1440). kalshi_open_price column added alongside existing kalshi_yes_price (closing). Falls back to NaN where no candlestick data available.

## Session Continuity

Last session: 2026-03-29T15:02:37.445Z
Stopped at: Completed 04-02-PLAN.md (v1 milestone complete)
Resume file: None
