# W2 JSONL traces and SLO counters

## Summary

Implemented two production-oriented, stdlib-only CRCP observability modules. The trace writer emits a fixed metadata-only JSONL schema, creates parent directories, serializes concurrent threads, optionally flushes records through `fsync`, and supports bounded size rotation. The SLO module provides thread-safe process-local poll counters, cumulative publish-latency buckets, an uncertain-SSE counter, and JSON-serializable wfmon snapshots.

No credential, token, payload, or SSE body fields are accepted by the trace API.

## File list

- `traces.py` — `JsonlTraceWriter`, unrotated `append_trace()` convenience API, validation, UTC timestamps, and optional `<trace>.1` through `<trace>.N` rotation.
- `slo.py` — `SloCounters`, default module-level recording helpers, and `export_metrics()`.
- `w2-jsonl-traces.md` — implementation and verification report.

## Wiring into existing modules

The unpacked `crcp` source was read-only, so this unit does not mutate it. During integration, place the modules at `crcp/traces.py` and `crcp/slo.py`, then wire them at these boundaries:

1. In `live_bridge.LiveBridgeService`, construct one `JsonlTraceWriter` and one `SloCounters` for the service lifetime. Call `record_poll(True)` only after a poll cycle finishes successfully and `record_poll(False)` on the outer polling exception path.
2. Measure each `bus.publish_envelope()` call with `time.monotonic()`. Pass the elapsed milliseconds to `record_publish()` after completion, and append one trace using the envelope `event_key` (or its transitional stable identifier), kind, target rail, elapsed milliseconds, and outcome. Reusing one writer is required for thread serialization and rotation.
3. In `write_path`, call `record_uncertain_sse()` when a response is classified `UNCERTAIN_ACCEPTED`; do not place response bodies or resume data in the trace.
4. In `health.write_wfmon_snippet`, add the result of `slo.export_metrics()` as the CRCP metrics payload. The result is already composed only of dictionaries, lists, strings, numbers, and `None`, so it can be passed directly to `json.dumps()`.

`SloCounters` is intentionally injectable, which keeps isolated services and tests independent. The module-level `record_poll()`, `record_publish()`, `record_uncertain_sse()`, and `export_metrics()` functions share a default instance for simple single-service deployments.

## Self-tests

Executed on the Linux Databricks job node with Python 3.11:

- Compiled both full module sources in memory.
- Imported both modules from the exact result paths.
- Appended 100 trace events from four concurrent threads with rotation and `fsync` enabled; every retained line decoded as JSON and had the exact six-field schema.
- Confirmed invalid empty event keys are rejected.
- Recorded one successful and one failed poll and verified a `0.5` success rate.
- Recorded publish latencies of 50, 300, and 900 ms against 100 and 500 ms buckets; verified cumulative counts of 1, 2, and 3 (`+Inf`), plus sum 1250 ms.
- Incremented and verified `uncertain_sse_count=2`.
- Serialized the exported wfmon metrics snapshot with `json.dumps()`.

Result: PASS.

UNIT-COMPLETE: w2-jsonl-traces
