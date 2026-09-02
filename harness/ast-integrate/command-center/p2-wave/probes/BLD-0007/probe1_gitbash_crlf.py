#!/usr/bin/env python3
"""Probe 1: Git-Bash CRLF discrimination plus matrix honesty.

Re-runs the Git-Bash cell probe under host bash (must FAIL) and under
igncr-emulation (must PASS). A probe that passes in both measures nothing.
Also asserts the live receipt never marks a cell PASS and cites the probe path.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from crlf import discriminate  # noqa: E402
from validator import FORBIDDEN_CELL_STATUS, get_cells, validate_receipt_file  # noqa: E402

OUT = REPO / "command-center/receipts/BLD-0007.json"
PROBE = "command-center/p2-wave/probes/BLD-0007/cells/windows__git-bash-msys.sh"


def main() -> int:
    if not OUT.is_file():
        print("FAILED:BLD-0007-probe1 receipt absent")
        return 1
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    if "SUCCESS:BLD-0007" not in OUT.read_text(encoding="utf-8"):
        print("FAILED:BLD-0007-probe1 sentinel-absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:BLD-0007-probe1 self-declared:{doc.get('state')}")
        return 1
    errs = validate_receipt_file(OUT, REPO)
    if errs:
        print("FAILED:BLD-0007-probe1 validator", errs[:12])
        return 1
    crlf = discriminate(HERE / "cells" / "windows__git-bash-msys.sh")
    print(
        "crlf wsl_or_linux_bash_rc="
        f"{crlf['wsl_or_linux_bash']['rc']} "
        f"gitbash_emulator_rc={crlf['git_bash_igncr_emulator']['rc']} "
        f"ok={crlf['ok']} both_same={crlf['both_states_identical']}"
    )
    if not crlf["ok"]:
        print("FAILED:BLD-0007-probe1 discrimination silent or inverted")
        print(json.dumps(crlf, indent=2)[:3000])
        return 1
    git_cell = None
    for cell in get_cells(doc) or []:
        st = str(cell.get("status") or "")
        if st in FORBIDDEN_CELL_STATUS or st == "PASS":
            print(f"FAILED:BLD-0007-probe1 cell {cell.get('id')} status={st}")
            return 1
        if cell.get("id") == "windows__git-bash-msys":
            git_cell = cell
    if git_cell is None:
        print("FAILED:BLD-0007-probe1 git-bash cell missing")
        return 1
    if git_cell.get("status") == "PASS":
        print("FAILED:BLD-0007-probe1 git-bash claimed PASS")
        return 1
    if str(git_cell.get("probe_path") or "").replace("\\", "/") != PROBE:
        print(f"FAILED:BLD-0007-probe1 probe_path {git_cell.get('probe_path')}")
        return 1
    if not (REPO / PROBE).is_file():
        print("FAILED:BLD-0007-probe1 probe file absent")
        return 1
    if git_cell.get("status") != "NOT-CHECKED":
        print(
            "FAILED:BLD-0007-probe1 expected NOT-CHECKED on Linux for "
            f"Windows x Git Bash, got {git_cell.get('status')}"
        )
        return 1
    print("SUCCESS:BLD-0007-probe1 git-bash CRLF discrimination")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
