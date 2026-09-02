#!/usr/bin/env python3
"""Probe 2: vendor-unique primitive must not appear in the intersection.

Mechanically different from probe 1: this probe never compares the published
intersection list for completeness. It only checks (a) the named Codex-only
control is unique and excluded, (b) a planted id is excluded when on one
vendor and included when on all, (c) the two reviewers hold disjoint source
halves.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import (  # noqa: E402
    CONTROL_ID,
    HALF_A,
    HALF_B,
    OUT_REL,
    SENTINEL,
    SIBLING_IDS,
    UNIT,
    compute,
    control_both_states,
    domain_of,
    schema_rejects_garbage,
)

ART = REPO / OUT_REL
SCHEMA = REPO / "command-center/schema/compatibility-matrix.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    live = compute()
    inter = set(live["intersection"])
    owners = [
        v["vendor_id"]
        for v in live["supported"]
        if CONTROL_ID in v["primitive_ids"]
    ]
    print(
        f"control={CONTROL_ID} owners={owners} in_intersection={CONTROL_ID in inter}"
    )
    if CONTROL_ID in inter:
        return fail("vendor-unique control leaked into intersection")
    if len(owners) != 1:
        return fail(f"control owners {owners} (want exactly one supported vendor)")

    both = control_both_states(live["supported"])
    print(
        "planted one_vendor={one} all_vendors={all} pass={p}".format(
            one=both["one_vendor_in_intersection"],
            all=both["all_vendors_in_intersection"],
            p=both["pass"],
        )
    )
    if not both["pass"]:
        return fail("planted unique-control detector is silent in one state")

    a = set(live["reviewer_a"]["source_units"])
    b = set(live["reviewer_b"]["source_units"])
    print(f"partition A={sorted(a)} B={sorted(b)}")
    if a != set(HALF_A) or b != set(HALF_B):
        return fail("reviewer halves drifted from engine constants")
    if a & b:
        return fail("reviewer source halves overlap")
    if a | b != set(SIBLING_IDS):
        return fail("reviewer halves do not cover RES-0023..RES-0032")
    if not inter.issubset(set(live["reviewer_a"]["extracted_intersection"])):
        return fail("intersection not subset of reviewer-A half-intersection")
    if not inter.issubset(set(live["reviewer_b"]["extracted_intersection"])):
        return fail("intersection not subset of reviewer-B half-intersection")

    payload = domain_of(doc)
    ctrl = payload.get("control") or {}
    if ctrl.get("vendor_unique_primitive") != CONTROL_ID:
        return fail("artifact control id mismatch")
    if ctrl.get("present_in_intersection") is not False:
        return fail("artifact claims control is in the intersection")
    if CONTROL_ID in (payload.get("intersection") or []):
        return fail("artifact intersection list contains the control")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    if not schema_rejects_garbage(schema):
        return fail("schema accepted garbage")

    print(f"SUCCESS:{UNIT}-probe2 unique-control excluded partitioned reviewers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
