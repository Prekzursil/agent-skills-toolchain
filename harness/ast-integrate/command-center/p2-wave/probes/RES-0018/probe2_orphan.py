#!/usr/bin/env python3
"""Named probe 2: orphan inheritance, marker string + settings keys (second rail)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import SENTINEL, run_orphan_control  # noqa: E402

ART = REPO / "command-center" / "research" / "RES-0018.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:RES-0018-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        print("FAILED:RES-0018-probe2 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:RES-0018-probe2 self-declared", doc.get("state"))
        return 1

    with tempfile.TemporaryDirectory(prefix="res0018-p2-") as tmp:
        ctrl = run_orphan_control(Path(tmp))

    if not ctrl["both_states"]:
        print("FAILED:RES-0018-probe2 detector silent in a required state")
        print(json.dumps(ctrl, indent=2)[:2000])
        return 1
    if not ctrl["detector_silent_on_clean"]:
        print("FAILED:RES-0018-probe2 clean uninstall still inherited prior marker")
        return 1
    if not ctrl["detector_fires_on_naive"]:
        print("FAILED:RES-0018-probe2 naive uninstall control did not inherit")
        return 1
    if not ctrl["naive_uninstall_control"]["cache_left_on_disk"]:
        print("FAILED:RES-0018-probe2 naive control did not leave cache")
        return 1
    if ctrl["verdict"] != "NO_INHERIT":
        print("FAILED:RES-0018-probe2 verdict", ctrl["verdict"])
        return 1

    art_orphan = doc.get("orphan_verdict") or {}
    if art_orphan.get("classification") != "NO_INHERIT":
        print("FAILED:RES-0018-probe2 artifact orphan classification", art_orphan)
        return 1
    if art_orphan.get("detector_control_fires_on_naive_uninstall") is not True:
        print("FAILED:RES-0018-probe2 artifact missing naive-uninstall control")
        return 1

    payload = {
        "probe": "probe2-orphan-control",
        "unit_id": "RES-0018",
        "clean_inherited": ctrl["clean_uninstall"]["inherited_prior_marker"],
        "naive_inherited": ctrl["naive_uninstall_control"]["inherited_prior_marker"],
        "both_states": True,
        "verdict": ctrl["verdict"],
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        "clean_inherited=False naive_inherited=True both_states=True "
        f"verdict={ctrl['verdict']}"
    )
    print("SUCCESS:RES-0018-probe2 orphan control (clean vs naive uninstall)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
