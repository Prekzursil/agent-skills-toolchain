#!/usr/bin/env python3
"""Named probe 2: clause-level reading of non-permissive / ambiguous texts.

Mechanically different from probe 1: obligation regexes over LICENSE bytes.
Does not treat the automated SPDX identifier as the constraining clause.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from inventory import automated_inventory, clause_readings, gpl_clause_ok  # noqa: E402

ART = REPO / (
    "command-center/adversarial/"
    "ADV-0048-license-inventory-compatibility-matrix.json"
)
UNIT = "ADV-0048"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    live_inv = automated_inventory()
    live = clause_readings(live_inv["components"])
    chk = gpl_clause_ok(live)
    if not chk["ok"]:
        return fail("GPL entire-work clause not recovered", chk)
    if chk.get("gpl_method") != "clause-extraction":
        return fail("probe 2 used the wrong method", chk)

    art_rows = {
        r["component_id"]: r
        for r in (doc.get("clause_readings") or [])
        if isinstance(r, dict)
    }
    live_rows = {r["component_id"]: r for r in live}
    if set(art_rows) != set(live_rows):
        return fail(
            "clause_readings id set mismatch",
            {"art": sorted(art_rows), "live": sorted(live_rows)},
        )
    for cid, live_r in live_rows.items():
        art_r = art_rows[cid]
        if art_r.get("method") != "clause-extraction":
            return fail(f"{cid} method not clause-extraction", art_r)
        if art_r.get("automated_spdx_ignored") is not True:
            return fail(f"{cid} must ignore automated SPDX as the clause")
        live_kinds = [c["kind"] for c in live_r.get("clauses") or []]
        art_kinds = [c["kind"] for c in art_r.get("clauses") or []]
        if live_kinds != art_kinds:
            return fail(f"{cid} clause kinds mismatch", {"art": art_kinds, "live": live_kinds})
        live_clause = (live_r.get("clauses") or [{}])[0].get("clause", "")
        art_clause = (art_r.get("clauses") or [{}])[0].get("clause", "")
        if live_clause != art_clause:
            return fail(f"{cid} clause text mismatch")
        if cid in {
            "control:known-gpl3",
            "control:mislabeled-mit-metadata-gpl-text",
        }:
            if "entire work" not in art_clause.lower():
                return fail(f"{cid} clause lost entire-work obligation", art_clause)
            if art_clause.strip() in {"GPL-3.0-only", "GPL-3.0", "MIT"}:
                return fail(f"{cid} collapsed to an identifier", art_clause)

    escalated = [
        c["id"]
        for c in live_inv["components"]
        if c.get("escalates_to_probe2")
    ]
    if set(escalated) != set(live_rows):
        return fail("escalation set != readings", {"esc": escalated, "read": sorted(live_rows)})

    cmds = [
        p.get("command")
        for p in (doc.get("named_probes") or [])
        if isinstance(p, dict)
    ]
    if not any("probe2_clause_read.py" in str(c) for c in cmds):
        return fail("named probe2 command absent", cmds)

    out = {
        "probe": "probe2-clause-read",
        "unit_id": UNIT,
        "pass": True,
        "method": "clause-extraction",
        "gpl_has_entire_work": True,
        "mislabeled_has_entire_work": True,
        "automated_spdx_ignored": True,
        "reading_n": len(live),
        "escalated": escalated,
        "artifact_matches_live": True,
    }
    (HERE / "probe2-clause-read.raw.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:ADV-0048-probe2 clause-level copyleft/unknown/custom reading")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
