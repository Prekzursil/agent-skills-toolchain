#!/usr/bin/env python3
"""Probe 1: both-states index/install control and collapsed-bit rejection.

Remove a capability from the index while leaving it installed. The proposed
signal must distinguish NOT_SELECTED from INDEX_MISS_INSTALLED. A collapsed
unavailable bit must be the same in both states. Artifact must record the
same codes. Also checks mid-task activation failure and deactivate residual.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import trees as T  # noqa: E402

ART = REPO / "command-center/phase3/A4/FAILURE-MODES.json"


def main() -> int:
    ctrl = T.both_states()
    checks = [
        ("pass", ctrl.get("pass")),
        ("codes_differ", ctrl.get("codes_differ")),
        ("collapsed_same", ctrl.get("collapsed_same_in_both_states")),
        ("install_survived", ctrl.get("install_file_survived_index_edit")),
    ]
    print(f"not_selected={ctrl.get('not_selected_code')}")
    print(f"index_miss_installed={ctrl.get('index_miss_installed_code')}")
    print(f"collapsed_a={ctrl.get('collapsed_state_a')} collapsed_b={ctrl.get('collapsed_state_b')}")
    print(f"midtask={ctrl.get('activation_failed_midtask', {}).get('code')}")
    print(f"residual={ctrl.get('deactivated_residual', {}).get('code')}")
    print(f"not_installed={ctrl.get('truly_not_installed', {}).get('code')}")
    for name, ok in checks:
        print(f"{name}={ok}")
        if not ok:
            print(f"FAILED:ARC-0026-probe1 {name}")
            return 1
    if ctrl.get("not_selected_code") != "NOT_SELECTED":
        print("FAILED:ARC-0026-probe1 expected NOT_SELECTED")
        return 1
    if ctrl.get("index_miss_installed_code") != "INDEX_MISS_INSTALLED":
        print("FAILED:ARC-0026-probe1 expected INDEX_MISS_INSTALLED")
        return 1
    if ctrl.get("collapsed_state_a") != "UNAVAILABLE":
        print("FAILED:ARC-0026-probe1 collapsed bit did not fire")
        return 1

    if not ART.is_file():
        print("FAILED:ARC-0026-probe1 FAILURE-MODES.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0026-probe1 self-declared {doc.get('state')}")
        return 1
    bs = doc.get("both_states") or {}
    if bs.get("not_selected_code") != "NOT_SELECTED":
        print("FAILED:ARC-0026-probe1 artifact NOT_SELECTED drift")
        return 1
    if bs.get("index_miss_installed_code") != "INDEX_MISS_INSTALLED":
        print("FAILED:ARC-0026-probe1 artifact INDEX_MISS_INSTALLED drift")
        return 1
    if bs.get("collapsed_same_in_both_states") is not True:
        print("FAILED:ARC-0026-probe1 artifact missing collapsed control")
        return 1
    if "SUCCESS:ARC-0026" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0026-probe1 sentinel absent")
        return 1
    print("SUCCESS:ARC-0026-probe1 both-states signal distinguishes index-miss from not-selected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
