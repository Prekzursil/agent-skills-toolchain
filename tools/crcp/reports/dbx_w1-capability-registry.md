---
title: dbx_w1-capability-registry
type: note
permalink: dqverify-repo-20261013/tools/crcp/reports/dbx-w1-capability-registry
---

# W1 capability registry

## Summary

Implemented a production-oriented, stdlib-only CRCP capability registry for the five required rails: `chatgpt`, `claude`, `codex`, `grok`, and `agent_mail`.

The module provides:

- Durable capability definitions containing `name`, `rail`, and an optional process-local handler stub.
- Default capabilities `chatgpt_backend_api`, `claude_orchestration`, `codex_execution`, `grok_reasoning`, and `agent_mail_bus`.
- Atomic `claim_lease(capability, owner, ttl_s)`, owner-checked `release`, and expiry-aware `is_available` APIs, both on `CapabilityRegistry` and as lazy module-level functions.
- Same-owner renewal, contention rejection, automatic takeover after expiry, strict TTL/owner validation, and typed unknown-capability exceptions.
- Bus-safe `UNSUPPORTED_CAPABILITY` structures via `check_required`, `unsupported`, `unsupported_capability`, and `UnsupportedCapabilityError.as_bus_result()`.
- Atomic JSON persistence at the default `reports/capabilities.json` path using a same-directory temporary file, flush, `fsync`, and `os.replace`.
- Cross-process serialization through portable atomic lock-directory creation, with bounded acquisition time and stale-lock recovery.

SQLite was evaluated first, but both WAL and rollback-journal SQLite returned `disk I/O error` on the required DBFS FUSE path. The permitted file backend was therefore used and validated directly on DBFS.

## File list

- `/dbfs/tmp/crcp-e2e-full/results/capabilities.py` — complete registry module and file backend.
- `/dbfs/tmp/crcp-e2e-full/results/w1-capability-registry.md` — this implementation and verification report.
- `/dbfs/tmp/crcp-e2e-full/results/reports/capabilities.json` — lazily created runtime state path; it is intentionally not pre-populated as a build artifact.

## Wiring into existing modules

The unpacked CRCP source was read-only, so no source modules were modified. The intended additive wiring is:

1. Construct one `CapabilityRegistry` in the bus process. Its default state is below the delivered module in `reports/capabilities.json`; a caller may supply another path.
2. Before routing an envelope, pass `envelope.get("capabilities_required", [])` to `registry.check_required(...)`.
3. If a result is returned, publish/return it as the response payload and set the response envelope `completion` to `UNSUPPORTED_CAPABILITY`. This directly handles the existing `chatgpt_backend_api` requirement emitted by `bridge.py`.
4. Before dispatching a supported capability, call `claim_lease(name, owner, ttl_s)`. Defer when it returns false; call `release(name, owner)` in a `finally` block after the work completes. A repeated claim by the same owner renews the lease.
5. Register live adapter callables with `Capability(name, rail, handler)` in each process that dispatches work. Only definitions and leases persist; executable handlers never enter state files.

The registry is additive to `envelope.py`: the existing `capabilities_required: list[str]` remains unchanged and becomes enforceable at the bus routing boundary.

## Self-tests

Final tests passed on the mandated DBFS results path:

- Normal import and bytecode compilation: pass.
- Required five-rail/default-capability catalog: pass.
- Known and unknown `capabilities_required` validation: pass.
- Typed `UNSUPPORTED_CAPABILITY` payload and typed exception conversion: pass.
- Initial availability, acquisition, same-owner renewal, competing-owner rejection, wrong-owner release rejection, expiry, takeover, and correct-owner release: pass.
- Definition persistence across independent registry instances and process-local handler behavior: pass.
- Invalid TTL rejection for zero, negative, infinity, NaN, and boolean values: pass.
- Eight simultaneous threads and, separately, eight simultaneous processes against one DBFS-backed JSON state: exactly one acquisition and seven contention results in each run.
- Atomic JSON backend creation/read/write/replace directly under `/dbfs/tmp/crcp-e2e-full/results/reports`: pass.
- Secret-pattern scan of the delivered Python module: no matches.

Final functional run: `PASS`, 24 assertions, 8 concurrent claimers.

UNIT-COMPLETE: w1-capability-registry