#!/usr/bin/env python3
"""Probe 1: real Linux GNU bash + bash -n on every shipped script.

Independent of the launch adapter: this process asks bash itself for uname,
/proc/version, and `bash -n`. Git Bash / /mnt/c is a fail, not a skip.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center/receipts/IMP-0015.json"
SCRIPTS = REPO / "release/platforms/linux/scripts"
SENTINEL = "SUCCESS:IMP-0015"


def bash_out(args: list[str]) -> tuple[int, str]:
    p = subprocess.run(
        args,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0015-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        print("FAILED:IMP-0015-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:IMP-0015-probe1 self-declared", doc.get("state"))
        return 1

    py_sys = os.uname().sysname
    rc_u, bash_uname = bash_out(["bash", "-c", "uname -s"])
    rc_v, bash_ver = bash_out(["bash", "--version"])
    bash_ver1 = (bash_ver.splitlines() or [""])[0]
    rc_p, bash_exe = bash_out(["bash", "-c", "readlink -f /proc/$$/exe || command -v bash"])
    proc_version = ""
    proc_path = Path("/proc/version")
    if proc_path.is_file():
        proc_version = proc_path.read_text(encoding="utf-8", errors="replace").splitlines()[0]
    cwd = str(REPO)
    mnt_c = Path("/mnt/c").exists()
    cwd_mnt = cwd == "/mnt/c" or cwd.startswith("/mnt/c/")

    host = {
        "python_uname": py_sys,
        "bash_uname": bash_uname,
        "bash_uname_rc": rc_u,
        "bash_version": bash_ver1,
        "bash_exe": bash_exe,
        "proc_version": proc_version,
        "mnt_c_exists": mnt_c,
        "cwd": cwd,
        "cwd_is_mnt_c": cwd_mnt,
    }

    if py_sys != "Linux" or bash_uname != "Linux" or rc_u != 0:
        print(json.dumps(host, indent=2))
        print("FAILED:IMP-0015-probe1 not real Linux")
        return 1
    blo = bash_ver1.lower()
    if any(tok in blo for tok in ("msys", "mingw", "cygwin")):
        print(json.dumps(host, indent=2))
        print("FAILED:IMP-0015-probe1 Git Bash / MSYS")
        return 1
    if "gnu bash" not in blo:
        print(json.dumps(host, indent=2))
        print("FAILED:IMP-0015-probe1 not GNU bash")
        return 1
    if cwd_mnt:
        print(json.dumps(host, indent=2))
        print("FAILED:IMP-0015-probe1 cwd is /mnt/c (WSL-on-Windows checkout)")
        return 1
    if rc_p != 0 or "bash" not in bash_exe:
        print(json.dumps(host, indent=2))
        print("FAILED:IMP-0015-probe1 bash exe unresolved")
        return 1

    scripts = sorted(SCRIPTS.glob("*.sh"))
    if len(scripts) < 3:
        print(f"FAILED:IMP-0015-probe1 script count {len(scripts)}")
        return 1

    rows = []
    for src in scripts:
        raw = src.read_bytes()
        if b"\r" in raw:
            print(f"FAILED:IMP-0015-probe1 CR in shipped {src}")
            return 1
        rc_n, nout = bash_out(["bash", "-n", str(src)])
        rows.append(
            {
                "path": src.relative_to(REPO).as_posix(),
                "bash_n_rc": rc_n,
                "bytes": len(raw),
                "has_cr": False,
            }
        )
        if rc_n != 0:
            print(json.dumps({"host": host, "syntax": rows, "err": nout}, indent=2))
            print(f"FAILED:IMP-0015-probe1 bash -n {src.name}")
            return 1

    payload = {
        "probe": "probe1-linux-bash-syntax",
        "unit_id": "IMP-0015",
        "pass": True,
        "host": host,
        "two_linux_signals": True,
        "methods": [
            "python os.uname().sysname",
            "bash -c 'uname -s' + bash --version + /proc/$$/exe",
        ],
        "scripts": rows,
        "independent_of_adapter": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print("SUCCESS:IMP-0015-probe1 real Linux GNU bash -n on shipped scripts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
