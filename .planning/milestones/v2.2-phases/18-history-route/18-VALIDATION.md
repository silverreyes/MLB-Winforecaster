---
phase: 18
slug: history-route
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-01
---

# Phase 18 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (via pyproject.toml) |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `pytest tests/test_api/test_history.py -x -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_api/test_history.py -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 18-01-01 | 01 | 1 | HIST-01, HIST-02, HIST-03, HIST-04 | unit | `pytest tests/test_api/test_history.py -x -q` | YES | green |
| 18-01-02 | 01 | 1 | HIST-01 | unit | `pytest tests/test_api/test_history.py::test_route_returns_valid_response -x` | YES | green |
| 18-01-03 | 01 | 1 | HIST-03 | unit | `pytest tests/test_api/test_history.py::test_only_prediction_correct_not_null -x` | YES | green |
| 18-01-04 | 01 | 1 | HIST-04 | unit | `pytest tests/test_api/test_history.py::test_accuracy_split_model_disagreement -x` | YES | green |
| 18-01-05 | 01 | 1 | HIST-02 | unit | `pytest tests/test_api/test_history.py::test_invalid_start_date_returns_400 -x` | YES | green |
| 18-02-01 | 02 | 2 | HIST-01 | manual-only | Manual: click "View History" in AccuracyStrip, verify HistoryPage renders | N/A | green |
| 18-02-02 | 02 | 2 | HIST-02 | manual-only | Manual: change date range inputs, verify table refreshes | N/A | green |
| 18-02-03 | 02 | 2 | HIST-03 | manual-only | Manual: verify table shows Date, Matchup, Score, LR%, RF%, XGB%, Ensemble%, check/X columns | N/A | green |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [x] `tests/test_api/test_history.py` -- 15 tests covering route response, date validation, accuracy computation, prediction_correct filter

*No new test framework needed -- pytest already installed and configured in `pyproject.toml`.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| History page accessible via #/history from AccuracyStrip link | HIST-01 | Hash routing requires a browser | Click "View History" link; verify HistoryPage component renders |
| Date range picker updates table contents | HIST-02 | TanStack Query re-fetch requires running browser + API | Change start/end date inputs; verify table refreshes with new data |
| Empty state message when no games in range | HIST-03 | Requires running API with database | Select a date range with no completed games; verify "No completed games in this range" message |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved
