---
title: dbx_fanout_fasttrack_2026-07-20
type: note
permalink: dqverify-repo-20261013/tools/crcp/reports/dbx-fanout-fasttrack-2026-07-20
---

# CRCP Databricks fast-track — 2026-07-20

## Runs

| Wave | Run ID | Units | Result | Elapsed (agent) |
|------|--------|------:|--------|-----------------|
| P0 | 982136530224451 | 3 | TERMINATED SUCCESS | (earlier) |
| P1+W1+W2 | 690432742789715 | 15 | TERMINATED SUCCESS | **559.6s** after setup; **15/15 SUCCESS**, 0 rate_limited |

Host: r5d.2xlarge (66.7 GB), concurrency 12, stagger 3.0s, codex-cli 0.144.6.

## Applied into `tools/crcp`

- Backups: `scratch/crcp-e2e-p0-fanout/apply_backups/20260720_075257`
- Smoke imports: **23/23 OK**
- Contract tests: **21/21 OK** (`scripts/run_contract_tests.py`)
- Golden journey #1: **PASS**

### New / updated modules (high level)

| Area | Modules |
|------|---------|
| P0 durability | `spool.py`, `singleton.py`, `sse_validate.py` (+ FULL `redact.py`) |
| P1 auth/bus/http | `credential_snapshot.py`, `delivery_worker.py`, `http_secure.py`, `dead_letter.py`, patched `bridge`/`bus`/`sentinel`/`write_path`/`live_bridge` |
| P1 envelope | `envelope.py`, `envelope_v11.py`, `artifact_store.py`, `event_spool.py` |
| W1 | `capabilities.py`, `lifecycle.py`, `tests/*` |
| W2 | `traces.py`, `slo.py`, `reconcile.py`, `fault_inject.py`, `wfmon_export.py`, `rails/*`, `golden_journey_1.py` |

Agent reports: `reports/dbx_*.md`.

## Residual integration risk (honest)

Parallel agents wrote **self-contained modules** plus some full-file overwrites. Cross-wiring is incomplete:

- `live_bridge.py` from FULL may not import P0 `spool`/`singleton` (modules present; wiring may need a merge pass).
- `write_path` / `sse_validate` vs `sse_contract` naming may need a single classification entrypoint.
- Flat-import tests assumed job-node layout; local runner fixed via `PYTHONPATH` + `run_contract_tests.py`.

**Next local step:** one orchestrator merge pass — wire spool lifecycle into `cycle_once`, unify SSE classify API, smoke `python -m crcp health` / live once.

## Re-run

```text
python scratch/crcp-e2e-p0-fanout/build_and_submit.py          # P0 only
python scratch/crcp-e2e-p0-fanout/build_full_phase_batch.py    # P1+W1+W2
python scratch/crcp-e2e-p0-fanout/harvest_recursive.py
python scratch/crcp-e2e-p0-fanout/apply_to_crcp.py
```