---
title: dbx_merge-A-live-spool
type: note
permalink: dqverify-repo-20261013/tools/crcp/reports/dbx-merge-a-live-spool
---

# Merge A — live bridge durability wiring

## Result

Wrote the full replacement `live_bridge.py` beside this report. Only the owned file was produced; the unpacked source tree was read but not modified.

## Wiring completed

- Imported and instantiated `EventSpool`, using `reports/spool.db` by default. Optional constructor paths were added for isolated tests without changing existing callers.
- In `cycle_once`, the fetched conversation payload now produces a stable `event_key(conversation_id, update_time, payload)`. The same key is placed on the outgoing envelope and `put_observed` durably records the logical update before any publish attempt.
- Added the spool lifecycle `observed -> spooled -> publishing -> acked`, with an ACK lookup that skips duplicate publishing after a crash between ACK and checkpoint persistence.
- A successful publish is acknowledged in SQLite before the conversation checkpoint is updated. A publish or ACK failure is marked `failed`, reported in the cycle summary, and leaves the conversation checkpoint unchanged so a later poll retries it.
- `run_forever` acquires `reports/live_bridge.lock` through `acquire_singleton_lock` before starting HTTP or polling. Lock contention prints the recorded owner PID and returns without killing or disturbing the owner.
- Replaced direct state writes with same-directory temporary-file serialization, file `fsync`, atomic `os.replace`, and directory `fsync`; failed writes clean up their temporary file.
- Preserved the existing `/livez`, `/readyz`, `/poll-now`, shared-token authentication, and per-client rate limiting behavior.
- Added spool backlog count and oldest age to `/metrics` and `/health`, plus the complete backlog object to `/status`.

## Principal call sites

- `LiveBridgeState.save`: atomic state persistence.
- `LiveBridgeService.__init__`: default spool and singleton paths.
- `LiveBridgeService.cycle_once`: stable event identity, observe/spool/claim/publish/ACK/fail ordering, and post-ACK checkpointing.
- `LiveBridgeService.run_forever`: singleton acquisition and clean contention return.
- HTTP handler `do_GET`: spool backlog telemetry.

## Validation

- Replacement source compiled successfully.
- Focused offline lifecycle fixture passed: first publish failure remained uncheckpointed and `failed`; the next cycle reused the same event key, published, ACKed, then checkpointed; an ACKed replay skipped publishing.
- Singleton contention fixture passed and printed the live lease owner PID while leaving service status stopped.
- Atomic state fixture left no temporary files behind.
- Existing contract suite: 21/21 passed with the repository's documented flat-import `PYTHONPATH`.
- Shared merge smoke/wiring suite: 6/6 passed.

## Residual risk

- Delivery is intentionally at-least-once. A process crash after the external send succeeds but before `mark_acked` commits can resend; downstream consumers must deduplicate using the propagated event key.
- Failed automatic publishes are retried when the conversation is observed again in the configured listing window. This file does not add an independent backlog-drain worker, so a persistently displaced conversation could remain queued until another worker or a wider poll sees it.
- With `auto_publish=False`, the existing export/checkpoint semantics are retained after durable spooling; operational use therefore requires a separate spool consumer.

UNIT-COMPLETE: merge-A-live-spool