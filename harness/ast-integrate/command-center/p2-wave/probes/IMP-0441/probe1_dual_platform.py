#!/usr/bin/env python3
"""Probe 1: both command-center gates exit 0 on LF and on CRLF working trees.

Linux CI is the LF tree. A Windows checkout under core.autocrlf=true is the
CRLF tree. The CLIs invoked are tools/command-center/validate.py and
tools/command-center/render.py --check, not re-implementations.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))
import eol_policy as eol  # noqa: E402


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="imp0441-p1-"))
    report = eol.dual_platform(tmp)
    payload = {
        "probe": "probe1-dual-platform-gates",
        "unit_id": "IMP-0441",
        "linux_lf_validate": report["linux_lf"]["validate"]["exit_code"],
        "linux_lf_render": report["linux_lf"]["render"]["exit_code"],
        "windows_crlf_validate": report["windows_crlf_sim"]["validate"]["exit_code"],
        "windows_crlf_render": report["windows_crlf_sim"]["render"]["exit_code"],
        "linux_green": report["linux_green"],
        "windows_green_after": report["windows_green_after"],
        "pass": report["linux_green"] and report["windows_green_after"],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        f"linux validate={payload['linux_lf_validate']} render={payload['linux_lf_render']} "
        f"windows-crlf validate={payload['windows_crlf_validate']} "
        f"render={payload['windows_crlf_render']}"
    )
    if not payload["pass"]:
        print("FAILED:IMP-0441-probe1 dual-platform gates not both green")
        print("linux:", report["linux_lf"])
        print("windows:", report["windows_crlf_sim"])
        return 1
    print("SUCCESS:IMP-0441-probe1 dual-platform gates exit 0 on LF and CRLF")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
