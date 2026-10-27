# e2e-A-spool-singleton

## Summary

Implemented the P0 durability boundary for the live bridge. Conversation observations now receive a deterministic, content-derived event key in a SQLite spool before any bus publish. Delivery moves through `observed -> spooled -> publishing -> acked` (with `failed` retry state), and the conversation update checkpoint advances only after the ACK is durably recorded. Interrupted `publishing` records are requeued when the spool is reopened.

`LiveBridgeState.save` now writes a same-directory temporary file, flushes and fsyncs it, atomically replaces the state file, and fsyncs the containing directory on Unix. `run_forever` acquires a portable singleton lease before starting HTTP or advertising running state. The lease uses `fcntl` on Unix and `msvcrt` on Windows, with a stable OS-lock file and atomically replaced PID/timestamp metadata; contention raises `SingletonLockError` containing the owner PID and never force-kills it.

## File list

- `spool.py` — stdlib SQLite event spool, deterministic event keys, lifecycle transitions, restart requeue, lookup/idempotency helpers, and backlog count/oldest-age statistics.
- `singleton.py` — portable singleton acquisition, atomic owner PID metadata, context-manager/explicit release, and `atexit` cleanup.
- `live_bridge.py` — full replacement wiring spool/ACK/checkpoint ordering, singleton startup lease, backlog summary, and atomic state persistence. It preserves compatible health/redaction changes co-landed in the shared P0 result tree.
- `e2e-A-spool-singleton.md` — this implementation and verification report.

## Wiring notes

- Install `spool.py` and `singleton.py` beside `live_bridge.py` in the `crcp` package.
- Defaults resolve to `<crcp-root>/reports/spool.db`, `<crcp-root>/reports/live_bridge.pid`, and the existing state path. Tests and callers may override `spool_path`, `singleton_path`, and `state_path` independently.
- Event identity hashes the canonical conversation snapshot rather than generated envelope metadata, so a refetch after a crash resolves to the same logical record.
- If publish raises, the spool row becomes `failed`, the error is reported, and `conversations[conversation_id].update_time` is not advanced. A later cycle retries that event. If ACK persisted but the JSON checkpoint did not, the next cycle observes the ACK and advances the checkpoint without republishing.
- `auto_publish=False` leaves observations durably spooled and intentionally does not advance the delivered checkpoint.

## Self-test notes

- `py_compile` passed for all three Python deliverables.
- Verified two identical inserts produce one event key and one SQLite row.
- Verified lifecycle transitions, idempotent ACK, backlog statistics, and restart recovery from `publishing` to `spooled`.
- Verified a real second process is denied the singleton lease, receives the holder PID, and can acquire after release.
- Verified repeated atomic state saves leave valid replacement content and no temporary file.
- Injected a synthetic bus failure: the event remained in backlog and the conversation checkpoint did not advance. A subsequent successful cycle published once, ACKed, advanced the checkpoint, and cleared backlog.

UNIT-COMPLETE: e2e-A-spool-singleton
