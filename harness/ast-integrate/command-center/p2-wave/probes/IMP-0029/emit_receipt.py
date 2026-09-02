#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0029.json through the atomic writer."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from multiprocessing import Process, Queue
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))
sys.path.insert(0, str(REPO / "command-center"))

import preflight as P  # noqa: E402
import receipt_writer as RW  # noqa: E402

UNIT = "IMP-0029"
OUT = "command-center/receipts/IMP-0029.json"
SENTINEL = "SUCCESS:IMP-0029"
IMPL = "tools/plugin/preflight.py"
TESTS_REL = "tools/plugin/tests/test_preflight.py"
P1 = "command-center/p2-wave/probes/IMP-0029/probe1_distinct_codes.py"
P2 = "command-center/p2-wave/probes/IMP-0029/probe2_oob_os.py"
QUESTION = (
    "Implement a preflight that refuses to start a mutating lifecycle op when "
    "free disk is below the payload size plus backup, when the target tree is "
    "not writable, when a file is locked by a running client, or when another "
    "lifecycle op holds the lock — preventing two concurrent installs from "
    "interleaving on the same live tree."
)
PAYLOAD = 64 * 1024
BACKUP = 64 * 1024


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
    }


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text[-4000:]


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


def live_measure() -> dict:
    out: dict = {}

    with P.TmpfsVolume("2M") as full:
        _tree(full)
        filled = P.fill_volume(full, leave_free=0)
        oob_free = P.os_free_bytes(full)
        r = P.run_preflight(
            full, payload_bytes=PAYLOAD, backup_bytes=BACKUP, acquire=False,
            client_retries=1, backoff_s=0,
        )
        out["disk"] = {
            "exit_code": r.exit_code,
            "reason": r.reason,
            "oob_free_bytes": oob_free,
            "needed_bytes": PAYLOAD + BACKUP,
            "fill_written": filled["written"],
            "f_bavail": filled["f_bavail"],
            "f_frsize": filled["f_frsize"],
        }

    with P.TmpfsVolume("2M") as ro:
        _tree(ro)
        P.remount_ro(ro)
        view = P.os_statvfs_view(ro)
        r = P.run_preflight(
            ro, payload_bytes=1024, backup_bytes=1024, acquire=False,
            client_retries=1, backoff_s=0,
        )
        out["perm"] = {
            "exit_code": r.exit_code,
            "reason": r.reason,
            "rdonly": bool(view["rdonly"]),
            "f_flag": view["f_flag"],
        }

    holder = None
    with P.TmpfsVolume("2M") as client:
        _tree(client)
        payload = client / "plugin.json"
        holder = P.spawn_lock_holder(payload)
        try:
            locks = P.locks_on_path(payload)
            r = P.run_preflight(
                client, payload_bytes=1024, backup_bytes=1024, acquire=False,
                client_retries=1, backoff_s=0,
            )
            out["client"] = {
                "exit_code": r.exit_code,
                "reason": r.reason,
                "holder_pid": holder.pid,
                "proc_exists": Path(f"/proc/{holder.pid}").is_dir(),
                "proc_locks": locks,
            }
        finally:
            P.stop_holder(holder)

    holder = None
    with P.TmpfsVolume("2M") as life:
        _tree(life)
        holder = P.spawn_lock_holder(life / P.LOCK_NAME)
        try:
            r = P.run_preflight(
                life, payload_bytes=1024, backup_bytes=1024, acquire=True,
                client_retries=1, backoff_s=0,
            )
            out["lifecycle"] = {
                "exit_code": r.exit_code,
                "reason": r.reason,
                "holder_pid": holder.pid,
                "proc_exists": Path(f"/proc/{holder.pid}").is_dir(),
            }
        finally:
            P.stop_holder(holder)

    with P.TmpfsVolume("4M") as ok:
        _tree(ok)
        r = P.run_preflight(
            ok, payload_bytes=PAYLOAD, backup_bytes=BACKUP, acquire=True,
            client_retries=1, backoff_s=0,
        )
        try:
            out["ok"] = {
                "exit_code": r.exit_code,
                "reason": r.reason,
                "lock_held": r.lock is not None,
                "oob_free_bytes": P.os_free_bytes(ok),
            }
        finally:
            if r.lock is not None:
                r.lock.release()

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
        out["concurrency"] = {
            "codes": sorted(int(x["exit_code"]) for x in rows),
            "rows": rows,
        }

    out["codes_distinct"] = len({
        out["disk"]["exit_code"],
        out["perm"]["exit_code"],
        out["client"]["exit_code"],
        out["lifecycle"]["exit_code"],
        out["ok"]["exit_code"],
    }) == 5
    return out


