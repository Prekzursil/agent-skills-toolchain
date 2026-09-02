#!/usr/bin/env python3
"""Probe 1: catalog controls for BLD-0032.

1. Unqualified heading citing a tagged premise must be caught (DROPPED-TAG).
2. Heading that inherits the tag must not be flagged.
3. Two-hop chain (rec cites CLM-A, A rests on NOT-CHECKED CLM-B) must be caught.
Also: UNGROUNDED for a recommendation with no traceable premise; CLEAN for settled.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import inherit as I  # noqa: E402


def evaluate() -> dict:
    findings = I.control_audit("union")
    by = I.by_id(findings)
    errors: list[str] = []

    drop = by.get("REC-DROP")
    if drop is None or drop.cls != "DROPPED-TAG":
        errors.append(f"REC-DROP want DROPPED-TAG got {None if drop is None else drop.cls}")
    elif drop.claim_id != "CLM-DROP-1" or drop.tag != "UNVERIFIED":
        errors.append(f"REC-DROP chain {drop.claim_id}/{drop.tag}")
    elif drop.hops < 1:
        errors.append("REC-DROP hops")

    inherit = by.get("REC-INHERIT")
    if inherit is None or inherit.cls != "INHERITED":
        errors.append(
            f"REC-INHERIT want INHERITED got {None if inherit is None else inherit.cls}"
        )
    elif inherit.qualified is not True:
        errors.append("REC-INHERIT must be qualified")

    trans = by.get("REC-TRANS")
    if trans is None or trans.cls != "DROPPED-TAG":
        errors.append(f"REC-TRANS want DROPPED-TAG got {None if trans is None else trans.cls}")
    elif trans.claim_id != "CLM-B" or trans.tag != "NOT-CHECKED":
        errors.append(f"REC-TRANS want CLM-B/NOT-CHECKED got {trans.claim_id}/{trans.tag}")
    elif trans.hops < 2:
        errors.append(f"REC-TRANS hops={trans.hops} (need two-hop)")
    elif "CLM-A" not in trans.cited:
        errors.append("REC-TRANS must cite CLM-A (one hop), not only CLM-B")

    ung = by.get("REC-UNGROUNDED")
    if ung is None or ung.cls != "UNGROUNDED":
        errors.append(
            f"REC-UNGROUNDED want UNGROUNDED got {None if ung is None else ung.cls}"
        )

    clean = by.get("REC-CLEAN")
    if clean is None or clean.cls != "CLEAN":
        errors.append(f"REC-CLEAN want CLEAN got {None if clean is None else clean.cls}")

    flagged = {f.rec.id for f in findings if f.cls == "DROPPED-TAG"}
    if "REC-INHERIT" in flagged:
        errors.append("false-positive: REC-INHERIT flagged DROPPED-TAG")
    if "REC-CLEAN" in flagged:
        errors.append("false-positive: REC-CLEAN flagged DROPPED-TAG")

    # Both edge builders must catch the one-hop drop and the two-hop chain.
    token = I.by_id(I.control_audit("token"))
    explicit = I.by_id(I.control_audit("explicit"))
    for method, table in (("token", token), ("explicit", explicit)):
        if table["REC-DROP"].cls != "DROPPED-TAG":
            errors.append(f"{method} missed REC-DROP")
        if table["REC-TRANS"].cls != "DROPPED-TAG" or table["REC-TRANS"].hops < 2:
            errors.append(f"{method} missed two-hop REC-TRANS")
        if table["REC-INHERIT"].cls == "DROPPED-TAG":
            errors.append(f"{method} false-positive REC-INHERIT")

    ok = not errors
    return {
        "ok": ok,
        "errors": errors,
        "findings": [f.as_dict() for f in findings],
        "flagged_dropped_tag": sorted(flagged),
        "controls": {
            "unqualified_drop": drop.cls == "DROPPED-TAG" if drop else False,
            "inherited_not_flagged": inherit.cls == "INHERITED" if inherit else False,
            "two_hop": bool(trans and trans.cls == "DROPPED-TAG" and trans.hops >= 2),
            "ungrounded": ung.cls == "UNGROUNDED" if ung else False,
        },
    }


def main() -> int:
    result = evaluate()
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["ok"]:
        print("FAILED:BLD-0032-probe1 " + "; ".join(result["errors"]))
        return 1
    c = result["controls"]
    print(
        "drop={unqualified_drop} inherit_ok={inherited_not_flagged} "
        "two_hop={two_hop} ungrounded={ungrounded}".format(**c)
    )
    print("SUCCESS:BLD-0032-probe1 catalog controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
