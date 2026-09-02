#!/usr/bin/env python3
"""Probe 2: independent reviewer traces two flagged recommendations by hand.

Does not trust inherit.classify() for the chain. Re-reads the packet files,
walks explicit claim-id edges (the catalog pivot), and confirms:

  REC-DROP  heading -> CLM-DROP-1 UNVERIFIED, heading unqualified
  REC-TRANS heading -> CLM-A CONFIRMED -> CLM-B NOT-CHECKED, heading unqualified

Both-states mutant: set CLM-B to CONFIRMED; REC-TRANS must leave DROPPED-TAG.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import inherit as I  # noqa: E402


def _heading_line(md: Path, heading: str) -> int:
    for h, line, _body in I.parse_markdown_sections(md):
        if h == heading:
            return line
    raise SystemExit(f"FAILED:BLD-0032-probe2 missing heading {heading}")


def hand_trace() -> dict:
    packet = I.CONTROL
    claims = I.load_claims(packet / "CLAIM-REGISTRY.json")
    recs = {r.id: r for r in I.load_control_recommendations(packet)}
    md = packet / "decision-packet.md"

    drop = recs["REC-DROP"]
    trans = recs["REC-TRANS"]

    # Explicit edges only (pivot away from token matching).
    drop_cites = I.explicit_cites(drop)
    trans_cites = I.explicit_cites(trans)

    drop_claim = claims[drop_cites[0]]
    drop_unqualified = not I.heading_has_tag(drop.heading, drop_claim.tag)
    drop_ok = (
        drop_cites == ["CLM-DROP-1"]
        and drop_claim.tag == "UNVERIFIED"
        and drop_unqualified
        and _heading_line(md, drop.heading) == drop.line
    )

    a = claims[trans_cites[0]]
    premises, hops = I.closure(trans_cites, claims)
    b = claims["CLM-B"]
    trans_ok = (
        trans_cites == ["CLM-A"]
        and a.tag == "CONFIRMED"
        and "CLM-B" in a.rests_on
        and "CLM-B" in premises
        and b.tag == "NOT-CHECKED"
        and hops.get("CLM-B", 0) >= 2
        and not I.heading_has_tag(trans.heading, b.tag)
        and _heading_line(md, trans.heading) == trans.line
    )

    inherit_rec = recs["REC-INHERIT"]
    inherit_claim = claims[I.explicit_cites(inherit_rec)[0]]
    inherit_ok = I.heading_has_tag(inherit_rec.heading, inherit_claim.tag)

    mutant = I.by_id(I.mutant_b_confirmed())
    mutant_ok = mutant["REC-TRANS"].cls != "DROPPED-TAG"
    still_drop = mutant["REC-DROP"].cls == "DROPPED-TAG"

    detector = I.by_id(I.control_audit("explicit"))
    agrees = (
        detector["REC-DROP"].cls == "DROPPED-TAG"
        and detector["REC-TRANS"].cls == "DROPPED-TAG"
        and detector["REC-TRANS"].claim_id == "CLM-B"
        and detector["REC-INHERIT"].cls == "INHERITED"
    )

    errors: list[str] = []
    if not drop_ok:
        errors.append("hand-trace REC-DROP failed")
    if not trans_ok:
        errors.append("hand-trace REC-TRANS two-hop failed")
    if not inherit_ok:
        errors.append("hand-trace REC-INHERIT heading missing tag")
    if not mutant_ok:
        errors.append("mutant CLM-B=CONFIRMED still flags REC-TRANS")
    if not still_drop:
        errors.append("mutant lost REC-DROP")
    if not agrees:
        errors.append("explicit-edge detector disagrees with hand trace")

    return {
        "ok": not errors,
        "errors": errors,
        "drop": {
            "heading": drop.heading,
            "heading_line": drop.line,
            "path": drop.path,
            "claim_id": drop_claim.id,
            "tag": drop_claim.tag,
            "tag_location": drop_claim.tag_location,
            "unqualified": drop_unqualified,
            "confirmed": drop_ok,
        },
        "trans": {
            "heading": trans.heading,
            "heading_line": trans.line,
            "path": trans.path,
            "cited": trans_cites,
            "claim_a_tag": a.tag,
            "claim_b_id": b.id,
            "claim_b_tag": b.tag,
            "claim_b_tag_location": b.tag_location,
            "hops_to_b": hops.get("CLM-B"),
            "unqualified": not I.heading_has_tag(trans.heading, b.tag),
            "confirmed": trans_ok,
        },
        "inherit_heading_has_tag": inherit_ok,
        "mutant_trans_class": mutant["REC-TRANS"].cls,
        "mutant_clears_trans": mutant_ok,
        "agrees_with_explicit_detector": agrees,
        "reviewer_id": "BLD-0032-probe2-hand-trace",
        "verdict": "PASS" if not errors else "FAIL",
        "independent": True,
    }


def main() -> int:
    result = hand_trace()
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["ok"]:
        print("FAILED:BLD-0032-probe2 " + "; ".join(result["errors"]))
        return 1
    print(
        "drop_ok={drop[confirmed]} trans_ok={trans[confirmed]} "
        "mutant_clears={mutant_clears_trans} agree={agrees_with_explicit_detector}".format(
            **result
        )
    )
    print("SUCCESS:BLD-0032-probe2 independent hand-trace")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
