#!/usr/bin/env python3
"""Probe 1: assignment quotes, multi-class, zero-coverage routing, taxonomy recount.

Re-derives taxonomy and assignments from catalog + fixtures. Does not trust
the artifact's summary fields. Both-states: dropping one class changes n;
forcing multi-class rows to a single class is rejected.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import assign as A  # noqa: E402
import candidates as C  # noqa: E402
import taxonomy as T  # noqa: E402

REPO = HERE.parents[3]
ART = REPO / "command-center/wfa/WFA-0035-extract-task-fit.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0035-probe1 {msg}")
    return 1


def main() -> int:
    tax = T.build_taxonomy()
    pack = C.load_candidates()
    planted = {c["id"]: c for c in pack["candidates"] if c.get("planted")}
    assigned = A.assign_all(pack["candidates"], tax["classes"])
    by_id = {r["candidate_id"]: r for r in assigned["assignments"]}

    print(
        json.dumps(
            {
                "n_classes": tax["n_classes"],
                "floor_sum": tax["floor_sum"],
                "floor_agreement": tax["floor_agreement"],
                "family_counts": tax["family_counts"],
                "n_candidates": assigned["n_candidates"],
                "n_assigned": assigned["n_assigned"],
                "n_multi_class": assigned["n_multi_class"],
                "n_zero": assigned["n_zero_coverage_classes"],
                "n_d_families": tax["n_d_families"],
            },
            sort_keys=True,
        )
    )

    if not tax["floor_agreement"]:
        return fail(f"floor disagreement {tax['disagreements']}")
    if tax["n_classes"] != tax["floor_sum"]:
        return fail("n_classes != floor_sum")
    if tax["n_d_families"] != 20:
        return fail(f"D1-D20 count {tax['n_d_families']}")

    dropped = dict(tax)
    dropped_classes = tax["classes"][1:]
    if len(dropped_classes) == tax["n_classes"]:
        return fail("drop-one-class mutant did not change n")
    if len(dropped_classes) != tax["n_classes"] - 1:
        return fail("drop-one-class arithmetic")
    print(
        f"DROP-ONE-CLASS n {tax['n_classes']} -> {len(dropped_classes)} "
        "(hardcoded-96 detector would miss this)"
    )

    for row in assigned["assignments"]:
        for cls in row["classes"]:
            quote = cls["deciding_sentence"]
            if not quote or quote not in row["does"]:
                return fail(
                    f"deciding_sentence not in does: {row['candidate_id']} {quote!r}"
                )

    for cid, rec in planted.items():
        want = list(rec.get("expected_classes") or [])
        got = by_id[cid]["class_ids"]
        if rec.get("role") == "decoy" or not want:
            if got:
                return fail(f"decoy {cid} assigned {got}")
            continue
        missing = [x for x in want if x not in got]
        if missing:
            return fail(f"{cid} expected {want} got {got} missing {missing}")
        if rec.get("role") == "multi-class" and len(got) < 2:
            return fail(f"{cid} should be multi-class, got {got}")
        print(f"PLANTED {cid} expected={want} got={got}")

    if assigned["n_multi_class"] < 1:
        return fail("no multi-class candidate")
    forced = A.force_single_class(assigned)
    if forced["n_multi_class"] != 0:
        return fail("force-single-class mutant still has multi-class")
    if assigned["n_multi_class"] == forced["n_multi_class"]:
        return fail("force-single-class mutant did not change multi-class count")
    print(
        f"FORCE-SINGLE-CLASS multi {assigned['n_multi_class']} -> "
        f"{forced['n_multi_class']} (detector fires on the mutant)"
    )

    zeros = assigned["zero_coverage_classes"]
    if not zeros:
        return fail("zero-coverage list empty")
    for z in zeros:
        lane = z.get("generation_lane") or {}
        if lane.get("route") != "WFA-generation":
            return fail(f"{z['class_id']} not routed to generation lane")
        if not lane.get("typed_goal"):
            return fail(f"{z['class_id']} generation goal missing")
    print(
        f"ZERO-COVERAGE n={len(zeros)} all routed to WFA-generation "
        f"(not left implicit)"
    )

    for src in pack["candidates"]:
        if src.get("family_origin") != "on-tree":
            continue
        path = REPO / src["origin"]
        live = path.read_text(encoding="utf-8")
        if src["does"] not in live:
            return fail(f"on-tree does not a live substring: {src['id']}")
    print(f"ON-TREE quotes verified n={pack['n_on_tree']}")

    if not ART.is_file():
        return fail(f"artifact missing {ART}")
    art = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:WFA-0035" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent in artifact")
    if str(art.get("state") or "").upper() in {"BLOCKED", "FAILED"}:
        return fail(f"artifact self-declared {art.get('state')}")
    art_zero = {
        z["class_id"] for z in art["coverage"]["zero_coverage_classes"]
    }
    live_zero = {z["class_id"] for z in zeros}
    if art_zero != live_zero:
        return fail("artifact zero-coverage set != live recompute")

    print(
        "SUCCESS:WFA-0035-probe1 assignment quotes multi-class "
        "zero-coverage taxonomy-recount"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
