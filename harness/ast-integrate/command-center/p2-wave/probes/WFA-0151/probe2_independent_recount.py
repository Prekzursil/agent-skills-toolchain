#!/usr/bin/env python3
"""Probe 2: independent recount of no-pin-no-fallback and UNRESOLVED-not-healthy.

Does not trust artifact['no_pin_and_no_fallback']; recomputes from inventory tuples.
Does not re-query OSV (that is probe 1).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from inventory import UNREACHABLE_CONTROL_ID, load_inventory, no_pin_no_fallback_ids  # noqa: E402

ART = REPO / "command-center/foundry/WFA-0151-supply-chain-map-for-the-105-external-dependencies-o.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0151-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "WFA-0151":
        return fail(f"unit_id {doc.get('unit_id')}")
    if "SUCCESS:WFA-0151" not in json.dumps(doc):
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    inv = load_inventory()
    deps = inv["dependencies"]
    if len(deps) != 105:
        return fail(f"inventory n={len(deps)}")
    ids = [d["id"] for d in deps]
    if len(set(ids)) != 105:
        return fail("duplicate inventory ids")

    recounted = no_pin_no_fallback_ids(deps)
    claimed = doc.get("no_pin_and_no_fallback") or []
    if not isinstance(claimed, list):
        return fail("artifact no_pin_and_no_fallback is not a list")
    if sorted(claimed) != recounted:
        return fail(f"recount mismatch claimed={sorted(claimed)} live={recounted}")

    rows = {r["id"]: r for r in (doc.get("rows") or []) if isinstance(r, dict)}
    if set(rows) != set(ids):
        return fail("artifact row ids != inventory ids")

    for dep in deps:
        row = rows[dep["id"]]
        want_none = (not dep.get("pin")) and (not dep.get("fallback"))
        if bool(row.get("no_pin_and_no_fallback")) != want_none:
            return fail(f"row flag mismatch {dep['id']}")
        if bool(row.get("pin")) != bool(dep.get("pin")):
            return fail(f"pin mismatch {dep['id']}")
        if (row.get("fallback") or None) != (dep.get("fallback") or None):
            return fail(f"fallback mismatch {dep['id']}")

    unr = rows.get(UNREACHABLE_CONTROL_ID) or {}
    if unr.get("resolution") != "UNRESOLVED":
        return fail("unreachable not UNRESOLVED")
    if unr.get("advisory_status") in {"CLEAN", "FLAGGED"}:
        return fail("unreachable advisory treated as a health verdict")
    if UNREACHABLE_CONTROL_ID not in recounted:
        return fail("unreachable control missing from no-pin-no-fallback recount")
    if UNREACHABLE_CONTROL_ID not in (doc.get("unresolved_ids") or []):
        return fail("unreachable missing from unresolved_ids")

    # Naive mutant: treat UNRESOLVED as healthy CLEAN. Must be distinguishable.
    naive_clean = {
        r["id"]
        for r in rows.values()
        if r.get("advisory_status") == "CLEAN" or r.get("resolution") == "UNRESOLVED"
    }
    real_clean = {r["id"] for r in rows.values() if r.get("advisory_status") == "CLEAN"}
    if UNREACHABLE_CONTROL_ID not in naive_clean:
        return fail("mutant fixture missing unreachable")
    if UNREACHABLE_CONTROL_ID in real_clean:
        return fail("unreachable in real CLEAN set")
    if naive_clean == real_clean:
        return fail("UNRESOLVED collapsed into CLEAN (detector vacuous)")

    print(
        json.dumps(
            {
                "inventory_source": inv["source"],
                "n": 105,
                "no_pin_no_fallback": recounted,
                "pass": True,
                "probe": "probe2-independent-recount",
                "unit_id": "WFA-0151",
                "unresolved_not_clean": True,
            },
            sort_keys=True,
        )
    )
    print(f"recount n=105 no_pin_no_fallback={len(recounted)} unresolved_not_assumed_healthy=True")
    print("SUCCESS:WFA-0151-probe2 independent no-pin-no-fallback recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
