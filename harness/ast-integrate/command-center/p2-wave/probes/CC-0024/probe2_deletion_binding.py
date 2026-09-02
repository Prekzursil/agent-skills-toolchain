#!/usr/bin/env python3
"""Deletion control, binding validity, and unbound-as-list (never a count)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import extract as X  # noqa: E402

REPO = HERE.parents[3]
ARTIFACT = REPO / "command-center" / "receipts" / "CC-0024.json"


def fail(msg: str) -> int:
    print(f"FAILED:CC-0024-probe2 {msg}")
    return 1


def main() -> int:
    units = X.catalog_units()
    ids = X.catalog_ids(units)
    path, kind, lines = X.locate_spec(units)
    original = X.extract_from_lines(lines, units)
    if not original["floor_recall"]["passed"]:
        return fail("floor-recall-not-green")

    known = next(
        r for r in original["requirements"] if r.get("floor_id") == "FLOOR-40-FLAGSHIP"
    )
    scratch = X.delete_requirement_text(lines, known)
    after = X.extract_from_lines(scratch, units)
    after_ids = {r["id"] for r in after["requirements"]}
    # Join original register to the post-deletion extract: a missing id is UNBOUND.
    reported_unbound = []
    for rec in original["requirements"]:
        if rec["id"] not in after_ids:
            row = dict(rec)
            row["binding_status"] = "UNBOUND"
            row["bound_unit_ids"] = []
            row["deletion_control"] = True
            reported_unbound.append(row)
    hit = [r for r in reported_unbound if r["id"] == known["id"]]
    if not hit:
        return fail("deletion-did-not-unbound " + known["id"])
    if hit[0]["spec_line"] != known["spec_line"]:
        return fail("unbound-missing-spec-line")
    # Never summarise as a count: print the id and spec line.
    print(
        "deletion_unbound "
        + hit[0]["id"]
        + " spec_line="
        + str(hit[0]["spec_line"])
        + " anchor="
        + hit[0]["spec_anchor"]
    )
    if after["floor_recall"]["passed"] and known["id"] in after_ids:
        return fail("deleted-floor-still-extracted")

    invalid = sorted(
        {
            uid
            for r in original["requirements"]
            for uid in r.get("bound_unit_ids") or []
            if uid not in ids
        }
    )
    if invalid:
        return fail("bound-id-not-in-catalog " + ",".join(invalid[:8]))

    if not ARTIFACT.is_file():
        return fail("artifact-absent")
    doc = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if not isinstance(doc.get("unbound"), list):
        return fail("unbound-not-a-list")
    for row in doc["unbound"]:
        if not isinstance(row, dict):
            return fail("unbound-row-not-object")
        if "spec_line" not in row or "spec_anchor" not in row or "id" not in row:
            return fail("unbound-row-incomplete " + str(row.get("id")))
        print(f"unbound {row['id']} spec_line={row['spec_line']} {row['spec_anchor']}")
    # A count-only field without the list would fail the isinstance check above.
    if doc.get("coverage", {}).get("unbound") != len(doc["unbound"]):
        return fail("coverage-unbound-count-disagrees-with-list")
    art_invalid = sorted(
        {
            uid
            for r in doc.get("requirements") or []
            for uid in (r.get("bound_unit_ids") or [])
            if uid not in ids
        }
    )
    if art_invalid:
        return fail("artifact-bound-id-not-in-catalog " + ",".join(art_invalid[:8]))

    print(f"binding_validity ok catalog_units={len(ids)}")
    print("SUCCESS:CC-0024-probe2 deletion-binding")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
