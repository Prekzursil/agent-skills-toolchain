# lane-53 / 03 — Gateway sentinel check

- **Date:** 2026-10-04 (UTC, pre-flight window).
- **Scope item:** final-round pre-flight part (d).
- **Method:** `curl -s -o /dev/null --max-time 5 -w 'status=%{http_code} time=%{time_total}s\n'` against the container gateway per CONVENTIONS.md; two probes spaced >1.2 s (pacing rule honored).

## Probes

| Probe | URL | Expected | Observed | Latency | curl exit |
|---|---|---|---|---|---|
| 1 (root) | `http://172.17.0.1:31100/` | HTTP 404 | **404** | 0.006 s | 0 |
| 2 (/mcp) | `http://172.17.0.1:31100/mcp` | HTTP 406 | **406** | 0.014 s | 0 |

## Deviation handling

- Both probes matched expected codes exactly → **no deviation** → per protocol, `harness_bridge_status` was **NOT run** (reserved for deviation only, with ≥90 s capture window).

## Result

**PART (d): PASS.** Gateway sentinel nominal (404 root / 406 mcp); harness bridge healthy by convention.

*Leak-gate: n/a (no credential material in scope).*
