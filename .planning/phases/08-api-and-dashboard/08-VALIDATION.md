---
phase: 8
slug: api-and-dashboard
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-29
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.1.1 (already installed) |
| **Config file** | none — existing discovery from repo root |
| **Quick run command** | `pytest tests/test_api/ -x -q` |
| **Full suite command** | `pytest tests/ -x -q && cd frontend && npm run build` |
| **Estimated runtime** | ~15 seconds (API tests); ~60 seconds (full + frontend build) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_api/ -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q && cd frontend && npm run build`
- **Before `/gsd:verify-work`:** Full suite must be green + frontend build must succeed
- **Max feedback latency:** 15 seconds (API unit tests)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 08-??-API-01 | TBD | 1 | API-01 | unit | `pytest tests/test_api/test_predictions.py::test_today_endpoint -x` | ❌ W0 | ⬜ pending |
| 08-??-API-02 | TBD | 1 | API-02 | unit | `pytest tests/test_api/test_predictions.py::test_date_endpoint -x` | ❌ W0 | ⬜ pending |
| 08-??-API-03 | TBD | 1 | API-03 | unit | `pytest tests/test_api/test_predictions.py::test_latest_timestamp -x` | ❌ W0 | ⬜ pending |
| 08-??-API-04 | TBD | 1 | API-04 | unit | `pytest tests/test_api/test_accuracy.py -x` | ❌ W0 | ⬜ pending |
| 08-??-API-05 | TBD | 1 | API-05 | unit | `pytest tests/test_api/test_health_endpoint.py -x` | ❌ W0 | ⬜ pending |
| 08-??-API-06 | TBD | 1 | API-06 | unit | `pytest tests/test_api/test_lifespan.py::test_missing_artifact_fails -x` | ❌ W0 | ⬜ pending |
| 08-??-DASH-01 | TBD | 2 | DASH-01 | smoke | `cd frontend && npm run build` | ❌ W0 | ⬜ pending |
| 08-??-DASH-02 | TBD | 2 | DASH-02 | manual | Visual inspection of GameCard rendering both prediction versions | N/A | ⬜ pending |
| 08-??-DASH-03 | TBD | 2 | DASH-03 | manual | Visual inspection of KalshiSection edge badge | N/A | ⬜ pending |
| 08-??-DASH-04 | TBD | 2 | DASH-04 | manual | Visual inspection of SpBadge TBD and warning states | N/A | ⬜ pending |
| 08-??-DASH-05 | TBD | 2 | DASH-05 | manual | Visual inspection with mock data older than 3 hours | N/A | ⬜ pending |
| 08-??-DASH-06 | TBD | 2 | DASH-06 | manual | Manual tab switching + network tab observation | N/A | ⬜ pending |
| 08-??-DASH-07 | TBD | 2 | DASH-07 | manual | Kill API server, observe dashboard error state | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_api/` directory — new test directory for API endpoint tests
- [ ] `tests/test_api/__init__.py` — package init
- [ ] `tests/test_api/conftest.py` — FastAPI TestClient fixture with mocked pool/artifacts
- [ ] `tests/test_api/test_predictions.py` — covers API-01, API-02, API-03
- [ ] `tests/test_api/test_accuracy.py` — covers API-04
- [ ] `tests/test_api/test_health_endpoint.py` — covers API-05
- [ ] `tests/test_api/test_lifespan.py` — covers API-06
- [ ] `httpx` added to dev dependencies — required for FastAPI TestClient

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| GameCard renders both prediction versions side-by-side | DASH-02 | No React component test framework in scope | Inspect dashboard in browser with real/mock data; verify pre-lineup and post-lineup columns both render with LR/RF/XGB probabilities |
| KalshiSection renders edge badge (BUY_YES/BUY_NO/NO_EDGE) | DASH-03 | No component test framework | Inspect dashboard; verify badge color and label match UI-SPEC for each edge state |
| SpBadge shows "TBD" with visual flag when starter unconfirmed | DASH-04 | No component test framework | Inspect dashboard with game where `confirmed=false`; verify TBD badge renders with warning color |
| Prediction cards grayed out after 3-hour staleness threshold | DASH-05 | Requires time-sensitive mock data | Set mock data timestamp to 4+ hours ago; verify cards show staleness overlay and indicator text |
| Polling fires every 60s when visible, suspends when hidden | DASH-06 | Browser tab visibility cannot be tested headlessly | Open Network tab, switch tabs, verify requests pause; return, verify polling resumes |
| "Dashboard offline" error state when API unreachable | DASH-07 | Requires simulating network failure | Kill API server; reload dashboard; verify error state renders with last-known data and timestamp |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
