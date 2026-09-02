#!/usr/bin/env python3
"""Probe 2: removal control + $schema poison (false-healthy P0 detector)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from common import (  # noqa: E402
    COMPLETION_SENTINEL,
    OUTPUT_REL,
    POISON_KEY,
    REMOVED_HOOK_ID,
    UNIT_ID,
)
from scenario import run_poison_schema, run_removal_control  # noqa: E402
from schema_local import domain  # noqa: E402


def main() -> int:
    art_path = REPO / OUTPUT_REL
    if not art_path.is_file():
        print("FAILED:CNF-0096-probe2 artifact missing")
        return 1
    text = art_path.read_text(encoding="utf-8")
    if COMPLETION_SENTINEL not in text:
        print("FAILED:CNF-0096-probe2 sentinel-absent")
        return 1
    doc = json.loads(text)
    payload = domain(doc)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0096-probe2 self-declared", doc.get("state"))
        return 1

    with tempfile.TemporaryDirectory(prefix="cnf0096-p2-") as tmp_s:
        tmp = Path(tmp_s)
        removal = run_removal_control(tmp / "removal")
        poison = run_poison_schema(tmp / "poison")

    removed = removal["removed_row"]
    if removed["id"] != REMOVED_HOOK_ID:
        print("FAILED:CNF-0096-probe2 wrong removed id", removed["id"])
        return 1
    if not (
        removed["installed"]
        and not removed["loaded"]
        and not removed["fired"]
        and removed.get("not_observed")
    ):
        print("FAILED:CNF-0096-probe2 removal did not report not-fired", removed)
        return 1
    if not removal["detected"]:
        print("FAILED:CNF-0096-probe2 removal control not detected")
        return 1
    if not removal["others_fired"]:
        print("FAILED:CNF-0096-probe2 sibling hooks failed after removal")
        return 1
    if removed["installed"] == removed["loaded"] or removed["loaded"] == removed["fired"] and removed["installed"] == removed["fired"]:
        # installed=true, loaded=false, fired=false is the required split
        if not (removed["installed"] and not removed["loaded"] and not removed["fired"]):
            print("FAILED:CNF-0096-probe2 three states collapsed", removed)
            return 1

    if poison["load_reason"] != "hook-not-loaded:poison-$schema-zero-load":
        print("FAILED:CNF-0096-probe2 poison load_reason", poison["load_reason"])
        return 1
    if not poison["health"]["zero_hooks_fired"]:
        print("FAILED:CNF-0096-probe2 poison still fired hooks")
        return 1
    if poison["health"]["process_healthy"]:
        print("FAILED:CNF-0096-probe2 process health green on zero fire")
        return 1
    if not poison["health"]["naive_healthy"]:
        print("FAILED:CNF-0096-probe2 naive health should still be green (file presence)")
        return 1
    if not poison["p0_filed"]:
        print("FAILED:CNF-0096-probe2 P0 false-healthy not filed")
        return 1

    rc = payload.get("removal_control") or {}
    if not rc.get("detected") or rc.get("removed_hook_id") != REMOVED_HOOK_ID:
        print("FAILED:CNF-0096-probe2 artifact removal_control", rc)
        return 1
    p0 = payload.get("false_healthy_p0") or {}
    if not p0.get("filed"):
        print("FAILED:CNF-0096-probe2 artifact P0 not filed")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe2-removal-control",
                "unit_id": UNIT_ID,
                "removed_hook_id": REMOVED_HOOK_ID,
                "reported_not_fired": True,
                "installed_not_loaded_not_fired": True,
                "poison_key": POISON_KEY,
                "zero_hooks_fired": True,
                "process_healthy": False,
                "naive_healthy": True,
                "p0_filed": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0096-probe2 removal control and false-healthy detector")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
