# Merge C — health/readiness integration

## Result

Produced the full owned replacement `health.py` without modifying the read-only source tree or unrelated modules.

## Wiring completed

- Added `livez()` as a cheap process-local probe. It performs no filesystem, network, CLI, or authentication work.
- Added `readyz()` over `reports/live_bridge_state.json` with the canonical stale threshold `2 * poll_interval + 60s` (180 seconds at the default 60-second interval).
- Readiness is RED for missing/unreadable state, absent or stale `last_poll_at`, unhealthy Codex auth, or any truthy persisted `last_error`. The error remains a failing sticky condition until the poller clears it on a successful cycle.
- Added the required metrics snapshot fields: `polls`, `fetches`, `publishes`, and `last_poll_age_s`. Missing or invalid values remain unknown (`null`) rather than becoming healthy zeroes.
- Wired `full_health()` to call `readyz()` with the already-probed Codex auth result and to call `livez()` locally. Critical `codex_auth` or `agent_mail` failure makes overall health RED. With critical rails healthy, a bridge/poller failure is YELLOW; an expected missing poller can no longer produce fake GREEN. `poller_expected=False` is an explicit opt-out.
- Replaced the old ad hoc localhost `/health` request in `health_table()` with the readiness and persisted metrics already present in the report.
- Applied the existing `wfmon_export.redact()` helper to rail details, signals, and persisted error details before they can be emitted.
- Preserved the existing CLI call sites and API names used by `crcp.__main__`: `full_health()`, `health_table()`, and `write_wfmon_snippet()`.

## Call sites

- `crcp.__main__.cmd_health()` -> `full_health()` -> rail probes + `readyz()` + `livez()`.
- `full_health()` -> `readyz(state_path, poll_interval_seconds, poll_grace_seconds, auth_report)`.
- `health_table(report)` -> `report["readyz"]` and `report["metrics"]`; it no longer performs a second poller HTTP probe.
- `write_wfmon_snippet()` continues delegating to the existing operational `wfmon_export.write_wfmon_snippet()`.

## Validation

- Candidate file compiles with Python 3.11.
- All 21 existing contract tests pass with the job-node flat-module test path.
- Focused integration scenarios pass for fresh state, the exact 180-second boundary, stale state, missing state, sticky poll error, unhealthy auth, metrics projection, explicit non-expected poller behavior, table rendering, and secret redaction.

## Residual risk

- `live_bridge.py` does not persist its configured poll interval in `live_bridge_state.json`; callers using a non-default interval must pass the same value into `full_health()`/`readyz()` or freshness will be evaluated against 60 seconds.
- The existing `live_bridge.py` HTTP `/readyz` handler still uses its simpler in-memory `running && !last_error` rule. Updating that endpoint was outside this unit's exclusive `health.py` ownership, so the authoritative integrated semantics in this artifact are the `crcp.health.readyz()` result and downstream wfmon report.
- The poller currently makes top-level cycle failures sticky, but per-conversation fetch/publish errors are recorded only in the cycle summary and do not populate persisted `last_error`. Health cannot gate on errors that the owned state producer does not persist.

UNIT-COMPLETE: merge-C-health-ready
