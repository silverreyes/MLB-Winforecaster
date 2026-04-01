---
phase: 15
slug: live-score-polling
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-31
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.1.1 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/test_pipeline/test_live_poller.py tests/test_api/test_games_live.py -x -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_pipeline/test_live_poller.py tests/test_api/test_games_live.py -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 15-01-01 | 01 | 0 | LIVE-01, LIVE-04–07, LIVE-08 | unit | `pytest tests/test_pipeline/test_live_poller.py tests/test_api/test_games_live.py -x -q` | YES | green |
| 15-02-01 | 02 | 1 | LIVE-01 | unit | `pytest tests/test_api/test_games_live.py::test_live_game_has_score -x` | YES | green |
| 15-02-02 | 02 | 1 | LIVE-01 | unit | `pytest tests/test_api/test_games_live.py::test_non_live_game_null_score -x` | YES | green |
| 15-02-03 | 02 | 1 | LIVE-04 | unit | `pytest tests/test_api/test_games_live.py::test_runners_parsed -x` | YES | green |
| 15-02-04 | 02 | 1 | LIVE-05 | unit | `pytest tests/test_api/test_games_live.py::test_count_parsed -x` | YES | green |
| 15-02-05 | 02 | 1 | LIVE-06 | unit | `pytest tests/test_api/test_games_live.py::test_batter_stats -x` | YES | green |
| 15-02-06 | 02 | 1 | LIVE-07 | unit | `pytest tests/test_api/test_games_live.py::test_on_deck_parsed -x` | YES | green |
| 15-03-01 | 03 | 1 | LIVE-08 | unit (mock DB) | `pytest tests/test_pipeline/test_live_poller.py::test_outcome_write_all_rows -x` | YES | green |
| 15-03-02 | 03 | 1 | LIVE-08 | unit (mock DB) | `pytest tests/test_pipeline/test_live_poller.py::test_prediction_correct -x` | YES | green |
| 15-03-03 | 03 | 1 | LIVE-08 | unit | `pytest tests/test_pipeline/test_live_poller.py::test_503_silent_skip -x` | YES | green |
| 15-03-04 | 03 | 1 | LIVE-08 | unit | `pytest tests/test_pipeline/test_live_poller.py::test_no_live_games_early_exit -x` | YES | green |
| 15-04-01 | 04 | 2 | LIVE-02 | manual-only | Manual: inspect useGames.ts `refetchInterval` logic | N/A | green |
| 15-04-02 | 04 | 2 | LIVE-03 | manual-only | Manual: visual verify ScoreRow renders only for LIVE status | N/A | green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_pipeline/test_live_poller.py` — stubs for LIVE-08 (poller job, outcome write, error handling, early exit)
- [x] `tests/test_api/test_games_live.py` — stubs for LIVE-01, LIVE-04, LIVE-05, LIVE-06, LIVE-07 (linescore parsing, API response enrichment)

*No new test framework needed — pytest already installed and configured in `pyproject.toml`.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `refetchInterval` returns 90000 when live games exist | LIVE-02 | No frontend test framework in project | Open browser DevTools → Network tab → confirm `/api/games` refetches every 90s while a LIVE game is present |
| `refetchInterval` returns `false` when no live games | LIVE-02 | No frontend test framework | With no LIVE games, confirm no polling requests appear in Network tab |
| ScoreRow renders only for LIVE status | LIVE-03 | No frontend test framework | Verify ScoreRow component is absent on Scheduled/Final cards, present on LIVE cards |
| BasesDiamond and pitch count display correctly | LIVE-04, LIVE-05 | Visual component verification | Expand an in-progress game card; verify diamond fills, balls/strikes/outs counters match API data |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved
