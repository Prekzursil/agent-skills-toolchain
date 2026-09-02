#!/usr/bin/env python3
"""Named probe 2: both-states control — global MSYS_NO_PATHCONV skips the clone.

With the variable set globally the path-carrying command must FAIL (no
sandbox payload). The same command under scoped mode must succeed. A
second shell (bash -lc) re-observes the scoped argv.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from lab import POSIX_PATH, run_live  # noqa: E402

UNIT = "TST-0190"


def main() -> int:
    report = run_live()
    checks = report["checks"]
    glob_echo = report["global_echo"]
    glob_fs = report["global_fs"]
    scoped_fs = report["scoped_fs"]
    bash = report["bash_echo"]

    if not checks["global_argv_inverted"]:
        print(f"FAILED:{UNIT}-probe2 global suppress still converted the POSIX path")
        print(json.dumps(glob_echo, indent=2, sort_keys=True)[:4000])
        return 1
    if glob_echo["observed_argv"][2] != POSIX_PATH:
        print(
            f"FAILED:{UNIT}-probe2 expected unconverted {POSIX_PATH!r} "
            f"got {glob_echo['observed_argv'][2]!r}"
        )
        return 1
    if glob_echo["child_msys_no_pathconv"] != "1":
        print(f"FAILED:{UNIT}-probe2 child env missing MSYS_NO_PATHCONV=1")
        return 1
    if not checks["global_fs_failed"]:
        print(f"FAILED:{UNIT}-probe2 global suppress still wrote the sandbox clone")
        print(json.dumps(glob_fs, indent=2, sort_keys=True)[:4000])
        return 1
    if not checks["scoped_fs_ok"]:
        print(f"FAILED:{UNIT}-probe2 scoped mode did not write the clone payload")
        print(json.dumps(scoped_fs, indent=2, sort_keys=True)[:4000])
        return 1
    if glob_fs["sandbox_exists"] is True:
        print(f"FAILED:{UNIT}-probe2 inversion not visible: sandbox marker present")
        return 1
    if not checks["bash_ok"]:
        print(f"FAILED:{UNIT}-probe2 bash re-observation diverged from python argv")
        print(json.dumps(bash, indent=2, sort_keys=True)[:4000])
        return 1

    out = {
        "probe": "probe2-global-suppress-control",
        "unit_id": UNIT,
        "global_path_unconverted": True,
        "global_clone_skipped": True,
        "scoped_clone_ok": True,
        "bash_argv_agrees": True,
        "msys_no_pathconv": glob_echo["child_msys_no_pathconv"],
        "global_write_returncode": glob_fs["returncode"],
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"global_path={glob_echo['observed_argv'][2]!r} "
        f"global_fs_exists={glob_fs['sandbox_exists']} "
        f"scoped_fs_ok={scoped_fs['payload_ok']} bash_ok={checks['bash_ok']}"
    )
    print(
        f"SUCCESS:{UNIT}-probe2 global MSYS_NO_PATHCONV skips the clone; "
        "scoped mode does not"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
