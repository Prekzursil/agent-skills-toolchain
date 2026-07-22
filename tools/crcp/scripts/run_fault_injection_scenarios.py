"""Run CRCP golden journey #2 against durable lifecycle and bus stubs.

The stubs intentionally model only the contracts needed by fault injection:
SQLite durability, idempotent ingest, expiring claims, idempotent bus accepts,
and an explicit local ACK checkpoint.  No network service or credential is
used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any

from fault_inject import FAULT_HOOKS, FaultInjector, InjectedFault


class LifecycleSpoolStub:
    """Small durable spool implementing the production lifecycle contract."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.execute(
                """
                create table if not exists spool (
                    event_key text primary key,
                    payload_sha256 text not null,
                    state text not null,
                    lease_owner text,
                    lease_until integer,
                    attempts integer not null default 0,
                    ack_id text
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path), timeout=10.0)
        con.row_factory = sqlite3.Row
        con.execute("pragma journal_mode = wal")
        con.execute("pragma synchronous = full")
        return con

    def ingest(self, event_key: str, payload_sha256: str) -> bool:
        """Persist observed then spooled without downgrading a replayed row."""
        with self._connect() as con:
            before = con.total_changes
            con.execute(
                """
                insert or ignore into spool(event_key, payload_sha256, state)
                values (?, ?, 'observed')
                """,
                (event_key, payload_sha256),
            )
            inserted = con.total_changes > before
            if inserted:
                con.execute(
                    "update spool set state='spooled' where event_key=? and state='observed'",
                    (event_key,),
                )
            else:
                row = con.execute(
                    "select payload_sha256 from spool where event_key=?", (event_key,)
                ).fetchone()
                if row is None or row["payload_sha256"] != payload_sha256:
                    raise ValueError("event_key reused with different payload")
            return inserted

    def claim(
        self,
        event_key: str,
        *,
        owner: str,
        now: int,
        lease_seconds: int,
    ) -> bool:
        with self._connect() as con:
            cur = con.execute(
                """
                update spool
                set state='publishing', lease_owner=?, lease_until=?, attempts=attempts+1
                where event_key=? and (
                    state='spooled'
                    or (state='publishing' and lease_until <= ?)
                )
                """,
                (owner, now + lease_seconds, event_key, now),
            )
            return cur.rowcount == 1

    def mark_acked(self, event_key: str, *, owner: str, ack_id: str) -> None:
        with self._connect() as con:
            cur = con.execute(
                """
                update spool
                set state='acked', ack_id=?, lease_owner=null, lease_until=null
                where event_key=? and state='publishing' and lease_owner=?
                """,
                (ack_id, event_key, owner),
            )
            if cur.rowcount != 1:
                raise RuntimeError("claim lost before ACK checkpoint")

    def row(self, event_key: str) -> dict[str, Any]:
        with self._connect() as con:
            row = con.execute(
                "select * from spool where event_key=?", (event_key,)
            ).fetchone()
        if row is None:
            raise KeyError(event_key)
        return dict(row)

    def acked_keys(self) -> set[str]:
        with self._connect() as con:
            rows = con.execute(
                "select event_key from spool where state='acked'"
            ).fetchall()
        return {str(row[0]) for row in rows}


class IdempotentBusStub:
    """Durable accepting bus keyed by the CRCP event key."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.execute(
                """
                create table if not exists accepted (
                    event_key text primary key,
                    ack_id text not null,
                    send_calls integer not null
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path), timeout=10.0)
        con.row_factory = sqlite3.Row
        con.execute("pragma journal_mode = wal")
        con.execute("pragma synchronous = full")
        return con

    def send(self, event_key: str) -> tuple[str, bool]:
        ack_id = "ack-" + hashlib.sha256(event_key.encode("utf-8")).hexdigest()[:20]
        with self._connect() as con:
            before = con.total_changes
            con.execute(
                "insert or ignore into accepted(event_key, ack_id, send_calls) values (?, ?, 0)",
                (event_key, ack_id),
            )
            newly_accepted = con.total_changes > before
            con.execute(
                "update accepted set send_calls=send_calls+1 where event_key=?",
                (event_key,),
            )
        return ack_id, newly_accepted

    def accepted_keys(self) -> set[str]:
        with self._connect() as con:
            rows = con.execute("select event_key from accepted").fetchall()
        return {str(row[0]) for row in rows}

    def row(self, event_key: str) -> dict[str, Any]:
        with self._connect() as con:
            row = con.execute(
                "select * from accepted where event_key=?", (event_key,)
            ).fetchone()
        if row is None:
            raise KeyError(event_key)
        return dict(row)


def _deliver_once(
    spool: LifecycleSpoolStub,
    bus: IdempotentBusStub,
    injector: FaultInjector,
    *,
    event_key: str,
    payload_sha256: str,
    now: int,
) -> None:
    inserted = spool.ingest(event_key, payload_sha256)
    injector.record_step("spooled", event_key=event_key, inserted=inserted)
    injector.fail_after_ingest(event_key=event_key)

    owner = f"worker-{now}"
    if not spool.claim(event_key, owner=owner, now=now, lease_seconds=5):
        row = spool.row(event_key)
        if row["state"] == "acked":
            injector.record_step("already_acked", event_key=event_key)
            return
        raise RuntimeError("message not claimable")
    injector.record_step("claimed", event_key=event_key, owner=owner)
    injector.fail_after_claim(event_key=event_key, owner=owner)

    ack_id, newly_accepted = bus.send(event_key)
    injector.record_step(
        "bus_acked",
        event_key=event_key,
        ack_id=ack_id,
        newly_accepted=newly_accepted,
    )
    injector.fail_after_send(event_key=event_key, ack_id=ack_id)
    spool.mark_acked(event_key, owner=owner, ack_id=ack_id)
    injector.record_step("checkpoint_acked", event_key=event_key, ack_id=ack_id)


def run_scenario(root: Path, hook: str, *, seed: int) -> dict[str, Any]:
    scenario_dir = root / hook
    scenario_dir.mkdir(parents=True, exist_ok=True)
    trace_path = scenario_dir / "journey.jsonl"
    spool = LifecycleSpoolStub(scenario_dir / "spool.sqlite3")
    bus = IdempotentBusStub(scenario_dir / "bus.sqlite3")
    payload_sha256 = hashlib.sha256(f"payload:{hook}".encode("utf-8")).hexdigest()
    event_key = hashlib.sha256(
        f"conversation-2\0update-2\0{payload_sha256}".encode("utf-8")
    ).hexdigest()

    crashing = FaultInjector(
        seed=seed,
        enabled_hooks=[hook],
        trace_path=trace_path,
    )
    caught: InjectedFault | None = None
    try:
        _deliver_once(
            spool,
            bus,
            crashing,
            event_key=event_key,
            payload_sha256=payload_sha256,
            now=100,
        )
    except InjectedFault as exc:
        caught = exc
    if caught is None or caught.hook != hook:
        raise AssertionError(f"expected injected crash at {hook}")

    # A later time makes any pre-crash publishing claim eligible for replay.
    replay = FaultInjector(seed=seed, trace_path=trace_path)
    _deliver_once(
        spool,
        bus,
        replay,
        event_key=event_key,
        payload_sha256=payload_sha256,
        now=200,
    )
    # A duplicate source observation must neither redeliver nor downgrade ACK.
    _deliver_once(
        spool,
        bus,
        replay,
        event_key=event_key,
        payload_sha256=payload_sha256,
        now=300,
    )

    spool_row = spool.row(event_key)
    bus_row = bus.row(event_key)
    accepted = bus.accepted_keys()
    acked = spool.acked_keys()
    no_lost_acked = accepted <= acked
    checks = {
        "fault_observed": caught.hook == hook,
        "event_eventually_acked": spool_row["state"] == "acked",
        "no_lost_acked_messages": no_lost_acked,
        "one_logical_bus_accept": len(accepted) == 1,
        "ack_identity_reconciled": spool_row["ack_id"] == bus_row["ack_id"],
        "duplicate_ingest_preserves_ack": spool.row(event_key)["state"] == "acked",
    }
    if not all(checks.values()):
        raise AssertionError(f"scenario checks failed: {checks}")
    return {
        "hook": hook,
        "success": True,
        "checks": checks,
        "spool_state": spool_row["state"],
        "claim_attempts": spool_row["attempts"],
        "bus_send_calls": bus_row["send_calls"],
        "logical_bus_accepts": len(accepted),
        "trace": str(trace_path),
    }


def run_all(root: Path, *, seed: int) -> dict[str, Any]:
    scenarios = [run_scenario(root, hook, seed=seed) for hook in sorted(FAULT_HOOKS)]
    return {
        "schema": "crcp.fault_scenario_report.v1",
        "success": all(item["success"] for item in scenarios),
        "seed": seed,
        "scenarios": scenarios,
        "assertion": "every bus-accepted event is durably checkpointed acked after replay",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20260720)
    parser.add_argument("--work-dir", type=Path)
    args = parser.parse_args(argv)

    temporary = args.work_dir is None
    root = args.work_dir or Path(tempfile.mkdtemp(prefix="crcp-fault-scenarios-"))
    try:
        report = run_all(root, seed=args.seed)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["success"] else 1
    finally:
        if temporary:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
