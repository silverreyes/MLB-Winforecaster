---
phase: 17
slug: final-outcomes-and-nightly-reconciliation
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-31
---

# Phase 17 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `python -m pytest tests/test_pipeline/test_reconciliation.py tests/test_api/test_games_final.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_pipeline/test_reconciliation.py tests/test_api/test_games_final.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 17-01-01 | 01 | 1 | FINL-04 | unit | `python -m pytest tests/test_pipeline/test_reconciliation.py -x -q` | YES | green |
| 17-01-02 | 01 | 1 | FINL-04 | unit | `python -m pytest tests/test_pipeline/test_reconciliation.py::TestIdempotency -x -q` | YES | green |
| 17-02-01 | 02 | 2 | FINL-01 | unit | `python -m pytest tests/test_api/test_games_final.py::TestFinalScoreDisplay -x -q` | YES | green |
| 17-02-02 | 02 | 2 | FINL-02 | unit | `python -m pytest tests/test_api/test_games_final.py::TestFinalPredictionDisplay -x -q` | YES | green |
| 17-02-03 | 02 | 2 | FINL-03 | unit | `python -m pytest tests/test_api/test_games_final.py::TestOutcomeMarker -x -q` | YES | green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_pipeline/test_reconciliation.py` — stubs for FINL-04 (reconcile_outcomes function, nightly job, idempotency)
- [x] `tests/test_api/test_games_final.py` — stubs for FINL-01, FINL-02, FINL-03 (GameResponse with final scores, outcome marker)

*Existing test infrastructure covers the framework; only new test files are needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Outcome marker (✓/✗) renders correctly on FINAL game card | FINL-03 | Requires visual browser inspection | Load dashboard on a date with completed games; verify check/X marker appears on FINAL cards |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved
