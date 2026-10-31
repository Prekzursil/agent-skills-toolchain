"""Rebuild one P2 wave-1 unit's artifact + receipts on Windows.

Usage: python _rebuild_unit.py ADV-XXXX

Runs the unit's own write_receipts.py main() with subprocess.run patched so the
POSIX "VAR=value python3 ..." command strings the unit scripts use work on
Windows exactly the way command-center/p2-wave/_measure_one_delivered.py runs
them (env-prefix extraction + g1_python wrapper). One unit per process.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WRAPPER = REPO / "_builder-shard0-w1" / "_win_compat_runpy.py"


def _patched_run(cmd, **kw):
    if isinstance(cmd, str):
        env = dict(os.environ)
        passed = kw.get("env")
        if isinstance(passed, dict):
            env.update(passed)
        while True:
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
            if m is None:
                break
            env[m.group(1)] = m.group(2).strip('"').strip("'")
            cmd = cmd[m.end():]
        if WRAPPER.is_file() and "python3" in cmd:
            exe = sys.executable.replace("\\", "/")
            cmd = cmd.replace("python3", f"{exe} {WRAPPER.as_posix()}", 1)
        kw["env"] = env
        kw["shell"] = True
    return subprocess._original_run(cmd, **kw)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: _rebuild_unit.py <UNIT-ID>")
        return 2
    uid = sys.argv[1]
    mod_path = REPO / "command-center" / "p2-wave" / "probes" / uid / "write_receipts.py"
    if not mod_path.is_file():
        print(f"FAILED:rebuild {uid} no write_receipts.py")
        return 2
    subprocess._original_run = subprocess.run
    subprocess.run = _patched_run
    spec = importlib.util.spec_from_file_location(f"{uid}_receipts", mod_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"{uid}_rebuild"] = mod
    spec.loader.exec_module(mod)
    try:
        rc = mod.main()
    except SystemExit as exc:
        rc = exc.code
    except Exception as exc:  # noqa: BLE001 - report, do not mask
        print(f"FAILED:rebuild {uid} {type(exc).__name__}: {exc}")
        return 1
    print(f"REBUILD {uid} rc={rc}")
    return int(rc or 0)


if __name__ == "__main__":
    raise SystemExit(main())
