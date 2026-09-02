#!/usr/bin/env python3
"""Named probe 2: residue is detected, and revert-of-revert is not lossy.

Field: untracked cache path remaining after a tracked-only checkout, plus
byte identity of the work tree after revert-of-revert vs the changed
snapshot. Distinct from probe 1 (benchmark delta + git diff vs pre-change SHA).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from revert_restore import (  # noqa: E402
    CACHE_REL,
    SINGLE_SIGNAL_REJECTED,
    scenario_invertible,
    scenario_residue,
)

ART = REPO / "command-center/receipts/TST-0312.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0312-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"receipt unparseable {exc}")
    if not isinstance(doc, dict):
        return fail("receipt not an object")
    if doc.get("unit_id") != "TST-0312":
        return fail(f"unit_id {doc.get('unit_id')}")
    if "SUCCESS:TST-0312" not in text:
        return fail("sentinel absent")

    with tempfile.TemporaryDirectory(prefix="tst0312-p2-") as tmp:
        work = Path(tmp)
        residue = scenario_residue(work)
        invert = scenario_invertible(work)

    if not residue["pass"]:
        print(json.dumps(residue, indent=2, default=str)[:4000])
        return fail("residue was absorbed or not detected")
    if CACHE_REL not in residue["residue_paths"]:
        return fail(f"{CACHE_REL} not in residue_paths")
    if not residue["cache_still_present"]:
        return fail("cache vanished; control would be vacuous")
    after = residue["after_tracked_checkout"]
    if after["verdict"] != SINGLE_SIGNAL_REJECTED:
        return fail(f"residue verdict {after['verdict']}")
    if residue["bench_only_would_claim"] != SINGLE_SIGNAL_REJECTED:
        return fail("bench-only gate did not classify as single-signal")
    if not invert["pass"] or invert["lossy"]:
        print(json.dumps(invert, indent=2, default=str)[:4000])
        return fail("revert-of-revert was lossy")
    if not invert["tree_matches_changed_state"]:
        return fail("tree after revert-of-revert != changed snapshot")
    if float(invert["metric_after_revert_of_revert"]) != 25.0:
        return fail("changed-state metric not restored by revert-of-revert")
    if not invert["after_first_revert_restored"]:
        return fail("first revert did not restore baseline")

    rec_res = doc.get("residue_control") or {}
    if rec_res.get("pass") is not True or rec_res.get("detected_not_absorbed") is not True:
        return fail("receipt residue flag drift")
    if CACHE_REL not in (rec_res.get("residue_paths") or []):
        return fail("receipt residue path drift")
    rec_inv = doc.get("invertibility") or {}
    if rec_inv.get("pass") is not True or rec_inv.get("lossy") is not False:
        return fail("receipt invertibility flag drift")

    out = {
        "probe": "probe2-residue-and-invert",
        "unit_id": "TST-0312",
        "residue_paths": residue["residue_paths"],
        "cache_still_present": residue["cache_still_present"],
        "residue_verdict": after["verdict"],
        "detected_not_absorbed": residue["detected_not_absorbed"],
        "invert_pass": invert["pass"],
        "lossy": invert["lossy"],
        "metric_after_revert_of_revert": invert["metric_after_revert_of_revert"],
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"residue={out['residue_paths']} verdict={out['residue_verdict']} "
        f"invert_lossy={out['lossy']} metric={out['metric_after_revert_of_revert']}"
    )
    print("SUCCESS:TST-0312-probe2 residue detected; revert-of-revert not lossy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
