---
title: dbx_w2-wfmon-metrics
type: note
permalink: dqverify-repo-20261013/tools/crcp/reports/dbx-w2-wfmon-metrics
---

# W2 wfmon metrics implementation

## Summary

Implemented a production-oriented, stdlib-only wfmon exporter. The v2 document preserves the prior compact feed fields (`source`, `probed_at`, `overall`, and `rails`) and adds:

- `readyz`: conservative auth, agent-mail, poll-freshness, lease, and optional backlog-age checks. Missing evidence is explicitly unknown and therefore not ready.
- `backlog`: read-only SQLite delivery counts, bytes, oldest active age, and per-state totals.
- `sse.uncertain`: uncertain accepted-write count from explicit metadata JSON inputs.
- `last_ack`: newest publish-state or durable-delivery acknowledgement and its age.
- `metrics`: flat cockpit-friendly values for backlog, SSE uncertainty, and ACK age.

All emitted data passes through credential-pattern redaction. Bearer values, JWT-shaped values, secret-bearing fields, and inline/query-style token assignments are removed. Writes use fsync plus atomic replacement and work on Windows and Linux.

## Files

- `wfmon_export.py` ÔÇö complete standalone exporter, collectors, readiness evaluator, atomic writer, drop-in snippet function, and CLI.
- `health.py` ÔÇö complete health module preserving existing probes/table behavior and delegating its existing `write_wfmon_snippet(report, path)` entry point to the operational exporter.
- `w2-wfmon-metrics.md` ÔÇö this implementation report.

## Wiring into existing modules

`crcp.__main__.cmd_health` already calls `health.write_wfmon_snippet(report, reports/wfmon_crcp_health.json)`. The delivered `health.py` keeps that signature, so no CLI change is required: overlay both Python files into the `crcp` package and the existing health command emits the v2 feed.

The exporter interoperates with the W1 delivery worker's `delivery.sqlite3` schema (`pending`, `leased`, `delivered`, `dead`) and the existing `.publish_state.json` format. It searches conventional CRCP delivery database locations, while CLI/function arguments allow explicit paths. SSE metrics are explicit inputs to avoid scanning arbitrary reports that may contain message content.

Direct operation is also supported:

```text
python -m crcp.wfmon_export --health reports/health_live.json --output reports/wfmon_crcp_health.json --root . --sse-metrics reports/slo_metrics.json
```

The CLI exits zero only when `readyz.ready` is true, making it suitable for a job or monitor gate.

## Self-tests

- `py_compile` passed for both delivered modules.
- 15 final assertions passed using temporary JSON and SQLite fixtures.
- Covered legacy top-level shape, fresh readiness, stale poll and lost lease failures, unknown-state degradation, active backlog item/byte/age aggregation, delivered ACK precedence, publish-state ACK fallback, uncertain SSE aggregation, atomic JSON round-trip, and redaction of Bearer/JWT/inline token forms.
- Package-overlay import of `crcp.health` and delegated `write_wfmon_snippet` was verified in an earlier integration smoke test.

UNIT-COMPLETE: w2-wfmon-metrics