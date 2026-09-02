#!/usr/bin/env python3
"""Probe 1: instantiate both boards; nearest-sibling differential; conflict gate."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import boards as B  # noqa: E402
import compose as K  # noqa: E402
import instantiate as I  # noqa: E402
import sibling as S  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:CNL-0111-probe1 {msg}")
    return 1


def main() -> int:
    presets = B.family_presets()
    if len(presets) != 2:
        return _fail(f"expected 2 presets got {len(presets)}")
    legal_p, risk_p = presets
    if legal_p["id"] != "C15" or risk_p["id"] != "C16":
        return _fail("owned ids are C15 and C16")
    if set(legal_p["outcome_types"]) & set(risk_p["outcome_types"]):
        return _fail("outcome type sets must be disjoint")
    if legal_p["evidence_standard"]["bar"] == risk_p["evidence_standard"]["bar"]:
        return _fail("evidence bars must differ")
    if legal_p["voting_method"] == risk_p["voting_method"]:
        return _fail("voting methods must differ")

    task = I.load_task()
    inst_legal = I.instantiate(legal_p, task)
    inst_risk = I.instantiate(risk_p, task)
    for inst, src in ((inst_legal, legal_p), (inst_risk, risk_p)):
        if inst["roster"] != src["roles"]:
            return _fail("roster mismatch")
        if inst["protocol_schedule"] != src["bound_protocols"]:
            return _fail("protocol schedule mismatch")
        if inst["voting_method"] != src["voting_method"]:
            return _fail("vote mismatch")
        if inst["stopping_expression"] != src["stopping_expression"]:
            return _fail("stop mismatch")

    library, meta = S.library_presets()
    if meta["preset_count"] != 72:
        return _fail(f"library preset_count={meta['preset_count']}")
    if meta["original_library_present"]:
        return _fail("expected original library absent; reconstruction path changed")

    row_legal = B.as_signature_row(legal_p)
    row_risk = B.as_signature_row(risk_p)
    d_boards = S.pairwise_distance(row_legal, row_risk)
    if d_boards <= meta["threshold"]:
        return _fail(f"C15 vs C16 collapsed d={d_boards}")

    nn_legal = S.nearest_sibling(row_legal, library, exclude_ids={"C15", "C16"})
    nn_risk = S.nearest_sibling(row_risk, library, exclude_ids={"C15", "C16"})
    if nn_legal["same_signature"] or nn_risk["same_signature"]:
        return _fail(f"mechanism-duplicate of sibling {nn_legal} {nn_risk}")
    if nn_legal["distance"] <= meta["threshold"]:
        return _fail("legal nearest sibling below threshold")
    if nn_risk["distance"] <= meta["threshold"]:
        return _fail("risk nearest sibling below threshold")

    planted = S.plant_renamed_duplicate(row_legal, "C-PLANT-DUP")
    d_plant = S.pairwise_distance(row_legal, planted)
    if d_plant > meta["threshold"]:
        return _fail("name-only clone of C15 not distance 0")

    legal_out = I.legal_outcome(task)
    risk_out = I.risk_outcome(task)
    if legal_out["outcome"] != "PROHIBITED":
        return _fail(f"fixture legal {legal_out}")
    if risk_out["outcome"] != "ACCEPT" or not risk_out["residual_risk_named"]:
        return _fail(f"fixture risk {risk_out}")
    composed = K.compose(legal_out, risk_out)
    if composed["action_authorized"]:
        return _fail("legal NO + risk ACCEPT must not authorize")
    if not composed["conflict_legal_no_risk_accept"]:
        return _fail("conflict flag missing")

    good_task = I.load_task(HERE / "fixtures" / "both_permit.json")
    good = K.compose(I.legal_outcome(good_task), I.risk_outcome(good_task))
    if not good["action_authorized"]:
        return _fail("known-good PERMITTED+ACCEPT must authorize")

    print(
        json.dumps(
            {
                "probe": "probe1-instantiate-and-sibling",
                "instantiations": [inst_legal, inst_risk],
                "c15_c16_distance": d_boards,
                "nearest_sibling_legal": nn_legal,
                "nearest_sibling_risk": nn_risk,
                "name_only_clone_distance": d_plant,
                "conflict": composed,
                "known_good_authorized": good["action_authorized"],
                "library": {
                    "source": meta["source"],
                    "original_library_present": meta["original_library_present"],
                    "preset_count": meta["preset_count"],
                },
            },
            sort_keys=True,
        )
    )
    print(
        f"legal_nn={nn_legal['neighbour_id']}:{nn_legal['neighbour_name']}"
        f" d={nn_legal['distance']}"
    )
    print(
        f"risk_nn={nn_risk['neighbour_id']}:{nn_risk['neighbour_name']}"
        f" d={nn_risk['distance']}"
    )
    print(
        "conflict legal=PROHIBITED risk=ACCEPT action_authorized="
        f"{composed['action_authorized']}"
    )
    print("SUCCESS:CNL-0111-probe1 instantiate sibling differential and conflict gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
