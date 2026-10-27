# W1 lifecycle states

## Summary

Implemented a production-oriented CRCP event lifecycle contract using only the Python standard library. The module defines the six required states (`observed`, `spooled`, `publishing`, `acked`, `dead_letter`, and `failed`), an explicit legal-transition table, and a validated `EventRecord` dataclass. Invalid, unknown, same-state, and terminal-state transitions raise without partially mutating a record.

Publishing attempts are counted when a record enters `publishing`. A retry is represented by `publishing -> spooled -> publishing`; this preserves the durable-spool invariant and increments the attempt count once per transport attempt. `acked` and `dead_letter` are terminal. A recoverable `failed` record may be moved back to `spooled`, or permanently quarantined in `dead_letter`.

The included `InMemoryLifecycleStore` is thread-safe, treats repeated observation of an event key as idempotent, returns copies to prevent unvalidated external mutation, and supports validated atomic JSON snapshots using a same-directory temporary file, `fsync`, and `os.replace`. The snapshot format is versioned as `crcp.lifecycle.v1`.

## File list

- `/dbfs/tmp/crcp-e2e-full/results/lifecycle.py` — complete lifecycle contract, record model, transition errors, in-memory store, and atomic JSON dump/load support.
- `/dbfs/tmp/crcp-e2e-full/results/w1-lifecycle-states.md` — implementation and verification report.

## Wiring into existing modules

The unpacked source tree was treated as read-only, so it was not modified. To integrate, place `lifecycle.py` at `crcp/lifecycle.py` and use one stable key per logical update, matching the synthesis contract: `conversation_id + update_time + payload_sha256` (with an unambiguous separator or canonical encoding).

In `crcp/live_bridge.py`, wire the lifecycle around the existing fetch/publish/checkpoint sequence as follows:

1. After detecting a new update, call `store.observe(event_key)`.
2. Persist the fetched envelope/payload, then transition `observed -> spooled`. Only this durable step should advance the ingest/observation checkpoint.
3. A delivery worker selects `spooled` records and transitions each to `publishing` immediately before calling `publish_envelope`.
4. On confirmed bus acknowledgement, transition `publishing -> acked` and then advance the delivery checkpoint.
5. On a retryable publish error, transition `publishing -> spooled`; after the retry budget is exhausted, transition to `dead_letter`. Use `failed` for records requiring recovery or operator intervention, with recovery returning them to `spooled`.

This keeps transport acknowledgement separate from observation and prevents a crash between publish and checkpoint from silently losing an accepted update. The event key makes replay discover the same logical record rather than creating a new one.

## Self-tests

Executed on the Linux Databricks job node:

- `python -m py_compile lifecycle.py` — passed.
- Created an observed record and verified duplicate observation is idempotent — passed.
- Exercised the happy path through `observed -> spooled -> publishing -> acked` — passed.
- Exercised `publishing -> spooled -> publishing` and verified `attempts == 2` — passed.
- Verified an illegal transition out of terminal `acked` raises `InvalidTransitionError` and leaves the stored record unchanged — passed.
- Exercised recovery/quarantine via `observed -> failed -> spooled -> dead_letter` — passed.
- Atomically dumped a two-record store, reloaded it, and verified exact serialized equality and format version — passed.
- Verified empty and unknown state values are rejected — passed.

Result: compilation passed and all 16 runtime assertions passed.

UNIT-COMPLETE: w1-lifecycle-states
