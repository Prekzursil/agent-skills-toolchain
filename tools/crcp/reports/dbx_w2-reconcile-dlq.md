# W2 reconcile and dead-letter tooling

## Summary

Implemented production-oriented, standard-library-only recovery tools for CRCP's durable delivery lifecycle. The reconciliation module compares spool records with the existing conversation checkpoint, reports orphan records and stale `publishing` claims, resets recoverable records to `spooled`, and atomically moves poison records into dead-letter storage. The dead-letter module provides metadata-only listing, credential-redacted inspection, requeue, and confirmation-gated permanent purge.

Both modules integrate with the delivered `DeliveryWorker` contract (`pending/`, `dead-letter/`, and `delivery.sqlite3`) and retain a schema-tolerant JSON-only fallback. They preserve unknown record fields for forward compatibility, recognize common flat and nested envelope/checkpoint layouts, reject unsafe or ambiguous entry paths, ignore symlinks, and use temp-file + flush + fsync + replace for JSON lifecycle changes. SQLite recovery changes use immediate transactions. Transport publishing is intentionally not performed by these operator commands: requeue restores the worker's `pending` state (reported as lifecycle state `spooled`), leaving the normal CRCP delivery worker as the single publishing path.

## File list

- `/dbfs/tmp/crcp-e2e-full/results/reconcile.py`
  - `scan_spool(spool_dir, checkpoint_path, stuck_after_seconds=...)`
  - `requeue_spooled(path, reason=...)`
  - `mark_dead_letter(path, dead_letter_dir, reason=...)`
  - CLI commands: `scan`, `requeue`, `dead-letter`
- `/dbfs/tmp/crcp-e2e-full/results/dead_letter.py`
  - `list_dead_letters(dead_letter_dir)`
  - `inspect_dead_letter(dead_letter_dir, entry)`
  - `requeue_dead_letter(dead_letter_dir, entry, spool_dir)`
  - `purge_dead_letters(dead_letter_dir, confirm=False)`
  - CLI commands: `list`, `inspect`, `requeue`, `purge --confirm`
- `/dbfs/tmp/crcp-e2e-full/results/w2-reconcile-dlq.md`
  - This implementation and verification report.

## Wiring into existing modules

Copy the two Python files into the existing `crcp/` package. They then run directly as module CLIs:

```text
python -m crcp.reconcile scan --spool <spool-dir> --checkpoint <live_bridge_state.json>
python -m crcp.reconcile requeue <spool-record.json>
python -m crcp.reconcile dead-letter <spool-record.json> --dir <dead-letter-dir> --reason <reason>
python -m crcp.dead_letter --dir <dead-letter-dir> list
python -m crcp.dead_letter --dir <dead-letter-dir> inspect <filename-or-event-key>
python -m crcp.dead_letter --dir <dead-letter-dir> requeue <entry> --spool <spool-dir>
python -m crcp.dead_letter --dir <dead-letter-dir> purge --confirm
```

The default checkpoint is the existing `reports/live_bridge_state.json`; its `conversations` mapping is supported as-is. Reconciliation also accepts additive future `events`, `checkpoints`, `published`, or `acked` collections and JSONL checkpoint files. Records match in decreasing specificity through `event_key`, `envelope_id`, `payload_sha256`, or `(conversation_id, update_time)`.

For the delivered worker, reconciliation reads `delivery.sqlite3` without exposing payloads, maps `pending/leased/delivered/dead` to `spooled/publishing/acked/dead_letter`, detects expired leases, and reports active database rows whose files are missing (and files lacking index rows). Requeue clears the SQLite lease and makes the item immediately eligible; dead-letter and purge keep the JSON file and SQLite index synchronized. The JSON-only fallback uses explicit lifecycle fields. No changes to the read-only unpacked source tree were made.

## Self-tests

Passed on the Linux Databricks job node with Python's bytecode compiler and an isolated temporary lifecycle fixture:

- Both modules compile successfully with `python -m py_compile`.
- Scan fixture: 3 readable spool records, 1 checkpoint, 2 orphans, 1 stale publisher, and 1 malformed JSON file were classified as expected.
- A stale `publishing` record requeued to `spooled`; requeue of an `acked` terminal record was rejected.
- A spool record was marked and atomically moved to dead-letter storage.
- Listing returned lifecycle metadata; inspection redacted a credential field and a bearer-shaped string.
- A dead letter requeued to the spool with history preserved and lease/dead-letter fields cleared.
- Purge without confirmation was rejected; `confirm=True` removed the fixture.
- Both CLI parsers completed their `--help` paths successfully.
- SQLite integration fixture passed end to end: enqueue, expired-lease detection, requeue, dead-letter move/index update, list, inspect, requeue to `pending/`, guarded purge, and removal of the dead database row.

UNIT-COMPLETE: w2-reconcile-dlq
