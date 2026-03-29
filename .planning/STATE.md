---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Live Platform
status: executing
last_updated: "2026-03-29T20:27:27.000Z"
last_activity: 2026-03-29 -- Completed 05-02 (extended game log v2 + FIP + pitch count)
progress:
  total_phases: 5
  completed_phases: 0
  total_plans: 4
  completed_plans: 2
  percent: 10
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-29 -- v2.0 milestone started)

**Core value:** Produce well-calibrated win probability estimates that can be rigorously compared against Kalshi market prices, surfacing where models agree, disagree, and where edges may exist.
**Current focus:** Phase 5 -- SP Feature Integration

## Current Position

Phase: 5 of 9 (SP Feature Integration)
Plan: 2 of 4 in current phase
Status: Executing
Last activity: 2026-03-29 -- Completed 05-02 (extended game log v2 + FIP + pitch count)

Progress: [====......] 10%

## Performance Metrics

**Velocity (v1.0):**
- Total plans completed: 10
- Average duration: 14min
- Total execution time: 2.3 hours

**By Phase (v2.0):**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 5 (SP Feature Integration) | 2/4 | 11min | 5.5min |

**Recent Trend (v1.0):**
- Last 5 plans: 34min, 5min, 10min, 5min, 5min
- Trend: Stable

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [v2.0 Roadmap]: 5-phase structure (5-9) following strict dependency chain: SP features -> model retrain -> pipeline -> API+dashboard -> infrastructure
- [v2.0 Roadmap]: API and Dashboard combined into Phase 8 (developed and tested together)
- [v2.0 Roadmap]: Infrastructure and Portfolio combined into Phase 9 (deploy last after local validation)
- [v2.0 Roadmap]: 5pm ET confirmation run is a third daily cron job (full pipeline re-run, not just flag update)
- [v2.0 Roadmap]: IsotonicRegression is the settled calibration method; temperature scaling only if reliability diagrams show problems
- [v2.0 Roadmap]: Memory limit audit (INFRA-01) is a hard gate BEFORE first VPS deploy
- [05-01]: 5-tier SP name resolution chain (exact -> override -> accent-strip -> ID bridge -> FG name lookup)
- [05-01]: Chadwick register cached via existing cache infrastructure for ID bridge Tier 1
- [05-02]: Versioned cache key (pitcher_game_log_v2_) prevents stale 3-column cache reuse
- [05-02]: Raw FIP formula (no cFIP constant) -- cancels in home-away differentials
- [05-02]: Cold-start imputation: 93 pitches (league avg), 7 days rest cap

### Pending Todos

None yet.

### Blockers/Concerns

- [Carry-forward]: pandas must stay at 2.2.x (not 3.0) due to pybaseball incompatibility
- [Carry-forward]: Kalshi historical data only available from 2025 -- edge comparison limited to ~1 season
- [Research]: pybaseball curl_cffi fix may not be in pinned v2.2.7 -- test before Phase 5 begins
- [Research]: MLB Stats API game log field coverage needs inspection for K/BB/HR per game and numberOfPitches

## Session Continuity

Last session: 2026-03-29
Stopped at: Completed 05-02-PLAN.md (extended game log v2 + FIP + pitch count)
Resume file: None
