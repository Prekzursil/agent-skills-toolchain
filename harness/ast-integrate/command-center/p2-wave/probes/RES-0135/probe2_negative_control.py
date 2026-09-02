#!/usr/bin/env python3
"""Probe 2: negative control + security fail-closed (disjoint from probe 1).

Catalog control: at least one FORBIDDEN cell and one SEPARATE-PACKAGE cell.
An all-TOGETHER mutant must fail (copyleft clauses were read).
Security mandate: unlicensed and vendor-riders never TOGETHER; rider snapshot
still contains the non-commercial distribution limit.
Does not rebuild the lattice (that is probe 1).
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ARTIFACT = (
    REPO
    / "command-center"
    / "research"
    / "supply-chain"
    / "RES-0135-licence-compatibility-matrix-for-aggregation.json"
)
N8N = HERE / "snapshots" / "n8n-sustainable-use-LICENSE.md"
USC = HERE / "snapshots" / "uscode-17-106.html"
CCSA = HERE / "snapshots" / "cc-by-sa-4.0.txt"

FORBIDDEN = "FORBIDDEN"
SEPARATE = "SEPARATE-PACKAGE"
TOGETHER = "TOGETHER"


def _fail(msg: str) -> int:
    print(f"FAILED:RES-0135-probe2 {msg}")
    return 1


def control_ok(cells: list) -> tuple[bool, str, dict]:
    if not isinstance(cells, list) or not cells:
        return False, "no cells", {}
    counts = {FORBIDDEN: 0, SEPARATE: 0, TOGETHER: 0}
    unlicensed_together = 0
    rider_together = 0
    sa_copyleft_together = 0
    for cell in cells:
        if not isinstance(cell, dict):
            return False, "non-object cell", {}
        v = cell.get("verdict")
        if v in counts:
            counts[v] += 1
        left, right = cell.get("left"), cell.get("right")
        pair = {left, right}
        if v == TOGETHER and "unlicensed" in pair:
            unlicensed_together += 1
        if v == TOGETHER and "vendor-riders" in pair:
            rider_together += 1
        software = {"GPL-3.0", "AGPL-3.0", "MPL-2.0"}
        if v == TOGETHER and "CC-BY-SA" in pair and pair & software:
            sa_copyleft_together += 1
    if counts[FORBIDDEN] < 1:
        return False, "no FORBIDDEN cell", counts
    if counts[SEPARATE] < 1:
        return False, "no SEPARATE-PACKAGE cell", counts
    if unlicensed_together:
        return False, "unlicensed marked TOGETHER", counts
    if rider_together:
        return False, "vendor-riders marked TOGETHER", counts
    if sa_copyleft_together:
        return False, "CC-BY-SA vs software copyleft marked TOGETHER", counts
    return True, "ok", counts


def main() -> int:
    if not ARTIFACT.is_file():
        return _fail("artifact missing")
    doc = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    cells = doc.get("cells") or []
    ok, why, counts = control_ok(cells)
    if not ok:
        return _fail(f"control: {why} {counts}")

    mutant = []
    for cell in cells:
        row = dict(cell)
        row["verdict"] = TOGETHER
        mutant.append(row)
    mok, _, _ = control_ok(mutant)
    if mok:
        return _fail("all-TOGETHER mutant still passed (control silent in both states)")

    n8n = N8N.read_text(encoding="utf-8")
    if "free of charge for" not in n8n or "non-commercial purposes" not in n8n:
        return _fail("vendor-rider snapshot lost non-commercial distribution limit")
    usc = USC.read_text(encoding="utf-8")
    if "exclusive rights" not in usc.lower():
        return _fail("17 USC §106 snapshot lost exclusive-rights language")
    ccsa = CCSA.read_text(encoding="utf-8")
    if "ShareAlike" not in ccsa or "Adapter's License" not in ccsa:
        return _fail("CC-BY-SA snapshot lost ShareAlike / Adapter's License")

    # Both-states on the permissive cluster: those cells stay TOGETHER.
    permissive = {"MIT", "Apache-2.0", "BSD", "CC0", "CC-BY"}
    perm_cells = [
        c
        for c in cells
        if isinstance(c, dict)
        and c.get("left") in permissive
        and c.get("right") in permissive
    ]
    if not perm_cells or any(c.get("verdict") != TOGETHER for c in perm_cells):
        return _fail("permissive cluster is not all TOGETHER")

    print(
        json.dumps(
            {
                "probe": "probe2-negative-control",
                "unit_id": "RES-0135",
                "counts": counts,
                "forbidden_present": True,
                "separate_package_present": True,
                "all_together_mutant_fails": True,
                "unlicensed_never_together": True,
                "vendor_riders_never_together": True,
                "permissive_cluster_together": True,
                "rider_noncommercial_limit_present": True,
            },
            indent=2,
            sort_keys=True,
        )
    )
    print(
        f"FORBIDDEN={counts[FORBIDDEN]} SEPARATE-PACKAGE={counts[SEPARATE]} "
        f"TOGETHER={counts[TOGETHER]} mutant_fails=True"
    )
    print("SUCCESS:RES-0135-probe2 FORBIDDEN and SEPARATE-PACKAGE negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
