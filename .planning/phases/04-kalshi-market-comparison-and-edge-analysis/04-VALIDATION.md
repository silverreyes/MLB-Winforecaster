---
phase: 4
slug: kalshi-market-comparison-and-edge-analysis
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-29
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | {path or "none — Wave 0 installs"} |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 1 | MARKET-01 | unit | `pytest tests/ -x -q` | ❌ W0 | ⬜ pending |
| 4-01-02 | 01 | 1 | MARKET-01 | unit | `pytest tests/ -x -q` | ❌ W0 | ⬜ pending |
| 4-02-01 | 02 | 2 | MARKET-02 | unit | `pytest tests/ -x -q` | ❌ W0 | ⬜ pending |
| 4-02-02 | 02 | 2 | MARKET-02 | unit | `pytest tests/ -x -q` | ❌ W0 | ⬜ pending |
| 4-03-01 | 03 | 3 | MARKET-03 | unit | `pytest tests/ -x -q` | ❌ W0 | ⬜ pending |
| 4-03-02 | 03 | 3 | MARKET-04 | unit | `pytest tests/ -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_kalshi.py` — stubs for MARKET-01 (Kalshi price fetch and join)
- [ ] `tests/test_edge_analysis.py` — stubs for MARKET-02, MARKET-03, MARKET-04
- [ ] `tests/conftest.py` — shared fixtures (sample feature matrix, sample Kalshi data)

*Existing pytest infrastructure from Phases 1-3 may already be present.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Notebook output shows correct edge table with fee adjustment | MARKET-03, MARKET-04 | Visual review of Jupyter notebook output required | Open notebook, run all cells, verify edge table has fee_adjusted_edge column and no rows where edge ignores fees |
| Brier score comparison correctly isolates 2025 games only | MARKET-02 | Data boundary validation — requires human review of game count | Verify notebook prints game count for Kalshi comparison section and it matches only 2025 games |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
