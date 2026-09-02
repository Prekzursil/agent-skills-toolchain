#!/usr/bin/env python3
"""Probe 2: NOT-FLAGGED control (mechanically different from probe 1).

A NOT-FLAGGED row with a basis must exist. Mutating all rows to FLAGGED,
or injecting a license ruling, must fail the same predicates (both-states).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from lib import ART, DISPOSITIONS, NO_LEGAL, OVERCLAIM, UNIT_ID, load_json  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT_ID}-probe2 {msg}")
    return 1


def not_flagged_ok(doc: dict) -> tuple[bool, str]:
    caps = doc.get("capabilities") or []
    rows = [c for c in caps if isinstance(c, dict) and c.get("disposition") == "NOT-FLAGGED"]
    if not rows:
        return False, "zero-not-flagged"
    for row in rows:
        basis = str(row.get("factual_basis") or "")
        if len(basis) < 80:
            return False, f"thin-not-flagged:{row.get('id')}"
        if OVERCLAIM.search(basis):
            return False, f"overclaim-not-flagged:{row.get('id')}"
        if not (row.get("source_lineage") or []):
            return False, f"not-flagged-without-lineage:{row.get('id')}"
    return True, f"not-flagged={len(rows)}"


def legal_clean(doc: dict) -> tuple[bool, str]:
    if NO_LEGAL not in json.dumps(doc, ensure_ascii=False):
        return False, "disclaimer-absent"
    if doc.get("no_legal_conclusion_statement") != NO_LEGAL:
        return False, "disclaimer-field"
    for cap in doc.get("capabilities") or []:
        klass = (cap or {}).get("classification") or {}
        if klass.get("legal_conclusion") is True:
            return False, f"legal_conclusion-true:{cap.get('id')}"
        if klass.get("eccn") or klass.get("license_required") is True or klass.get("itar"):
            return False, f"ruling-injected:{cap.get('id')}"
        if OVERCLAIM.search(str(cap.get("factual_basis") or "")):
            return False, f"basis-ruling:{cap.get('id')}"
    return True, "clean"


def main() -> int:
    if not ART.is_file():
        return fail("artifact-absent")
    doc = load_json(ART)
    ok, why = not_flagged_ok(doc)
    if not ok:
        return fail(why)
    clean, cwhy = legal_clean(doc)
    if not clean:
        return fail(cwhy)

    flagged_only = copy.deepcopy(doc)
    for cap in flagged_only["capabilities"]:
        cap["disposition"] = "FLAGGED"
    m1_ok, _ = not_flagged_ok(flagged_only)
    if m1_ok:
        return fail("all-flagged-mutant-still-passes")

    thin = copy.deepcopy(doc)
    for cap in thin["capabilities"]:
        if cap.get("disposition") == "NOT-FLAGGED":
            cap["factual_basis"] = "none"
            break
    m2_ok, _ = not_flagged_ok(thin)
    if m2_ok:
        return fail("thin-basis-mutant-still-passes")

    ruling = copy.deepcopy(doc)
    ruling["capabilities"][0]["factual_basis"] = (
        "This capability is export-controlled and requires a license under ECCN is 4D004."
    )
    ruling["capabilities"][0]["classification"] = {
        "eccn": "4D004",
        "itar": False,
        "legal_conclusion": True,
        "license_required": True,
    }
    m3_ok, _ = legal_clean(ruling)
    if m3_ok:
        return fail("legal-ruling-mutant-still-passes")

    disps = sorted({c.get("disposition") for c in doc["capabilities"]})
    if set(disps) != set(DISPOSITIONS):
        return fail(f"partition-incomplete:{disps}")

    out = {
        "all_flagged_mutant_fails": (not m1_ok),
        "legal_ruling_mutant_fails": (not m3_ok),
        "not_flagged_ids": [c["id"] for c in doc["capabilities"] if c.get("disposition") == "NOT-FLAGGED"],
        "pass": True,
        "probe": "probe2-not-flagged-control",
        "thin_basis_mutant_fails": (not m2_ok),
        "unit_id": UNIT_ID,
        "why": why,
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    print(
        f"SUCCESS:{UNIT_ID}-probe2 NOT-FLAGGED control fires; "
        "all-FLAGGED and license-ruling mutants go red"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
