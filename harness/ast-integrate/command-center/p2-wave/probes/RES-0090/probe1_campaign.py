#!/usr/bin/env python3
"""Probe 1: re-run the mutation campaign; operators hashed before rates; control killed."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from lib import (  # noqa: E402
    HOOK_REL,
    OPS_PATH,
    campaign,
    load_operators,
    operators_sha256,
)

ART = REPO / "command-center" / "research" / "RES-0090.json"
SENTINEL = (
    "SUCCESS:RES-0090 in the receipt AND a pre-published operator set plus a "
    "measured survival rate on one real hook with a killed control"
)


def main() -> int:
    ops = load_operators()
    if not ops.get("published_before_any_rate"):
        print("FAILED:RES-0090-probe1 operators not marked published_before_any_rate")
        return 1
    if "rate" in ops or "survival_rate" in ops:
        print("FAILED:RES-0090-probe1 operator file contains a rate")
        return 1
    live_hash = operators_sha256()
    result = campaign()
    if result["operators_sha256"] != live_hash:
        print("FAILED:RES-0090-probe1 operator hash changed during campaign")
        return 1
    if not result["operators_hashed_before_rates"]:
        print("FAILED:RES-0090-probe1 hash-before-rates flag false")
        return 1
    if result["target_path"] != HOOK_REL:
        print("FAILED:RES-0090-probe1 wrong target", result["target_path"])
        return 1
    if not result["control_killed"]:
        print("FAILED:RES-0090-probe1 control mutant survived")
        return 1
    if result["mutants_total"] < 3:
        print("FAILED:RES-0090-probe1 too few mutants")
        return 1
    control = next(m for m in result["mutants"] if m["id"] == result["control_operator_id"])
    if not control["killed"]:
        print("FAILED:RES-0090-probe1 named control not killed")
        return 1

    if not ART.is_file():
        print("FAILED:RES-0090-probe1 artifact missing")
        return 1
    art = json.loads(ART.read_text(encoding="utf-8"))
    blob = ART.read_text(encoding="utf-8")
    if str(art.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:RES-0090-probe1 self-declared", art.get("state"))
        return 1
    if SENTINEL not in blob or "SUCCESS:RES-0090" not in blob:
        print("FAILED:RES-0090-probe1 sentinel absent")
        return 1
    pub = art.get("operator_set") or {}
    if pub.get("sha256") != live_hash:
        print("FAILED:RES-0090-probe1 artifact operator sha256 mismatch")
        return 1
    surv = art.get("survival") or {}
    if int(surv.get("survived") or -1) != result["survived"]:
        print("FAILED:RES-0090-probe1 artifact survived count mismatch")
        return 1
    if int(surv.get("killed") or -1) != result["killed"]:
        print("FAILED:RES-0090-probe1 artifact killed count mismatch")
        return 1
    if not (art.get("killed_control") or {}).get("killed"):
        print("FAILED:RES-0090-probe1 artifact control not killed")
        return 1
    if not OPS_PATH.is_file():
        print("FAILED:RES-0090-probe1 operators.json missing")
        return 1

    payload = {
        "probe": "probe1-campaign",
        "operators_sha256": live_hash,
        "mutants_total": result["mutants_total"],
        "killed": result["killed"],
        "survived": result["survived"],
        "rate": result["rate"],
        "control_killed": result["control_killed"],
        "control_id": result["control_operator_id"],
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"ops={live_hash[:12]} killed={result['killed']}/{result['mutants_total']} "
        f"survived={result['survived']} control_killed={result['control_killed']}"
    )
    print("SUCCESS:RES-0090-probe1 pre-published operators; live campaign; control killed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
