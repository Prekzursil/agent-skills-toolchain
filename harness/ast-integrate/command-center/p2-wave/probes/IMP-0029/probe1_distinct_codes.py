#!/usr/bin/env python3
"""Probe 1: each precondition refused with a distinct code + same-run pass.

Catalog signal (1): plant a full temp volume, a read-only target, a client
WRITE lock, and a held lifecycle lock; the gate must refuse with codes
11/12/13/14. Negative control in the same process: a healthy tree must
pass (exit 0). Concurrency: two simultaneous acquires, exactly one proceeds.
"""
from __future__ import annotations

import json
import os
import sys
import time
from multiprocessing import Process, Queue
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import preflight as P  # noqa: E402

UNIT = "IMP-0029"
RECEIPT = REPO / "command-center" / "receipts" / "IMP-0029.json"
PAYLOAD = 64 * 1024
BACKUP = 64 * 1024


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def _tree(vol: Path) -> None:
    (vol / "plugin.json").write_text('{"name":"demo"}\n', encoding="utf-8")
    (vol / "commands").mkdir(exist_ok=True)
    (vol / "commands" / "ping.md").write_text("# ping\n", encoding="utf-8")


def _race_child(target: str, q: Queue) -> None:
    r = P.run_preflight(
        Path(target),
        payload_bytes=1024,
        backup_bytes=1024,
        acquire=True,
        client_retries=1,
        backoff_s=0,
    )
    q.put({"exit_code": r.exit_code, "reason": r.reason, "pid": os.getpid()})
    if r.lock is not None:
        time.sleep(1.0)
        r.lock.release()


def main() -> int:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size < 200:
        return fail("receipt missing")
    text = RECEIPT.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:IMP-0029" not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"receipt state={doc.get('state')}")

    codes: dict[str, int] = {}
    reasons: dict[str, str] = {}

    with P.TmpfsVolume("2M") as full:
        _tree(full)
        filled = P.fill_volume(full, leave_free=0)
        r = P.run_preflight(
            full, payload_bytes=PAYLOAD, backup_bytes=BACKUP, acquire=False,
            client_retries=1, backoff_s=0,
        )
        codes["disk"] = r.exit_code
        reasons["disk"] = r.reason
        if r.exit_code != P.EXIT_DISK:
            return fail(f"disk want 11 got {r.exit_code} fill={filled}")

    with P.TmpfsVolume("2M") as ro:
        _tree(ro)
        P.remount_ro(ro)
        r = P.run_preflight(
            ro, payload_bytes=1024, backup_bytes=1024, acquire=False,
            client_retries=1, backoff_s=0,
        )
        codes["perm"] = r.exit_code
        reasons["perm"] = r.reason
        if r.exit_code != P.EXIT_PERM:
            return fail(f"perm want 12 got {r.exit_code}")

    holder_c = None
    with P.TmpfsVolume("2M") as client:
        _tree(client)
        holder_c = P.spawn_lock_holder(client / "plugin.json")
        try:
            r = P.run_preflight(
                client, payload_bytes=1024, backup_bytes=1024, acquire=False,
                client_retries=1, backoff_s=0,
            )
            codes["client"] = r.exit_code
            reasons["client"] = r.reason
            if r.exit_code != P.EXIT_CLIENT_LOCK:
                return fail(f"client want 13 got {r.exit_code}")
        finally:
            P.stop_holder(holder_c)

    holder_l = None
    with P.TmpfsVolume("2M") as life:
        _tree(life)
        holder_l = P.spawn_lock_holder(life / P.LOCK_NAME)
        try:
            r = P.run_preflight(
                life, payload_bytes=1024, backup_bytes=1024, acquire=True,
                client_retries=1, backoff_s=0,
            )
            codes["lifecycle"] = r.exit_code
            reasons["lifecycle"] = r.reason
            if r.exit_code != P.EXIT_LIFECYCLE_LOCK:
                return fail(f"lifecycle want 14 got {r.exit_code}")
        finally:
            P.stop_holder(holder_l)

    with P.TmpfsVolume("4M") as ok:
        _tree(ok)
        r = P.run_preflight(
            ok, payload_bytes=PAYLOAD, backup_bytes=BACKUP, acquire=True,
            client_retries=1, backoff_s=0,
        )
        try:
            codes["ok"] = r.exit_code
            reasons["ok"] = r.reason
            if r.exit_code != P.EXIT_OK or r.lock is None:
                return fail(f"negative control want 0 got {r.exit_code} {r.reason}")
        finally:
            if r.lock is not None:
                r.lock.release()

    if len(set(codes.values())) != 5:
        return fail(f"exit codes not distinct: {codes}")

    with P.TmpfsVolume("4M") as race:
        _tree(race)
        q: Queue = Queue()
        procs = [
            Process(target=_race_child, args=(str(race), q)),
            Process(target=_race_child, args=(str(race), q)),
        ]
        for p in procs:
            p.start()
        rows = [q.get(timeout=10) for _ in procs]
        for p in procs:
            p.join(timeout=10)
            if p.is_alive():
                p.kill()
                p.join(timeout=2)
        race_codes = sorted(int(x["exit_code"]) for x in rows)
        if race_codes != [P.EXIT_OK, P.EXIT_LIFECYCLE_LOCK]:
            return fail(f"concurrency want [0,14] got {race_codes} {rows}")

    out = {
        "pass": True,
        "probe": "probe1-distinct-codes",
        "unit_id": UNIT,
        "codes": codes,
        "reasons": reasons,
        "distinct": True,
        "negative_control_pass": codes["ok"] == 0,
        "concurrency": {"codes": race_codes, "rows": rows},
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "SUCCESS:IMP-0029-probe1 distinct codes "
        f"disk={codes['disk']} perm={codes['perm']} "
        f"client={codes['client']} lifecycle={codes['lifecycle']} "
        f"ok={codes['ok']} race={race_codes}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
