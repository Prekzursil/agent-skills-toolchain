#!/usr/bin/env python3
"""Named probe 1: scoped guard keeps the revision intact and the POSIX path live.

Two independent signals: (a) the child's observed argv and (b) the
filesystem effect of the path-carrying command.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from lab import CONVERTED_PATH, REVISION, run_live  # noqa: E402

UNIT = "TST-0190"


def main() -> int:
    report = run_live()
    checks = report["checks"]
    scoped = report["scoped_echo"]
    fs = report["scoped_fs"]
    if not checks["scoped_argv_ok"]:
        print(f"FAILED:{UNIT}-probe1 scoped argv did not keep revision and convert path")
        print(json.dumps(scoped, indent=2, sort_keys=True)[:4000])
        return 1
    if scoped["observed_argv"][1] != REVISION:
        print(f"FAILED:{UNIT}-probe1 revision mutated: {scoped['observed_argv'][1]!r}")
        return 1
    if scoped["observed_argv"][2] != CONVERTED_PATH:
        print(f"FAILED:{UNIT}-probe1 path not converted: {scoped['observed_argv'][2]!r}")
        return 1
    if scoped["msys_no_pathconv_global"] or scoped["child_msys_no_pathconv"]:
        print(f"FAILED:{UNIT}-probe1 MSYS_NO_PATHCONV was set globally")
        return 1
    if not checks["scoped_fs_ok"]:
        print(f"FAILED:{UNIT}-probe1 path-carrying command left no sandbox payload")
        print(json.dumps(fs, indent=2, sort_keys=True)[:4000])
        return 1
    if not checks["pathspec_ok"]:
        print(f"FAILED:{UNIT}-probe1 /README.md pathspec was rewritten under scoped mode")
        print(json.dumps(report["pathspec"], indent=2))
        return 1
    out = {
        "probe": "probe1-scoped-argv-and-fs",
        "unit_id": UNIT,
        "observed_argv": scoped["observed_argv"],
        "revision_intact": True,
        "posix_path_converted": True,
        "filesystem_payload_ok": True,
        "msys_no_pathconv_global": False,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"revision={REVISION!r} converted_path={CONVERTED_PATH!r} "
        f"fs_ok={fs['payload_ok']}"
    )
    print(f"SUCCESS:{UNIT}-probe1 scoped revision intact and POSIX path resolved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
