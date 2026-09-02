#!/usr/bin/env python3
"""Probe 2: every claim slot is in the skeleton; milestone rewrite never drops values.

Planted missing-slot and planted dropped-measurement must fire. A known-good
skeleton is silent.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from synthesis.durability import (  # noqa: E402
    CLASS_LOST_DATA,
    CLASS_MISSING_SLOT,
    UNKNOWN,
    atomic_write_json,
    claim_slots,
    inspect_artifact,
    load_synthesis_lane,
    record_milestone,
    resolve_output,
    write_skeleton,
)

UNIT = "SYN-0046"


def _plant_missing_slot(root: Path, unit: dict) -> dict:
    skel = write_skeleton(root, unit)
    path = resolve_output(root, unit)
    doc = json.loads(path.read_text(encoding="utf-8"))
    slots = claim_slots(unit)
    dropped = slots[-1]
    del doc["claims"][dropped]
    atomic_write_json(path, doc)
    return inspect_artifact(path, unit)


def _plant_lost_measurement(root: Path, unit: dict) -> dict:
    skel = write_skeleton(root, unit)
    slots = claim_slots(unit)
    first = record_milestone(root, unit, slots[0], "keep-me")
    path = resolve_output(root, unit)
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["claims"][slots[0]] = {"status": UNKNOWN, "value": None, "measured_at": None}
    atomic_write_json(path, doc)
    return inspect_artifact(path, unit, previous=first)


def main() -> int:
    lane = load_synthesis_lane(REPO)
    if len(lane) != 48:
        print(f"FAILED:SYN-0046-probe2 lane count {len(lane)}")
        return 1
    with tempfile.TemporaryDirectory(prefix="syn-0046-slots-") as tmp:
        root = Path(tmp)
        rows = []
        all_slots_ok = True
        preserve_ok = True
        for unit in lane:
            skel = write_skeleton(root / "lane", unit)
            slots = claim_slots(unit)
            have = set((skel.get("claims") or {}).keys())
            missing = [s for s in slots if s not in have]
            if missing:
                all_slots_ok = False
            measured = record_milestone(root / "lane", unit, slots[0], "first-value")
            if len(slots) > 1:
                measured = record_milestone(root / "lane", unit, slots[1], "second-value")
            first_kept = (measured["claims"][slots[0]].get("value") == "first-value")
            if not first_kept:
                preserve_ok = False
            final_slots = set(measured["claims"].keys())
            if set(slots) - final_slots:
                all_slots_ok = False
            rows.append(
                {
                    "unit_id": unit["id"],
                    "slot_count": len(slots),
                    "missing": missing,
                    "first_kept": first_kept,
                }
            )

        missing_ctrl = _plant_missing_slot(root / "missing", lane[0])
        lost_ctrl = _plant_lost_measurement(root / "lost", lane[0])
        good = write_skeleton(root / "good", lane[0])
        good_insp = inspect_artifact(resolve_output(root / "good", lane[0]), lane[0])

        payload = {
            "probe": "probe2-slots-and-milestones",
            "unit_id": UNIT,
            "lane_count": len(lane),
            "all_skeletons_have_every_claim_slot": all_slots_ok,
            "milestone_rewrite_preserves_measured": preserve_ok,
            "planted_missing_slot": {
                "fired": missing_ctrl["fired"],
                "findings": missing_ctrl["findings"],
                "missing_slots": missing_ctrl["missing_slots"],
            },
            "planted_lost_measurement": {
                "fired": lost_ctrl["fired"],
                "findings": lost_ctrl["findings"],
                "lost_slots": lost_ctrl["lost_slots"],
            },
            "known_good_silent": (not good_insp["fired"]) and good_insp["honest_unknown"],
            "slot_sum": sum(r["slot_count"] for r in rows),
        }
        payload["pass"] = bool(
            all_slots_ok
            and preserve_ok
            and CLASS_MISSING_SLOT in missing_ctrl["findings"]
            and CLASS_LOST_DATA in lost_ctrl["findings"]
            and payload["known_good_silent"]
            and len(lane) == 48
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
        if not payload["pass"]:
            print("FAILED:SYN-0046-probe2 claim slots / milestone rewrite")
            return 1
        print(
            "SUCCESS:SYN-0046-probe2 every SYN-0001..SYN-0048 skeleton has every "
            "claim slot; milestone rewrite kept measured values; planted defects fired"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
