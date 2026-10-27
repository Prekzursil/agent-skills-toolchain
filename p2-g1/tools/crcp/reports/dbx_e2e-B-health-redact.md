# e2e-B-health-redact — P0 health and redaction

## Summary

Implemented secret-safe recursive redaction and metadata-only report filtering, split process liveness from poller readiness, added bounded operational metrics, and wired honest HTTP health endpoints into the live bridge. Readiness is RED when no poll has completed, the last poll is older than `2 * poll_interval + 60` seconds, auth is unusable, a sticky `last_error` exists, the service is stopped, or a lease is known lost. A stale or otherwise unready poller can no longer produce an overall GREEN health result.

## File list

- `redact.py` — new module with `redact_obj`, `redact_text`, and metadata-default `safe_report`; credential values are replaced by `[REDACTED]`.
- `health.py` — full replacement adding `livez`, `readyz`, `metrics`, readiness-aware `full_health`, and readiness/metrics output for wfmon.
- `live_bridge.py` — full replacement exposing the new probes and applying redaction to state, errors, cycle summaries, and HTTP JSON responses.
- `e2e-B-health-redact.md` — this unit report.

## Wiring notes

- Install `redact.py` beside the other `crcp` package modules. Report writers should persist `safe_report(report)` rather than the raw write-path result; the allowlist deliberately excludes response bodies, SSE event samples, titles, and conversation identifiers.
- `health.py` imports `.redact`. Its existing no-argument `full_health()` call remains valid and reads `reports/live_bridge_state.json`; missing state is treated as not ready rather than healthy.
- The bridge imports `livez`, `readyz`, and `metrics` from `.health`. `GET /livez` is cheap and returns 200. `GET /readyz` returns 200 only when ready and 503 otherwise. `GET /metrics` returns JSON counters/ages. Existing `/health` and `/api/health` remain HTTP 200 for compatibility, with an explicit `ok` or `not_ready` body.
- `last_error` clears only after a completely clean poll cycle. HTTP and persisted bridge data are passed through recursive redaction as defense in depth.
- The replacement remains compatible with the adjacent P0 spool/singleton integration present in the shared result directory.

## Self-test notes

- `python -m py_compile` passed for all three Python deliverables.
- Redaction tests covered every required key family plus Bearer, assignment, cookie-header, and JSON textual forms; the source secret was absent from sanitized output.
- Readiness tests covered fresh, stale, auth-bad, and sticky-error states, including the exact stale threshold behavior.
- Metrics tests covered backlog aggregation and poll/fetch/publish counters.
- An ephemeral loopback HTTP server verified `/livez` 200, fresh `/readyz` 200, stale `/readyz` 503, `/metrics` content, and compatibility `/health` reporting `not_ready` while returning 200.
- A sanitized `full_health` report rendered successfully through `health_table`.

UNIT-COMPLETE: e2e-B-health-redact
