---
title: dbx_w2-fault-injection
type: note
permalink: dqverify-repo-20261013/tools/crcp/reports/dbx-w2-fault-injection
---

# W2 fault injection — CRCP golden journey #2

## Summary

Implemented deterministic, opt-in fault injection for the three required
durability boundaries: `fail_after_ingest`, `fail_after_claim`, and
`fail_after_send`. The injector is disabled by default, uses SHA-256 over the
seed/hook/occurrence for scheduling, raises a typed `InjectedFault`, and writes
metadata-only lifecycle records to an append-only, flushed and fsynced JSONL
trace. Trace sequence numbers continue after a replay process reconstructs the
injector.

Implemented a scenario runner with SQLite lifecycle and idempotent bus stubs.
For each crash boundary it simulates a process crash, reconstructs state from
disk, expires any abandoned claim, replays delivery, and injects the source a
second time. Its primary invariant is that every bus-accepted event is present
in the durable spool as `acked` after replay. The post-send case proves that two
physical calls resolve to one logical bus acceptance and the same ACK identity.

## Files

- `fault_inject.py` — reusable fault hooks, typed exception, deterministic
  decisions, bounded/redacted context, and durable JSONL journey tracing.
- `run_fault_injection_scenarios.py` — executable golden journey #2 runner plus
  durable lifecycle/spool and idempotent bus stubs.
- `w2-fault-injection.md` — this implementation and verification report.

All deliverables are under `/dbfs/tmp/crcp-e2e-full/results/` as required.

## Wiring into existing modules

The source tree was read-only, so no existing CRCP module was modified. The
injector is designed for dependency injection at the audited boundaries:

1. In `live_bridge.py` (or its durable-spool successor), call
   `record_step("spooled", ...)` and `fail_after_ingest(...)` only after the
   `observed -> spooled` transaction commits.
2. In the independent spool delivery worker, call
   `record_step("claimed", ...)` and `fail_after_claim(...)` only after the
   `spooled -> publishing` claim and lease commit.
3. Immediately after `bus.publish_envelope(...)` returns terminal acceptance,
   record `bus_acked` and call `fail_after_send(...)`; only then persist the
   local `publishing -> acked` checkpoint.
4. Construct `FaultInjector()` with no enabled hooks in production. Tests pass
   an explicitly configured injector and a trace path. Replays use a disabled
   injector with the same seed and trace path, preserving the journey ID and
   continuing trace sequence numbers.

This placement directly exercises the existing unsafe publish-before-checkpoint
window without embedding fault behavior in `bus.py`. Correct post-send replay
depends on the production bus/consumer honoring the stable CRCP event key as an
idempotency key; the scenario stub implements and verifies that contract.

## Self-tests

Executed with Python on the Linux Databricks job node:

- `python -m py_compile fault_inject.py run_fault_injection_scenarios.py` — PASS.
- Injector API checks — PASS: identical seed produced identical decisions;
  trace numbering continued across reconstructed instances; nested context was
  bounded; credential-looking keys were redacted and test secret values were
  absent from the trace.
- `python run_fault_injection_scenarios.py --seed 20260720` — PASS, 3/3:
  `fail_after_ingest`, `fail_after_claim`, and `fail_after_send`.
- Every scenario reached durable `acked`, preserved ACK identity, accepted one
  logical bus message, tolerated duplicate ingest, and satisfied
  `accepted_event_keys <= durable_acked_event_keys`.
- The `fail_after_send` replay performed two send calls but produced exactly one
  logical acceptance, demonstrating idempotent reconciliation of the uncertain
  send window.

UNIT-COMPLETE: w2-fault-injection