---
status: complete
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
issues: 0
pending: 0
skipped: 3

## Gaps

[none yet]
