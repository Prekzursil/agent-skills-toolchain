#!/usr/bin/env python3
"""Probe 2: adversarial circularity + live harvest of three program records.

A record whose refuting observation is unobservable in principle is rejected
as circular. Independently, three real records produced elsewhere are scored
against the five mandatory elements; the receipt's missing-element table must
match this live recompute.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from harvest import harvest  # noqa: E402
from validator import validate  # noqa: E402

ART = REPO / "command-center/receipts/TST-0284.json"
FIXTURES = HERE / "fixtures" / "records.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0284-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:TST-0284" not in json.dumps(doc):
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    fx = json.loads(FIXTURES.read_text(encoding="utf-8"))
    world = validate(fx["circular_unobservable"])
    omni = validate(fx["circular_omniscient"])
    eq = validate(fx["circular_equals_claim"])
    good = validate(fx["well_formed"])
    if world["accepted"] or omni["accepted"] or eq["accepted"]:
        return fail(
            f"circular accepted world={world} omni={omni} eq={eq}"
        )
    if not (
        world["circular"] or any("unobservable" in r for r in world["reasons"])
    ):
        return fail(f"world not classified circular: {world}")
    if not (
        omni["circular"] or any("unobservable" in r or "omniscient" in r for r in omni["reasons"])
    ):
        return fail(f"omniscient not classified circular: {omni}")
    if not good["accepted"]:
        return fail(f"well-formed over-blocked during circular probe: {good}")

    rec_circ = (doc.get("tests") or {}).get("rejects_circular_unobservable") or {}
    if rec_circ.get("pass") is not True:
        return fail("receipt circular test not PASS")

    live = harvest()
    if live["n"] < 3:
        return fail(f"harvest n={live['n']}")
    rec_h = doc.get("harvest") or {}
    rec_rows = {
        r.get("id"): r for r in (rec_h.get("records") or []) if isinstance(r, dict)
    }
    for row in live["records"]:
        got = rec_rows.get(row["id"])
        if not got:
            return fail(f"receipt missing harvest row {row['id']}")
        if sorted(got.get("missing") or []) != sorted(row["missing"]):
            return fail(
                f"missing-element mismatch {row['id']}: "
                f"receipt={got.get('missing')} live={row['missing']}"
            )
        if got.get("accepted") != row["accepted"]:
            return fail(f"accepted mismatch {row['id']}")
        if row["accepted"]:
            return fail(f"{row['id']} unexpectedly accepted as a five-element proof")

    declared = rec_h.get("catalog_declared_impossibility_artifacts") or []
    live_decl = {d["path"]: d["present"] for d in live["catalog_declared_impossibility_artifacts"]}
    for d in declared:
        if live_decl.get(d.get("path")) != d.get("present"):
            return fail(f"declared-artifact presence drift {d}")

    summary = {
        "probe": "probe2-circular-and-harvest",
        "unit_id": "TST-0284",
        "pass": True,
        "circular_rejected": True,
        "omniscient_rejected": True,
        "equals_claim_rejected": True,
        "well_formed_still_accepted": True,
        "harvest_n": live["n"],
        "harvest_ids": [r["id"] for r in live["records"]],
        "harvest_missing": {r["id"]: r["missing"] for r in live["records"]},
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "circular=REJECTED harvest="
        + ",".join(r["id"] for r in live["records"])
    )
    print("SUCCESS:TST-0284-probe2 circular unobservable rejected; three records scored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
