#!/usr/bin/env python3
"""IMP-0013 probe 1: two independent live signals for .cmd shim launch.

Signal 1: adapter Get-Command/PATHEXT resolve + argv launch of a .cmd shim.
Signal 2: real POSIX ``command -v`` (Git-Bash-class) on the same PATH, via
/bin/sh, not the adapter's walker.

A tool visible to only one shell is recorded as disagreement, not skipped.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ADAPTER_DIR = REPO / "release" / "platforms" / "windows"
sys.path.insert(0, str(ADAPTER_DIR))

from launch_adapter import (  # noqa: E402
    get_command,
    launch,
    posix_command_v_live,
    write_cmd_shim,
)


def main() -> int:
    adapter = ADAPTER_DIR / "launch_adapter.py"
    ps1 = ADAPTER_DIR / "Launch-Adapter.ps1"
    if not adapter.is_file() or adapter.stat().st_size < 200:
        print("FAILED:IMP-0013-probe1 adapter missing")
        return 1
    if not ps1.is_file() or ps1.stat().st_size < 200:
        print("FAILED:IMP-0013-probe1 Launch-Adapter.ps1 missing")
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0013-p1-") as tmp:
        d = Path(tmp)
        shim = write_cmd_shim(d, "shim-tool")
        dirs = [str(d)]
        gc = get_command("shim-tool", path_dirs=dirs)
        live_posix = posix_command_v_live("shim-tool", path_dirs=dirs)
        if gc is None:
            print("FAILED:IMP-0013-probe1 Get-Command/PATHEXT miss")
            return 1
        if Path(gc).resolve() != shim.resolve():
            print(f"FAILED:IMP-0013-probe1 resolved {gc!r} != {str(shim)!r}")
            return 1
        if live_posix is not None:
            print(
                "FAILED:IMP-0013-probe1 command -v unexpectedly hit "
                f"{live_posix!r} (would hide the .cmd finding)"
            )
            return 1
        resolution, proc = launch(
            "shim-tool",
            ["--probe1"],
            path_dirs=dirs,
            live_posix=True,
        )
        if proc.returncode != 0:
            print(f"FAILED:IMP-0013-probe1 launch rc={proc.returncode}")
            print(proc.stderr)
            return 1
        if "IMP-0013-SHIM-LAUNCHED" not in (proc.stdout or ""):
            print(f"FAILED:IMP-0013-probe1 stdout {proc.stdout!r}")
            return 1
        if "--probe1" not in (proc.stdout or ""):
            print(f"FAILED:IMP-0013-probe1 argv not forwarded {proc.stdout!r}")
            return 1
        if not resolution.disagreement:
            print("FAILED:IMP-0013-probe1 disagreement hidden")
            print(json.dumps(resolution.as_json(), indent=2))
            return 1
        if resolution.disagreement_kind != "pathext-shim-only":
            print(f"FAILED:IMP-0013-probe1 kind={resolution.disagreement_kind}")
            return 1
        if resolution.used_for_launch != gc:
            print("FAILED:IMP-0013-probe1 launch used a non-Get-Command path")
            return 1

        out = {
            "probe": "probe1-cmd-shim-disagreement",
            "unit_id": "IMP-0013",
            "host": os.uname().sysname if hasattr(os, "uname") else os.name,
            "signal1_get_command_path": gc,
            "signal1_launch_rc": proc.returncode,
            "signal1_stdout_token": "IMP-0013-SHIM-LAUNCHED",
            "signal2_command_v": live_posix,
            "signal2_method": "/bin/sh -c 'command -v \"$1\"'",
            "disagreement": True,
            "disagreement_kind": resolution.disagreement_kind,
            "disagreement_hidden": False,
            "argv_forwarded": True,
            "pass": True,
        }
        print(json.dumps(out, sort_keys=True))
        print(
            "get_command="
            + gc
            + " command_v="
            + repr(live_posix)
            + " disagreement="
            + resolution.disagreement_kind
            + " launch_rc="
            + str(proc.returncode)
        )
        print("SUCCESS:IMP-0013-probe1 cmd-shim Get-Command launch vs POSIX command -v")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
