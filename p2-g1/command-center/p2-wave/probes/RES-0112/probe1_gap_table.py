#!/usr/bin/env python3
"""Probe 1: sentinel, gap table, already-satisfied control, mechanism evidence."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UNIT = "RES-0112"
ART = REPO / "command-center/research/RES-0112.json"
SENTINEL = (
    "SUCCESS:RES-0112 in the receipt AND a property gap table citing "
    "existing gates at file:line with at least one already-satisfied row"
)
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("catalog sentinel absent")
    doc = json.loads(text)
    if doc.get("unit_id") != UNIT:
        return fail(f"unit_id={doc.get('unit_id')!r}")
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return fail(f"self-declared {st}")

    table = doc.get("property_gap_table")
    if not isinstance(table, list) or len(table) < 2:
        return fail("property_gap_table missing or too short")

    already = [r for r in table if isinstance(r, dict) and r.get("status") == "already-satisfied"]
    absent = [r for r in table if isinstance(r, dict) and r.get("status") == "absent"]
    if not already:
        return fail("control: no already-satisfied row")
    if not absent:
        return fail("no absent row (nothing claimed lacking)")

    for row in table:
        cites = row.get("gate_citations") or []
        if not cites:
            return fail(f"{row.get('property_id')} has no gate_citations")
        for c in cites:
            if not c.get("path") or not isinstance(c.get("line"), int):
                return fail(f"{row.get('property_id')} citation missing path/line")
            if not str(c.get("snippet") or "").strip():
                return fail(f"{row.get('property_id')} citation missing snippet")
        if row.get("status") == "absent":
            # tests_required: cite file:line when claiming absent
            if not all(isinstance(c.get("line"), int) and c["line"] >= 1 for c in cites):
                return fail(f"absent {row.get('property_id')} lacks file:line")

    mechs = doc.get("mechanisms") or []
    if len(mechs) < 2:
        return fail("need at least two mechanisms")
    promoted = 0
    for m in mechs:
        doi = m.get("doi") or m.get("report")
        if not doi:
            return fail(f"{m.get('id')} missing doi/report")
        if not m.get("section_or_figure"):
            return fail(f"{m.get('id')} missing section_or_figure")
        if m.get("promoted") is True:
            if not m.get("effect_size") or not m.get("baseline"):
                return fail(f"{m.get('id')} promoted without effect+baseline (must be E3)")
            if str(m.get("evidence_tier") or "").upper() == "E3":
                return fail(f"{m.get('id')} E3 cannot promote")
            promoted += 1
        else:
            if not m.get("effect_size") or not m.get("baseline"):
                if str(m.get("evidence_tier") or "").upper() != "E3":
                    return fail(f"{m.get('id')} missing numbers but not marked E3")
    if promoted < 1:
        return fail("no promoted mechanism with effect+baseline")

    rejected = doc.get("e3_headlines_rejected") or []
    if not rejected:
        return fail("need an E3 headline-without-baseline rejection (the rule must fire)")

    rev = doc.get("reviewer") or {}
    if rev.get("default_when_insufficient") != "REFUTED":
        return fail("reviewer must default to REFUTED")
    if not rev.get("surviving_claims_strongest_caveat"):
        return fail("surviving claim missing strongest caveat")

    out = {
        "pass": True,
        "probe": "probe1-gap-table",
        "unit_id": UNIT,
        "already_satisfied": [r["property_id"] for r in already],
        "absent": [r["property_id"] for r in absent],
        "promoted_mechanisms": [
            m["id"] for m in mechs if m.get("promoted") is True
        ],
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"already={len(already)} absent={len(absent)} promoted={promoted} "
        f"e3_rejected={len(rejected)}"
    )
    print(f"SUCCESS:{UNIT}-probe1 property gap table + already-satisfied control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
