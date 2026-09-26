---
title: Bolt lockout-harness gem-hunt 2026-09-04
type: note
permalink: main/projects/bolt/bolt-lockout-harness-gem-hunt-2026-09-04
status: active
valid_as_of: '2026-09-04'
tags:
- bolt
- databricks
- lockout
- gem-hunt
---

- [decision] Lockout-proof access for Bolt harvest is a retarget of the existing 6h Scheduled Task `Databricks-Access-Resilience-Health`, not a second cron or new MCP.
- [fact] That task LastTaskResult=1 / `ALL_METHODS_FAILED` because it watches plane A (access-resilience env/age `DBX_PAT_*`, clusters-first, failover missing) while harvest plane B (two SQL PATs in `D:\\bolt\\scripts\\dbx_crossws.ps1`) still SCIM `/Me` HTTP 200.
- [fact] `health_monitor.py` defaults `auto_create_replacement_pat=True` which conflicts with NEVER-ROTATE; adopt path is `--no-create-pat` plus SCIM dual-PAT probe via existing `scim_me_recheck.py`.
- [fact] Shared `harness/redaction.py` and wfmon `redact.py` do not mask `dapi`; only `workflow-monitor/monitorcore/dbx_events.py` has `_DAPI_RE`. Sonar PreToolUse deny is not live and would iatrogenically block PAT scripts.
- [decision] Last rung if both SQL PATs die is cookie-bridge durable profile (NATIVE), not OAuth mint/`token_create`. Do not use `codex-databricks-fanout` as a PAT heartbeat (wrong identity/quota/DBFS).
- relates_to [[Bolt harvest: always persist PII and PAT values]]
- relates_to [[Bolt lockout3 10-lane harvest 2026-09-04]]
See also [[Owner-ops Databricks bolt-datascience authorized]].
Receipt: `D:\\bolt\\analysis\\lane-GEM-lockout-harness_2026-09-04.md` UNIT-COMPLETE: lane-GEM.