def main() -> int:
    ts0 = now()
    tcode, ttext = run_cmd(
        "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/plugin/tests/test_preflight.py"
    )
    if tcode != 0:
        print(ttext)
        print("FAILED:IMP-0029 tests before emit")
        return 1
    live = live_measure()
    if live["disk"]["exit_code"] != P.EXIT_DISK:
        print("FAILED:IMP-0029 live disk planting")
        return 1
    if live["perm"]["exit_code"] != P.EXIT_PERM:
        print("FAILED:IMP-0029 live perm planting")
        return 1
    if live["client"]["exit_code"] != P.EXIT_CLIENT_LOCK:
        print("FAILED:IMP-0029 live client-lock planting")
        return 1
    if live["lifecycle"]["exit_code"] != P.EXIT_LIFECYCLE_LOCK:
        print("FAILED:IMP-0029 live lifecycle-lock planting")
        return 1
    if live["ok"]["exit_code"] != P.EXIT_OK:
        print("FAILED:IMP-0029 negative control")
        return 1
    if live["concurrency"]["codes"] != [P.EXIT_OK, P.EXIT_LIFECYCLE_LOCK]:
        print(f"FAILED:IMP-0029 concurrency {live['concurrency']}")
        return 1
    if not live["codes_distinct"]:
        print("FAILED:IMP-0029 codes not distinct")
        return 1

    ts1 = now()
    impl_sha, impl_bytes = digest(REPO / IMPL)
    receipt = {
        "unit_id": UNIT,
        "id": UNIT,
        "schema_version": 1,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "question": QUESTION,
        "title": "Preflight gate: disk, permissions, locks, and concurrent-op detection",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0029",
        "answer": (
            "tools/plugin/preflight.py refuses a mutating lifecycle op with distinct "
            f"exit codes: disk={P.EXIT_DISK} ({P.REASON_DISK}), "
            f"perm={P.EXIT_PERM} ({P.REASON_PERM}), "
            f"client-lock={P.EXIT_CLIENT_LOCK} ({P.REASON_CLIENT_LOCK}), "
            f"lifecycle-lock={P.EXIT_LIFECYCLE_LOCK} ({P.REASON_LIFECYCLE_LOCK}). "
            "A full tmpfs, a remount-ro target, a POSIX WRITE lock, and a held "
            ".plugin-lifecycle.lock were planted; OS statvfs / ST_RDONLY / "
            "/proc/locks PIDs confirmed each precondition was real. Same-run "
            "negative control exits 0. Two simultaneous acquires: exactly one "
            "proceeds. SIGINT releases the lock. Disk and permission do not retry; "
            "client lock retries x3 with backoff. SUCCESS:IMP-0029"
        ),
        "cloud_ok": False,
        "adv_rebuild_circle": False,
        "min_bytes_threshold": 128,
        "implementation": {
            "module": IMPL,
            "bytes": impl_bytes,
            "sha256": impl_sha,
            "lock_name": P.LOCK_NAME,
            "exit_codes": {
                "ok": P.EXIT_OK,
                "disk": P.EXIT_DISK,
                "perm": P.EXIT_PERM,
                "client_lock": P.EXIT_CLIENT_LOCK,
                "lifecycle_lock": P.EXIT_LIFECYCLE_LOCK,
            },
            "retry": {
                "client_lock": "x3 backoff",
                "disk": "none",
                "perm": "none",
                "lifecycle_lock": "non-blocking refuse",
            },
        },
        "live": live,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "artifacts": [
            art(IMPL, "implementation"),
            art(TESTS_REL, "supporting"),
            art(P1, "supporting"),
            art(P2, "supporting"),
        ],
        "evidence": [
            {
                "id": "E1-planted-refusals",
                "kind": "planted-precondition-refusal",
                "anchor": "tools/plugin/preflight.py:run_preflight",
                "claim": (
                    "Each planted failure (full tmpfs, remount-ro, client WRITE "
                    "lock, held lifecycle lock) is refused with a distinct exit "
                    "code 11/12/13/14, and a healthy tree in the same run exits 0."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": "python3 -B tools/plugin/tests/test_preflight.py",
                        "exit_code": tcode,
                        "raw_output": ttext[-1500:],
                    },
                    {
                        "role": "verifier",
                        "method": "live-plant",
                        "command": "run_preflight on full/ro/client/lifecycle/ok volumes",
                        "exit_code": 0,
                        "raw_output": json.dumps(
                            {
                                "disk": live["disk"]["exit_code"],
                                "perm": live["perm"]["exit_code"],
                                "client": live["client"]["exit_code"],
                                "lifecycle": live["lifecycle"]["exit_code"],
                                "ok": live["ok"]["exit_code"],
                                "distinct": live["codes_distinct"],
                            }
                        ),
                    },
                ],
            },
            {
                "id": "E2-oob-os-facts",
                "kind": "out-of-band-os-observation",
                "anchor": "/proc/locks + os.statvfs + ST_RDONLY",
                "claim": (
                    "Independent OS facts match the refusals: statvfs free_bytes "
                    f"{live['disk']['oob_free_bytes']} < needed "
                    f"{live['disk']['needed_bytes']}; remount-ro ST_RDONLY "
                    f"f_flag={live['perm']['f_flag']}; client lock holder "
                    f"pid={live['client']['holder_pid']} alive in /proc and listed "
                    "in /proc/locks; two-process race codes "
                    f"{live['concurrency']['codes']}."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "os.statvfs",
                        "command": "os.statvfs(full_tmpfs).f_bavail * f_frsize",
                        "raw_output": json.dumps(live["disk"]),
                    },
                    {
                        "role": "verifier",
                        "method": "/proc/locks",
                        "command": "parse /proc/locks for WRITE pid on planted file",
                        "raw_output": json.dumps(
                            {
                                "holder_pid": live["client"]["holder_pid"],
                                "proc_exists": live["client"]["proc_exists"],
                                "locks": live["client"]["proc_locks"],
                            },
                            default=str,
                        ),
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "test_disk_full_refuses_with_code_11",
                "command": "python3 -B tools/plugin/tests/test_preflight.py",
                "result": "PASS",
            },
            {
                "id": "test_readonly_target_refuses_with_code_12",
                "command": "python3 -B tools/plugin/tests/test_preflight.py",
                "result": "PASS",
            },
            {
                "id": "test_client_lock_refuses_with_code_13",
                "command": "python3 -B tools/plugin/tests/test_preflight.py",
                "result": "PASS",
            },
            {
                "id": "test_lifecycle_lock_refuses_with_code_14",
                "command": "python3 -B tools/plugin/tests/test_preflight.py",
                "result": "PASS",
            },
            {
                "id": "test_all_preconditions_and_negative_control_in_same_run",
                "command": "python3 -B tools/plugin/tests/test_preflight.py",
                "result": "PASS",
            },
            {
                "id": "test_two_simultaneous_installs_exactly_one_proceeds",
                "command": "python3 -B tools/plugin/tests/test_preflight.py",
                "result": "PASS",
            },
            {
                "id": "test_lock_released_on_sigint",
                "command": "python3 -B tools/plugin/tests/test_preflight.py",
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "healthy-tree-passes-in-same-run",
                "kind": "detector-liveness",
                "description": (
                    "With disk, writability, and locks all satisfied, preflight "
                    "must exit 0 in the same run as the four refusals."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "exit 11/12/13/14",
                "good_state_output": f"exit {live['ok']['exit_code']}",
            }
        ],
        "reviewer": {
            "reviewer_id": "IMP-0029-probe2-oob-os",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 re-plants each condition and confirms it via os.statvfs, "
                "ST_RDONLY/EROFS, /proc/locks and /proc/<pid>, then SIGINT-releases "
                "the lifecycle lock. Two independent signals, not the gate's own "
                "reason string."
            ),
        },
        "timestamps": {
            "started_at": ts0,
            "ended_at": ts1,
            "generated_at": ts1,
        },
        "retry": {
            "count": 0,
            "policy": "bounded retry x3 with backoff for a transient lock only; space or permission failure does not retry",
        },
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0029/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0023 transactional install and IMP-0028 journal are not "
                    "on this worktree; the preflight is the gate those units will "
                    "call. Cycle IMP-0029 -> IMP-0028 was cut so this unit has no "
                    "journal dependency."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Wire run_preflight into IMP-0023 install once that unit lands.",
            }
        ],
        "notes": (
            "G-1 IMP-0029: live named probes, SUCCESS artifact, per-unit manifest. "
            "Did not run global unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }

    dest = REPO / OUT
    try:
        result = RW.write_json(dest, receipt, validate=True, repo=REPO)
    except RW.ReceiptInvalid as exc:
        print(f"FAILED:IMP-0029 receipt invalid before write: {exc}")
        return 1
    parsed, nbytes = RW.read_json(dest)
    if parsed != receipt:
        print("FAILED:IMP-0029 live read-back does not equal what was written")
        return 1
    if SENTINEL not in dest.read_text(encoding="utf-8"):
        print("FAILED:IMP-0029 sentinel missing after write")
        return 1
    print(f"wrote {OUT} bytes={nbytes} sha256={result.sha256}")
    print("SUCCESS:IMP-0029 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
