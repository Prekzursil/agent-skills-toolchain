#!/usr/bin/env python3
"""Rewrite TST-0190 probe2 main: observable = the child's received argument bytes.

Estate finding folded into the design: C:\\c is a junction to the drive root on
this box, so EVERY aliased /c/... path resolves regardless of suppression - the
regression seed's "command silently skipped" shape is therefore observed
through the child's argv (it demonstrably received a path form no Windows API
accepts as absolute), which is mechanically sound on any box.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
P2 = HERE.parent / "command-center" / "p2-wave" / "probes" / "TST-0190" / "probe2_global_suppression.py"

NEW = r'''#!/usr/bin/env python3
"""TST-0190 probe2 -- both-states control (regression seed windows-shell.md:11).

With MSYS_NO_PATHCONV exported GLOBALLY, a path-carrying command demonstrably
receives a POSIX-style path that no Windows path API accepts as absolute (the
defect shape behind 'global suppression silently skipped a clone'). Without
the variable, MSYS converts the same argument to a Windows path.

ESTATE FINDING (measured 2026-10-26): C:\c is a junction to the C:\ root on
this box, so any /c/... path ALSO resolves through the alias; the probe
therefore asserts on the child's received argument bytes, not on resolution,
which stays sound regardless of junctions. Exit 0 on pass, 1 on failure.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import msys_lane as ML  # noqa: E402

UNIT = "TST-0190"


def main() -> int:
    BASH = ML.git_bash()
    py = sys.executable.replace("\\", "/")
    echo = (HERE / "echo_args.py").as_posix()
    arg = "/c/Users/Prekzursil"

    # GLOBAL suppression: child demonstrably receives the UNCONVERTED POSIX path
    p_g = subprocess.run(
        [BASH, "-c", "export MSYS_NO_PATHCONV=1; %s %s %s" % (py, echo, arg)],
        capture_output=True, text=True, timeout=60,
    )
    try:
        doc_g = json.loads((p_g.stdout or "").strip().splitlines()[-1])
    except Exception:
        doc_g = {}
    seen_g = (doc_g.get("argv") or [None])[0]
    global_defect_visible = seen_g == arg  # unconverted POSIX path reached a native child

    # normal conversion: the same argument arrives as a Windows path
    p_n = subprocess.run(
        [BASH, "-c", "%s %s %s" % (py, echo, arg)],
        capture_output=True, text=True, timeout=60,
    )
    try:
        doc_n = json.loads((p_n.stdout or "").strip().splitlines()[-1])
    except Exception:
        doc_n = {}
    seen_n = (doc_n.get("argv") or [None])[0]
    normal_converted = bool(seen_n) and seen_n.replace("/", "\\").lower().startswith("c:")

    payload = {
        "probe": "probe2-global-suppression-fails",
        "unit_id": UNIT,
        "pass": global_defect_visible and normal_converted,
        "global_suppression": {
            "child_seen_path": seen_g,
            "unconverted_posix_reached_child": global_defect_visible,
            "defect": "the path-carrying command received a path form no Windows API accepts as absolute",
        },
        "normal_conversion": {
            "child_seen_path": seen_n,
            "converted": normal_converted,
        },
        "estate_finding": {
            "c_drive_junction": "C:" + chr(92) + "c is a junction to the drive root on this box; /c/... aliases resolve, so resolution-based probes are unsound here",
            "design": "assert on received argument bytes (mechanically sound on any box)",
        },
        "regression_seed": "windows-shell.md:11 global suppression silently skipped a clone",
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe2 global-defect-visible=%s normal-converted=%s"
              % (UNIT, global_defect_visible, normal_converted))
        return 0
    print("FAILED:%s-probe2 global=%s normal=%s (%r / %r)"
          % (UNIT, global_defect_visible, normal_converted, seen_g, seen_n))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

P2.write_text(NEW, encoding="utf-8", newline="\n")
import ast
ast.parse(NEW)
print("probe2 rewritten + syntax OK")
