# P1 Bus Delivery Worker

## Summary

Implemented a production-oriented, stdlib-only CRCP delivery worker with a
durable JSON spool and SQLite scheduling database. Delivery is at-least-once:
an envelope is retained until the sender acknowledges success, and an expired
claim can be recovered by another worker. Failures use capped exponential
backoff with configurable jitter. Poison and over-age envelopes move to a
dead-letter directory. New enqueue operations are rejected before either the
item-count or total-byte cap would be exceeded, so accepted work is not evicted
to make space.

The synchronous publishing behavior remains the default. Supplying `worker=`
to the publishing APIs selects durable enqueue instead.

## Files

- `delivery_worker.py` — new durable worker, spool management, SQLite claim
  leases, retry scheduling, dead-letter handling, caps, stats, bounded batch
  processing, and interruptible continuous loop.
- `bus.py` — full existing module plus an additive `worker=` hook on
  `publish_envelope`.
- `publish.py` — full existing module plus durable-worker hooks for
  `publish_outbox` and `publish_file`; queued and confirmed-published state are
  kept distinct, and publish state replacement is atomic and fsynced.
- `p1-bus-worker.md` — this implementation and verification report.

## Wiring into existing modules

Deploy `delivery_worker.py` beside the other `crcp` package modules, and deploy
the supplied full `bus.py` and `publish.py` modules in place of their source
versions.

Create one or more `DeliveryWorker(spool_dir, ...)` instances pointing to the
same local spool. Producers call either
`publish_envelope(envelope, worker=worker)` or
`publish_outbox(outbox, worker=worker)`. These calls durably enqueue and return
without performing network delivery. A separate service thread/process calls
`worker.run_forever(stop_event)`; bounded schedulers may instead call
`worker.process_once(limit=...)`.

The worker's default sender lazily calls the original synchronous
`publish_envelope` path, so no import cycle is introduced. SQLite rows are keyed
by envelope ID and are the authoritative deduplication and delivery state.
Spool filenames use a hash of that ID, preventing path traversal. A successful
delivery commits `delivered` before deleting its spool file. Because transport
does not expose an idempotency acknowledgement, a process failure after remote
send but before local acknowledgement can produce a duplicate; consumers must
continue to deduplicate on envelope ID, as required by at-least-once delivery.

## Self-tests

All checks passed on the Linux job node:

- Python compilation for all three Python deliverables.
- Durable enqueue and duplicate-ID suppression.
- First-send failure, exact exponential retry scheduling with jitter disabled,
  and later successful acknowledgement.
- Dead-letter move after the configured maximum failure count.
- Backlog item-cap rejection without eviction.
- Claim exclusion between two owners and recovery after lease expiry.
- Maximum-age expiry into dead-letter.
- `publish_envelope(..., worker=...)` hook without a network call.
- Package-level integration from `publish_outbox` through durable enqueue and
  worker delivery, including distinct queued versus published state.

No external service or credential was used by the tests.

UNIT-COMPLETE: p1-bus-worker
