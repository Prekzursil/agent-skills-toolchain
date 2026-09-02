#!/usr/bin/env python3
"""Probe 1: instantiate each CNL-0114 preset against the fixture task.

Records roster, protocol schedule, voting method, stopping expression.
Asserts intra-family profiles are measurably distinct (not a rename).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import family as F  # noqa: E402

MIN_INTRA = 2


def main() -> int:
    task = F.load_task()
    presets = F.family_presets()
    rows = []
    profiles = {}
    for preset in presets:
        inst = F.instantiate(preset, task)
        for key in ("roster", "protocol_schedule", "voting_method", "stopping_expression"):
            if not inst.get(key):
                print(f"FAILED:CNL-0114-probe1 missing {key} on {preset['id']}")
                return 1
        if not inst["roster"]:
            print(f"FAILED:CNL-0114-probe1 empty roster {preset['id']}")
            return 1
        prof = F.profile_of_instance(inst)
        profiles[preset["id"]] = prof
        rows.append(
            {
                "preset_id": preset["id"],
                "roster": [
                    {
                        "role_id": s["role_id"],
                        "votes": s["votes"],
                        "filled_by": s.get("filled_by"),
                    }
                    for s in inst["roster"]
                ],
                "protocol_schedule": inst["protocol_schedule"],
                "voting_method": inst["voting_method"],
                "stopping_expression": inst["stopping_expression"],
                "third_party_kind": inst["third_party_kind"],
                "franchise": inst["franchise"],
                "outcomes": inst["outcomes"],
            }
        )

    pairs = []
    ids = [p["id"] for p in presets]
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            dist = F.distance(profiles[a], profiles[b])
            pairs.append({"a": a, "b": b, "distance": dist})
            if dist < MIN_INTRA:
                print(
                    f"FAILED:CNL-0114-probe1 intra-family distance {dist} < {MIN_INTRA} for {a} vs {b}"
                )
                return 1

    neg = profiles["council.preset.multi-interest.negotiation"]
    med = profiles["council.preset.multi-interest.mediation"]
    if neg["third_party_kind"] == med["third_party_kind"]:
        print("FAILED:CNL-0114-probe1 negotiation/mediation share third_party_kind")
        return 1
    if neg["third_party_kind"] != "none" or med["third_party_kind"] != "mediator":
        print("FAILED:CNL-0114-probe1 negotiation/mediation third-party kinds wrong")
        return 1
    if not neg["batna_is_first_class_outcome"] or med["batna_is_first_class_outcome"]:
        print("FAILED:CNL-0114-probe1 BATNA is not the negotiation/mediation split")
        return 1
    if med["mediator_cannot_vote"] is not True:
        print("FAILED:CNL-0114-probe1 mediator is not barred from voting")
        return 1

    adv = profiles["council.preset.multi-interest.adversarial-collaboration"]
    if not adv["split_verdict_is_fault"] or not adv["prereg_hash_required"]:
        print("FAILED:CNL-0114-probe1 adversarial collaboration missing lock/fault")
        return 1
    if adv["voting_method"] == neg["voting_method"]:
        print("FAILED:CNL-0114-probe1 adversarial collaboration voting matches negotiation")
        return 1

    lay = profiles["council.preset.multi-interest.lay-panel"]
    if not lay["presenter_disenfranchised"] or not lay["ballot_forbids_expert_default"]:
        print("FAILED:CNL-0114-probe1 lay panel missing anti-steering machinery")
        return 1
    if "expert-presenter" not in lay["role_ids"]:
        print("FAILED:CNL-0114-probe1 lay panel missing expert-presenter seat")
        return 1
    if any(x.startswith("expert") and x in lay["franchise"] for x in lay["franchise"]):
        print("FAILED:CNL-0114-probe1 expert sits on the lay franchise")
        return 1
    if "expert-presenter" in {x.split(".")[0] for x in lay["franchise"]}:
        print("FAILED:CNL-0114-probe1 presenter is in the franchise")
        return 1

    report = {
        "unit": "CNL-0114",
        "probe": "probe1_instantiate",
        "task_id": task["id"],
        "instantiations": rows,
        "intra_family_distances": pairs,
        "min_intra_family_distance": min(p["distance"] for p in pairs),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(
        f"instantiated={len(rows)} min_intra={report['min_intra_family_distance']} "
        f"neg_third={neg['third_party_kind']} med_third={med['third_party_kind']}"
    )
    print("SUCCESS:CNL-0114-probe1 instantiate roster/schedule/vote/stop")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
