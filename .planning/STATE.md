---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: in-progress
stopped_at: Completed 03-01-PLAN.md
last_updated: "2026-03-29T07:38:27Z"
last_activity: 2026-03-29 -- Completed 03-01-PLAN.md (model training library)
progress:
  total_phases: 4
  completed_phases: 2
  total_plans: 8
  completed_plans: 7
  percent: 88
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-28)

**Core value:** Produce well-calibrated win probability estimates that can be rigorously compared against Kalshi market prices, surfacing where models agree, disagree, and where edges may exist.
**Current focus:** Phase 3 in progress -- model training library complete, notebooks next

## Current Position

Phase: 3 of 4 (Model Training and Backtesting)
Plan: 1 of 2 in current phase (03-01 complete)
Status: 03-01 complete -- ready for 03-02 (notebooks)
Last activity: 2026-03-29 -- Completed 03-01-PLAN.md (model training library)

Progress: [=========.] 88% (7/8 plans overall)

## Performance Metrics

**Velocity:**
- Total plans completed: 7
- Average duration: 16min
- Total execution time: 1.92 hours

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
- [Phase 03 P01]: Excluded xwoba_diff from all feature sets (100% NaN); core set differentiates on sp_recent_era_diff only
- [Phase 03 P01]: XGBoost early stopping uses last 20% of training window (temporal split), not calibration season
- [Phase 03 P01]: feature_set_name is explicit string parameter, not derived from column contents

### Pending Todos

None yet.

### Blockers/Concerns

- [Research]: pandas must stay at 2.2.x (not 3.0) due to pybaseball incompatibility with PyArrow string dtypes
- [Research]: Kalshi historical data only available from 2025 -- Phase 4 comparison limited to ~1 season
- [Research]: 2020 60-game season may need exclusion or era-flagging -- decision needed during Phase 1
- [Phase 4 Blocker]: `fetch_kalshi_markets()` stores `last_price_dollars` (settlement closing price). Phase 4 benchmark requires PRE-GAME market price to avoid look-ahead bias. Must investigate Kalshi candlestick/trade-history API before Phase 4 planning. See `<known_issues>` block in `01-03-PLAN.md`.

## Session Continuity

Last session: 2026-03-29T07:38:27Z
Stopped at: Completed 03-01-PLAN.md
Resume file: .planning/phases/03-model-training-and-backtesting/03-01-SUMMARY.md
