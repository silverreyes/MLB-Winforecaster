---
phase: 9
slug: infrastructure-and-go-live
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-29
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | bash / shell scripts (infrastructure validation) |
| **Config file** | none — verification via CLI commands |
| **Quick run command** | `docker compose config --quiet && echo OK` |
| **Full suite command** | `bash scripts/memory-audit.sh && docker compose config --quiet && nginx -t` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `docker compose config --quiet && echo OK`
- **After every plan wave:** Run `bash scripts/memory-audit.sh && docker compose config --quiet && nginx -t`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 9-01-01 | 01 | 1 | INFRA-01 | infra | `docker compose config --quiet` | ❌ W0 | ⬜ pending |
| 9-01-02 | 01 | 1 | INFRA-01 | infra | `bash scripts/memory-audit.sh` | ❌ W0 | ⬜ pending |
| 9-02-01 | 02 | 2 | INFRA-02 | manual | `nginx -t` (on VPS) | ❌ W0 | ⬜ pending |
| 9-02-02 | 02 | 2 | INFRA-02 | manual | `certbot renew --dry-run` (on VPS) | ❌ W0 | ⬜ pending |
| 9-03-01 | 03 | 2 | INFRA-03 | manual | `docker volume ls \| grep mlb_pgdata` | ❌ W0 | ⬜ pending |
| 9-03-02 | 03 | 2 | INFRA-03 | infra | `bash scripts/backup.sh && ls /opt/backups/mlb/` | ❌ W0 | ⬜ pending |
| 9-04-01 | 04 | 3 | PORT-01 | manual | browser verify at silverreyes.net/mlb-winforecaster | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `scripts/memory-audit.sh` — INFRA-01 hard gate: check VPS memory headroom before deploy
- [ ] `scripts/backup.sh` — INFRA-03: pg_dump with 7-day retention
- [ ] `Dockerfile` — multi-stage build for api/worker
- [ ] `docker-compose.yml` — with mem_limit values

*Existing infrastructure: None — all files are new for this phase.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SSL cert active and serving HTTPS | INFRA-02 | Requires live VPS + DNS A record | curl -I https://mlbforecaster.silverreyes.net; check 200 OK |
| Certbot renewal dry-run | INFRA-02 | Requires VPS access | ssh VPS; certbot renew --dry-run |
| Postgres volume persists after stop/start | INFRA-03 | Requires running Docker stack | docker compose stop; docker compose start; verify data intact |
| Portfolio page renders correctly | PORT-01 | Browser visual verification | Open silverreyes.net/mlb-winforecaster; verify table + images |
| docker stats shows headroom | INFRA-01 | Requires live containers | docker stats --no-stream; confirm <~5.5GB used |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
