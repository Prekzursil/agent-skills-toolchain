#!/usr/bin/env python3
"""Probe 2: out-of-band OS observation that planted preconditions were real.

Catalog signal (2): independent of the gate's reason string. This probe
re-plants each failure and confirms it via OS APIs the preflight does not
own as its pass/fail:

  * os.statvfs f_bavail*f_frsize for the full tmpfs
  * statvfs f_flag & ST_RDONLY (and EROFS on a write) for the read-only mount
  * /proc/locks + /proc/<pid> for the lock-holder PID
  * after SIGINT, /proc/locks no longer lists that WRITE lock

A refusal with no matching OS fact is a false positive.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import preflight as P  # noqa: E402

UNIT = "IMP-0029"
RECEIPT = REPO / "command-center" / "receipts" / "IMP-0029.json"
PAYLOAD = 64 * 1024
BACKUP = 64 * 1024
NEEDED = PAYLOAD + BACKUP
ST_RDONLY = int(getattr(os, "ST_RDONLY", 1))


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def _tree(vol: Path) -> None:
    (vol / "plugin.json").write_text('{"name":"demo"}\n', encoding="utf-8")
    (vol / "commands").mkdir(exist_ok=True)
    (vol / "commands" / "ping.md").write_text("# ping\n", encoding="utf-8")


def _independent_free(path: Path) -> dict:
    """Duplicate statvfs read (not P.os_free_bytes)."""
    st = os.statvfs(os.fspath(path))
    return {
        "f_bavail": int(st.f_bavail),
        "f_frsize": int(st.f_frsize),
        "f_flag": int(getattr(st, "f_flag", 0)),
        "free_bytes": int(st.f_bavail) * int(st.f_frsize),
        "rdonly": bool(int(getattr(st, "f_flag", 0)) & ST_RDONLY),
    }


def _independent_proc_locks() -> list[dict]:
    """Duplicate /proc/locks parser (not P.parse_proc_locks)."""
    rows: list[dict] = []
    raw = Path("/proc/locks").read_text(encoding="utf-8", errors="replace")
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) < 6:
            continue
        try:
            pid = int(parts[4])
            maj_s, min_s, ino_s = parts[5].split(":")
            maj, minor, ino = int(maj_s, 16), int(min_s, 16), int(ino_s, 10)
        except ValueError:
            continue
        rows.append(
            {
                "raw": line.strip(),
                "kind": parts[1],
                "mode": parts[3],
                "pid": pid,
                "major": maj,
                "minor": minor,
                "ino": ino,
            }
        )
    return rows


def _locks_for(path: Path, rows: list[dict]) -> list[dict]:
    st = path.stat()
    maj, minor, ino = os.major(st.st_dev), os.minor(st.st_dev), int(st.st_ino)
    return [
        r
        for r in rows
        if r["major"] == maj and r["minor"] == minor and r["ino"] == ino
    ]


def _pid_cmdline(pid: int) -> str:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\x00", b" ")
        return raw.decode("utf-8", "replace")[:200]
    except OSError:
        return ""


def main() -> int:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size < 200:
        return fail("receipt missing")
    text = RECEIPT.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:IMP-0029" not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"receipt state={doc.get('state')}")

    report: dict = {"probe": "probe2-oob-os", "unit_id": UNIT}

    with P.TmpfsVolume("2M") as full:
        _tree(full)
        P.fill_volume(full, leave_free=0)
        oob = _independent_free(full)
        if oob["free_bytes"] >= NEEDED:
            return fail(f"planted full volume still has free={oob['free_bytes']}")
        r = P.run_preflight(
            full, payload_bytes=PAYLOAD, backup_bytes=BACKUP, acquire=False,
            client_retries=1, backoff_s=0,
        )
        if r.exit_code != P.EXIT_DISK:
            return fail(f"disk refuse missing code={r.exit_code} oob={oob}")
        if int(r.observation["disk"]["free_bytes"]) != oob["free_bytes"]:
            return fail("disk observation disagrees with independent statvfs")
        report["disk"] = {
            "oob_free_bytes": oob["free_bytes"],
            "needed": NEEDED,
            "exit_code": r.exit_code,
            "false_positive": False,
        }

    with P.TmpfsVolume("2M") as ro:
        _tree(ro)
        P.remount_ro(ro)
        oob = _independent_free(ro)
        if not oob["rdonly"]:
            return fail(f"ST_RDONLY not set independently f_flag={oob['f_flag']}")
        erofs = False
        try:
            (ro / "should-fail").write_text("x", encoding="utf-8")
        except OSError as exc:
            erofs = exc.errno == 30  # EROFS
        if not erofs:
            return fail("independent write on ro mount did not raise EROFS")
        r = P.run_preflight(
            ro, payload_bytes=1024, backup_bytes=1024, acquire=False,
            client_retries=1, backoff_s=0,
        )
        if r.exit_code != P.EXIT_PERM:
            return fail(f"perm refuse missing code={r.exit_code}")
        report["readonly"] = {
            "f_flag": oob["f_flag"],
            "rdonly": True,
            "erofs": True,
            "exit_code": r.exit_code,
        }

    holder = None
    with P.TmpfsVolume("2M") as client:
        _tree(client)
        payload = client / "plugin.json"
        holder = P.spawn_lock_holder(payload)
        try:
            if not Path(f"/proc/{holder.pid}").is_dir():
                return fail(f"holder pid {holder.pid} not in /proc")
            rows = _independent_proc_locks()
            matched = [
                r for r in _locks_for(payload, rows) if r["mode"] == "WRITE"
            ]
            if not matched:
                return fail("independent /proc/locks has no WRITE on planted file")
            if not any(r["pid"] == holder.pid for r in matched):
                return fail(f"lock pid != holder {holder.pid} matched={matched}")
            r = P.run_preflight(
                client, payload_bytes=1024, backup_bytes=1024, acquire=False,
                client_retries=1, backoff_s=0,
            )
            if r.exit_code != P.EXIT_CLIENT_LOCK:
                return fail(f"client refuse missing code={r.exit_code}")
            report["client_lock"] = {
                "holder_pid": holder.pid,
                "proc_exists": True,
                "cmdline": _pid_cmdline(holder.pid),
                "proc_locks": matched,
                "exit_code": r.exit_code,
            }
        finally:
            P.stop_holder(holder)

    with P.TmpfsVolume("4M") as held:
        _tree(held)
        proc = subprocess.Popen(
            [
                sys.executable,
                "-B",
                str(PLUGIN / "preflight.py"),
                "--target",
                str(held),
                "--payload-bytes",
                "1024",
                "--backup-bytes",
                "1024",
                "--acquire",
                "--hold-seconds",
                "30",
                "--client-retries",
                "1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert proc.stdout is not None
        ready = ""
        t0 = time.monotonic()
        while time.monotonic() - t0 < 8:
            line = proc.stdout.readline()
            if not line:
                break
            ready += line
            if "READY pid=" in line:
                break
        if "READY pid=" not in ready:
            proc.kill()
            return fail(f"hold child never READY {ready!r}")
        lock_path = held / P.LOCK_NAME
        before = [
            r
            for r in _locks_for(lock_path, _independent_proc_locks())
            if r["mode"] == "WRITE" and r["pid"] == proc.pid
        ]
        if not before:
            proc.kill()
            return fail("independent /proc/locks missing child WRITE lock")
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
            return fail("SIGINT child hung")
        time.sleep(0.05)
        after = [
            r
            for r in _locks_for(lock_path, _independent_proc_locks())
            if r["mode"] == "WRITE" and Path(f"/proc/{r['pid']}").is_dir()
        ]
        if after:
            return fail(f"WRITE lock survived SIGINT {after}")
        report["sigint_release"] = {
            "child_pid": proc.pid,
            "before": before,
            "after": after,
            "released": True,
        }

    report["pass"] = True
    print(json.dumps(report, sort_keys=True, default=str))
    print(
        "SUCCESS:IMP-0029-probe2 oob statvfs + ST_RDONLY/EROFS + "
        "/proc/locks pid + SIGINT release"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
