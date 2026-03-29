---
phase: 5
slug: sp-feature-integration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-29
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (installed, working) |
| **Config file** | None (uses defaults) |
| **Quick run command** | `python -m pytest tests/test_feature_builder.py tests/test_leakage.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~30 seconds (unit + integration) |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_feature_builder.py tests/test_leakage.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 5-01-01 | 01 | 0 | SP-01, SP-02 | unit | `python -m pytest tests/test_sp_id_bridge.py -x` | ❌ W0 | ⬜ pending |
| 5-01-02 | 01 | 0 | SP-01 | unit | `python -m pytest tests/test_feature_builder.py::test_xwoba_fix -x` | ❌ W0 | ⬜ pending |
| 5-01-03 | 01 | 1 | SP-02 | unit | `python -m pytest tests/test_sp_id_bridge.py -x` | ❌ W0 | ⬜ pending |
| 5-01-04 | 01 | 1 | SP-01 | unit | `python -m pytest tests/test_feature_builder.py::test_xwoba_fix -x` | ❌ W0 | ⬜ pending |
| 5-02-01 | 02 | 0 | SP-07, SP-08 | unit | `python -m pytest tests/test_sp_recent_form.py -x` | ❌ W0 | ⬜ pending |
| 5-02-02 | 02 | 1 | SP-07 | unit | `python -m pytest tests/test_feature_builder.py::test_recent_fip_diff -x` | ❌ W0 | ⬜ pending |
| 5-02-03 | 02 | 1 | SP-08 | unit | `python -m pytest tests/test_feature_builder.py::test_pitch_count_days_rest -x` | ❌ W0 | ⬜ pending |
| 5-03-01 | 03 | 0 | SP-03–SP-06, SP-09–SP-12 | unit | `python -m pytest tests/test_feature_builder.py -x -q` | ❌ W0 | ⬜ pending |
| 5-03-02 | 03 | 1 | SP-03, SP-12 | integration | `python -m pytest tests/test_leakage.py::test_sp_std_no_leakage tests/test_leakage.py::test_sp_temporal_safety -x` | ❌ W0 | ⬜ pending |
| 5-03-03 | 03 | 1 | SP-04 | unit | `python -m pytest tests/test_feature_builder.py::test_k_bb_pct_diff -x` | ❌ W0 | ⬜ pending |
| 5-03-04 | 03 | 1 | SP-05 | unit | `python -m pytest tests/test_feature_builder.py::test_whip_diff -x` | ❌ W0 | ⬜ pending |
| 5-03-05 | 03 | 1 | SP-06 | unit | `python -m pytest tests/test_feature_builder.py::test_era_diff -x` | ❌ W0 | ⬜ pending |
| 5-03-06 | 03 | 1 | SP-09 | unit | `python -m pytest tests/test_feature_builder.py::test_feature_set_constants -x` | ❌ W0 | ⬜ pending |
| 5-03-07 | 03 | 1 | SP-10 | unit | `python -m pytest tests/test_feature_builder.py::test_cold_start -x` | ❌ W0 | ⬜ pending |
| 5-03-08 | 03 | 2 | SP-11 | integration | `python -m pytest tests/test_feature_builder.py::test_v2_parquet_output -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_sp_id_bridge.py` — stubs for SP-02 (ID bridge unit tests: Chadwick lookup, accent normalization, override dict)
- [ ] New test functions in `tests/test_feature_builder.py` — stubs for SP-01 (xwOBA fix), SP-04 (K-BB%), SP-05 (WHIP diff), SP-06 (ERA diff), SP-07 (recent FIP diff), SP-08 (pitch count + days rest), SP-09 (feature set constants), SP-10 (cold-start), SP-11 (v2 parquet output)
- [ ] New test functions in `tests/test_leakage.py` — stubs for SP-03 (season-to-date no leakage), SP-12 (temporal safety: columns change game-to-game)
- [ ] `tests/test_sp_recent_form.py` — stubs for extended game log extraction (strikeOuts, baseOnBalls, homeRuns, numberOfPitches fields)

*All Wave 0 stubs use `pytest.importorskip` or `pytest.mark.skip` on the unimplemented functions — stubs must FAIL (not ERROR) so the test runner continues.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `feature_store_v2.parquet` written with correct shape | SP-11 | Requires running full pipeline; shape depends on data volume | Run `python -c "import pandas as pd; df=pd.read_parquet('data/cache/feature_store_v2.parquet'); print(df.shape, df.columns.tolist())"` after Phase 5 complete |
| Cold-start imputation covers rookies + call-ups | SP-10 | Requires real player data (e.g., 2024 debut pitchers) | Check that 0 rows have NaN in SP feature columns after build_feature_store() runs on 2024 season |
| xwOBA non-NaN rate for Statcast-covered starters | SP-01 | Depends on Statcast coverage (~85% of starters) | `df['xwoba_diff'].notna().sum()` on feature_store_v2; expect >85% non-NaN for post-2015 seasons |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
