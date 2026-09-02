#!/usr/bin/env python3
"""Probe 2: UI-only control; all-public mutant must fail the classifier."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import classify as C  # noqa: E402
import evidence as E  # noqa: E402


def main() -> int:
    path = E.REPO / E.ARTIFACT_REL
    if not path.is_file():
        print("FAILED:RES-0032-probe2 artifact missing")
        return 1
    doc = json.loads(path.read_text(encoding="utf-8"))
    rows = doc.get("rows") or []
    ok, why = C.control_ui_only_and_discriminating(rows)
    print(f"live_control ok={ok} {why}")
    if not ok:
        print("FAILED:RES-0032-probe2 live table fails UI-only/discriminating control")
        return 1
    ui = [r for r in rows if r.get("verdict") == "UI-only"]
    print("ui_only_rows=" + ",".join(str(r.get("id")) for r in ui))
    if "github-copilot-workspace" not in {r.get("id") for r in ui}:
        print("FAILED:RES-0032-probe2 Copilot Workspace is not UI-only")
        return 1
    mutant = copy.deepcopy(rows)
    for r in mutant:
        r["verdict"] = "public-versioned-API"
    mok, mwhy = C.control_ui_only_and_discriminating(mutant)
    print(f"all_public_mutant ok={mok} {mwhy}")
    if mok:
        print("FAILED:RES-0032-probe2 all-public mutant was accepted")
        return 1
    empty_ok, empty_why = C.control_ui_only_and_discriminating([])
    print(f"empty_mutant ok={empty_ok} {empty_why}")
    if empty_ok:
        print("FAILED:RES-0032-probe2 empty table accepted")
        return 1
    print("SUCCESS:RES-0032-probe2 UI-only control and discriminating classifier")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
