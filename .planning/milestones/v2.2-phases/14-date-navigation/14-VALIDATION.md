---
phase: 14
slug: date-navigation
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-31
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
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
| 14-01-01 | 01 | 1 | DATE-04, DATE-05, DATE-06, DATE-07, DATE-08 | unit | `pytest tests/test_api/test_games.py -x -q` | yes (extended by Plan 01) | pending |
| 14-02-01 | 02 | 2 | DATE-01, DATE-02, DATE-03, DATE-04, DATE-06 | compile | `cd frontend && npx tsc --noEmit` | N/A (type check) | pending |
| 14-02-02 | 02 | 2 | DATE-01, DATE-02, DATE-03 | compile | `cd frontend && npx tsc --noEmit` | N/A (type check) | pending |
| 14-03-01 | 03 | 3 | DATE-01, DATE-02, DATE-03, DATE-05, DATE-07, DATE-08 | compile | `cd frontend && npx tsc --noEmit` | N/A (type check) | pending |
| 14-03-02 | 03 | 3 | DATE-01, DATE-02, DATE-03, DATE-05, DATE-07, DATE-08 | manual | N/A -- browser interaction | N/A | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. Plan 01 extends `tests/test_api/test_games.py` with `TestDateNavigation` and `TestTomorrowPreliminary` classes. Plans 02 and 03 are frontend (TypeScript compile check + visual verification).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Date picker opens and allows jumping to arbitrary date | DATE-01 | Browser UI interaction | Open app, click date picker, select a non-today date, verify content updates |
| Arrow navigation prev/next day | DATE-01 | Browser UI interaction | Click left and right arrow controls, verify URL/content changes |
| Polling stops on past/future dates | DATE-03 | Network tab observation | Navigate to past date, open DevTools Network, verify no repeated `/games/` calls |
| FutureDateBanner renders with correct heading typography | DATE-07 | Visual check | Navigate to tomorrow/future date, verify banner heading matches 20px/600 spec |
| PRELIMINARY badge appears on confirmed-SP tomorrow games | DATE-05 | Visual check | Navigate to tomorrow, verify amber badge on games with both SPs confirmed |

*If none: "All phase behaviors have automated verification."*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or are manual-only with test instructions
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
