---
phase: 7
slug: live-pipeline-and-database
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-29
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pytest.ini or pyproject.toml [tool.pytest.ini_options] |
| **Quick run command** | `pytest tests/test_pipeline/ -x -q` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_pipeline/ -x -q`
- **After every plan wave:** Run `pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 7-01-01 | 01 | 1 | PIPE-01 | unit | `pytest tests/test_pipeline/test_schema.py -x -q` | ❌ W0 | ⬜ pending |
| 7-01-02 | 01 | 1 | PIPE-01 | integration | `pytest tests/test_pipeline/test_db.py -x -q` | ❌ W0 | ⬜ pending |
| 7-02-01 | 02 | 1 | PIPE-02, PIPE-03 | unit | `pytest tests/test_pipeline/test_live_features.py -x -q` | ❌ W0 | ⬜ pending |
| 7-02-02 | 02 | 1 | PIPE-04 | unit | `pytest tests/test_pipeline/test_inference.py -x -q` | ❌ W0 | ⬜ pending |
| 7-03-01 | 03 | 2 | PIPE-05 | unit | `pytest tests/test_pipeline/test_scheduler.py -x -q` | ❌ W0 | ⬜ pending |
| 7-03-02 | 03 | 2 | PIPE-06, PIPE-07 | integration | `pytest tests/test_pipeline/test_pipeline_runs.py -x -q` | ❌ W0 | ⬜ pending |
| 7-03-03 | 03 | 2 | PIPE-08 | unit | `pytest tests/test_pipeline/test_health_endpoint.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_pipeline/__init__.py` — test package init
- [ ] `tests/test_pipeline/test_schema.py` — stubs for PIPE-01 (predictions table schema, CHECK constraints)
- [ ] `tests/test_pipeline/test_db.py` — stubs for PIPE-01 (DB connection, migrations)
- [ ] `tests/test_pipeline/test_live_features.py` — stubs for PIPE-02, PIPE-03 (LiveFeatureBuilder, Kalshi live prices)
- [ ] `tests/test_pipeline/test_inference.py` — stubs for PIPE-04 (artifact loading, predict_proba calls)
- [ ] `tests/test_pipeline/test_scheduler.py` — stubs for PIPE-05 (APScheduler 10am/1pm/5pm ET cron triggers)
- [ ] `tests/test_pipeline/test_pipeline_runs.py` — stubs for PIPE-06, PIPE-07 (pre_lineup/post_lineup/confirmation run logic, is_latest flag, sp_may_have_changed)
- [ ] `tests/test_pipeline/test_health_endpoint.py` — stubs for PIPE-08 (GET /api/v1/health response shape)
- [ ] `tests/test_pipeline/conftest.py` — shared fixtures (test Postgres container via pytest-docker or monkeypatched engine)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 10am ET pipeline fires on correct schedule in production | PIPE-05 | Cannot simulate wall-clock cron in CI without time-mocking | Deploy to staging, observe cron log at 10am ET |
| FanGraphs data freshness / Cloudflare fallback | PIPE-02 | Depends on external service availability | Manually test pybaseball fetch, verify cache fallback triggers |
| Kalshi market not yet open at 10am ET | PIPE-03 | Market open time varies by day | Trigger pre_lineup run when market is closed; confirm NULL price + NO_EDGE stored |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
