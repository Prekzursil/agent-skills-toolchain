# W2 golden journey 1

## Summary

Implemented a deterministic, fixture-only CRCP observe-to-request acceptance journey. The runner loads a minimal ChatGPT conversation delta, constructs and validates one `crcp.envelope.v1.1` `task.request`, verifies the content-derived `event_key` is stable on replay, injects the duplicate into the SQLite spool, and proves that the replay produces one spool record and one logical effect. No live network or credential access is used.

## Files

- `/dbfs/tmp/crcp-e2e-full/results/fixtures/golden_journey_1/chatgpt_delta.json` — minimal conversation delta with a stable conversation ID, update time, and one user message.
- `/dbfs/tmp/crcp-e2e-full/results/fixtures/golden_journey_1/expected_task_request.json` — exact expected `task.request` envelope with deterministic IDs, timestamp, content address, and event key.
- `/dbfs/tmp/crcp-e2e-full/results/golden_journey_1.py` — standalone stdlib runner; exits 0 only after envelope, replay, deduplication, lifecycle, and logical-effect checks pass.
- `/dbfs/tmp/crcp-e2e-full/results/w2-golden-journey-1.md` — this implementation report.

## Wiring into existing modules

The runner imports `make_event_key`, `payload_sha256`, and `EventSpool` from the existing sibling `event_spool.py`. This directly exercises the shared canonical JSON hashing, the specified `conversation_id:update_time:payload_sha256` identity, the unique SQLite spool key, and the `observed -> spooled -> publishing -> acked` lifecycle.

It imports `require_valid` from the existing sibling `envelope_v11.py`, so the generated request is checked against the shared v1.1 schema, UUID, timestamp, kind, capability, metadata, and content-address rules. Python resolves both modules from the runner's result directory regardless of the caller's current working directory.

## Self-tests

- Parsed both fixtures with `python3 -B -m json.tool`: PASS.
- Ran `python3 -B /dbfs/tmp/crcp-e2e-full/results/golden_journey_1.py`: PASS, `kind=task.request`, `logical_effects=1`.
- Ran the same absolute-path command from `/tmp` with `PYTHONOPTIMIZE=1`: PASS, confirming location independence and that safety checks remain active when native Python assertions are optimized out.
- The runner compared the generated envelope byte-for-data against the expected JSON object, rebuilt the event key from a separately loaded replay, rejected the duplicate insertion, confirmed exactly one durable spool row and logical effect, and reached `acked`.

UNIT-COMPLETE: w2-golden-journey-1
