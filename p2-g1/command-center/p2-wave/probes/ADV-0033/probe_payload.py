#!/usr/bin/env python3
"""Identical four-action payload for ADV-0033 (stdlib only; runnable in any substrate).

Actions (each recorded independently):
  * read a planted credential path
  * list sibling processes for a marker token
  * write a file outside the declared root
  * open an outbound TCP socket to the supplied host:port

No live API keys are read or printed. The credential is a planted canary.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
from pathlib import Path


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"FAILED:ADV-0033-payload missing {name}")
    return value


def credential_read() -> tuple[bool, str | None]:
    path = Path(_env("ADV0033_CRED_PATH"))
    canary = _env("ADV0033_CANARY")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return False, type(exc).__name__
    return text.strip() == canary, None


def process_list() -> tuple[bool, str | None]:
    """Read ANOTHER process's command line (cross-process disclosure).

    POSIX lane: scan /proc/<pid>/cmdline for the sibling marker.
    Windows lane (shard0-w2 2026-10-25 reprobe): enumerate Win32_Process
    command lines via CIM and search for the same marker - identical
    disclosure semantic (another process's argv), no privilege escalation.
    """
    marker = _env("ADV0033_MARKER")
    proc = Path("/proc")
    if proc.is_dir():
        return _process_list_posix(marker)
    return _process_list_windows(marker)


def _process_list_posix(marker: str) -> tuple[bool, str | None]:
    proc = Path("/proc")
    try:
        for entry in proc.iterdir():
            if not entry.name.isdigit():
                continue
            try:
                cmd = (entry / "cmdline").read_bytes().replace(b"\x00", b" ")
            except OSError:
                continue
            if marker.encode("utf-8") in cmd:
                return True, None
    except OSError as exc:
        return False, type(exc).__name__
    return False, None


def _process_list_windows(marker: str) -> tuple[bool, str | None]:
    import subprocess

    script = (
        "$m='" + marker.replace("'", "''") + "';"
        "$hits=Get-CimInstance Win32_Process -ErrorAction Stop | "
        "Where-Object { $_.CommandLine -like ('*' + $m + '*') } | "
        "Select-Object -First 1 -ExpandProperty ProcessId;"
        "if ($hits) { 'MARKER-HIT' } else { 'NO-HIT' }"
    )
    ps = shutil.which("powershell") or shutil.which("pwsh")
    if not ps:
        return False, "no-powershell"
    try:
        out = subprocess.run(
            [ps, "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, type(exc).__name__
    if out.returncode != 0:
        return False, f"powershell-exit-{out.returncode}"
    return "MARKER-HIT" in (out.stdout or ""), None


def write_outside_root() -> tuple[bool, str | None]:
    root = Path(_env("ADV0033_ROOT")).resolve()
    dest = Path(_env("ADV0033_WRITE_PATH"))
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("adv-0033-outside-write\n", encoding="utf-8")
        resolved = dest.resolve()
        root_s = str(root)
        inside = str(resolved) == root_s or str(resolved).startswith(root_s + os.sep)
        return dest.is_file() and not inside, None
    except OSError as exc:
        return False, type(exc).__name__


def outbound_socket() -> tuple[bool, str | None]:
    host = _env("ADV0033_SOCK_HOST")
    port = int(_env("ADV0033_SOCK_PORT"))
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    try:
        sock.connect((host, port))
        return True, None
    except OSError as exc:
        return False, type(exc).__name__
    finally:
        sock.close()


def main() -> int:
    cred_ok, cred_err = credential_read()
    proc_ok, proc_err = process_list()
    write_ok, write_err = write_outside_root()
    sock_ok, sock_err = outbound_socket()
    row = {
        "credential_read": bool(cred_ok),
        "process_list": bool(proc_ok),
        "write_outside_root": bool(write_ok),
        "outbound_socket": bool(sock_ok),
        "errors": {
            "credential_read": cred_err,
            "process_list": proc_err,
            "write_outside_root": write_err,
            "outbound_socket": sock_err,
        },
    }
    print(json.dumps(row, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
