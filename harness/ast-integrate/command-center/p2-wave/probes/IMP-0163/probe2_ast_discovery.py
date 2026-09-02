#!/usr/bin/env python3
"""Probe 2: AST discovery meta-test — planted unregistered adapter turns it red.

Both-states: live tree closed (silent on good); planted file fires; unlink restores.
Independent of probe1's suite pass/fail: this is the detector control.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from workflow_import.harness.discover import planted_unregistered_control  # noqa: E402
from workflow_import.harness.registry import REGISTERED_ADAPTER_IDS  # noqa: E402
from workflow_import.paths import ADAPTERS_DIR  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0163.json"


def main() -> int:
    ctrl = planted_unregistered_control()
    if not ctrl["pass"]:
        print(f"FAILED:IMP-0163-probe2 detector control {json.dumps(ctrl)}")
        return 1
    if set(ctrl["planted_ids"]) < set(REGISTERED_ADAPTER_IDS):
        print("FAILED:IMP-0163-probe2 plant scan dropped registered ids")
        return 1
    leftover = ADAPTERS_DIR / "planted_unregistered.py"
    if leftover.is_file():
        print("FAILED:IMP-0163-probe2 plant file leaked")
        return 1

    if not ART.is_file():
        print("FAILED:IMP-0163-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0163-probe2 self-declared {doc.get('state')}")
        return 1
    disc = (doc.get("discovery") or {})
    if disc.get("planted_unregistered_fails") is not True:
        print("FAILED:IMP-0163-probe2 receipt missing planted_unregistered_fails")
        return 1
    if disc.get("live_closed") is not True:
        print("FAILED:IMP-0163-probe2 receipt live_closed not true")
        return 1
    if "SUCCESS:IMP-0163" not in text:
        print("FAILED:IMP-0163-probe2 sentinel-absent")
        return 1

    print(json.dumps(ctrl, sort_keys=True))
    print("fired_on_bad=True silent_on_good=True restore_closed=True")
    print("SUCCESS:IMP-0163-probe2 ast-discovery")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
