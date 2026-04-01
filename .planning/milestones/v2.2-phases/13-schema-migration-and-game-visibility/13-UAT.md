---
status: diagnosed
phase: 13-schema-migration-and-game-visibility
source: [13-01-SUMMARY.md, 13-02-SUMMARY.md, 13-03-SUMMARY.md]
started: 2026-03-31T13:00:00Z
updated: 2026-03-31T13:00:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running server/service. Clear ephemeral state (temp DBs, caches, lock files). Start the application from scratch. The API server should boot without errors, the migration (migration_001.sql) should run and add game_id + reconciliation columns to the predictions table, and a basic API call (e.g. GET /api/v1/games/2026-03-31 or the health check) should return a live response without errors.
result: pass

### 2. All Games Visible
expected: The dashboard displays all scheduled games for today — not just games that have model predictions. If there are 15 games on the schedule, all 15 appear in the card grid, even if only some have win probability data.
result: pass

### 3. Status Badge — PRE-GAME
expected: Games scheduled for later today (not yet started) show a gray "PRE-GAME" badge on the card, positioned between the game time and the starting pitcher row.
result: pass

### 4. Status Badge — LIVE
expected: Games currently in progress show a green "LIVE" badge on the card.
result: skipped
reason: Can't test until games start this evening

### 5. Status Badge — FINAL
expected: Completed games show a "FINAL" badge on the card.
result: skipped
reason: Can't test; no games have completed yet today

### 6. Status Badge — POSTPONED
expected: Any postponed game shows an amber/yellow "POSTPONED" badge on the card.
result: skipped
reason: Can't test until there is an actually postponed game

### 7. Stub Cards (No Prediction)
expected: Games that don't have a model prediction render a stub card — the card shows the matchup (team vs team), game time, status badge, and "SP: TBD" (or equivalent), but does NOT show a win probability bar or a Kalshi comparison section. The card is visually distinct but still recognizable as a game entry.
result: pass
reason: Visually confirmed before 10am pipeline run; all games now have predictions so can no longer reproduce stub state

### 8. Full Prediction Cards
expected: Games that DO have a model prediction still show the full card layout — win probability, home/away percentages, the Kalshi comparison section — the same as before this phase. Nothing was broken for predicted games.
result: pass

## Summary

total: 8
passed: 5
issues: 2
pending: 0
skipped: 3

## Gaps

- truth: "apply_schema() runs migration_001.sql automatically on container startup with no manual intervention required"
  status: failed
  reason: "User reported: apply_schema() did not run migration_001.sql against the live Postgres database on container startup. The migration had to be applied manually."
  severity: major
  test: post-uat
  root_cause: "Two bugs: (1) migration_001.sql absent from [tool.setuptools.package-data] in pyproject.toml — not installed into site-packages when pip installs in non-editable mode, so migration_path.exists() returns False silently. (2) api/main.py lifespan never calls apply_schema() — only the worker does, leaving the api container unable to trigger migrations independently."
  artifacts:
    - path: "pyproject.toml"
      issue: "migration_001.sql not listed in [tool.setuptools.package-data]; only schema.sql is present"
    - path: "src/pipeline/db.py"
      issue: "migration_path.exists() guard silently skips the migration with no warning when file is absent"
    - path: "api/main.py"
      issue: "lifespan startup calls get_pool() but never apply_schema()"
  missing:
    - "Add migration_*.sql glob to pyproject.toml package-data"
    - "Call apply_schema(pool) in api/main.py lifespan startup block"
  debug_session: ""

- truth: "10am pre_lineup pipeline run populates confirmed starting pitchers for games where MLB.com lists confirmed SPs"
  status: failed
  reason: "User reported: SP: TBD for all 14 games despite MLB.com listing confirmed starters for many of them. Possibly related to full lineup not being set, but confirmed SPs should still appear."
  severity: minor
  test: post-uat
  root_cause: "By-design behavior. _process_pre_lineup() in runner.py hardcodes home_sp: None, away_sp: None unconditionally. The pre_lineup run uses TEAM_ONLY models which don't consume SP names as features; SP names are only stored at post_lineup (1pm) when SP_ENHANCED models use them. The probable pitcher data IS fetched from the API correctly — it is intentionally discarded. Changing to display pitcher names at 10am is a product decision, not a bug fix."
  artifacts:
    - path: "src/pipeline/runner.py"
      issue: "lines 167-168: home_sp and away_sp hardcoded to None in _process_pre_lineup(); probable pitcher data from API is discarded"
  missing:
    - "Product decision: pass game.get('home_probable_pitcher') / game.get('away_probable_pitcher') to insert_prediction in pre_lineup if UI display of confirmed SPs at 10am is desired (sp_uncertainty=True would remain set)"
  debug_session: ""
