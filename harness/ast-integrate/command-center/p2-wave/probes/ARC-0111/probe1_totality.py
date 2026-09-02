#!/usr/bin/env python3
"""Probe 1: totality is computed, both-states, silently-dropped option fires.

Good fixture: mapped + out_of_scope + superseded + unmapped == selected count.
Bad mutant: drop one unmapped id from the unmapped list; totality must fail.
Known-present: I5 is mapped to a contract clause.
Silently-dropped: M04 has no ruling and appears in unmapped, not omitted.
Live tree: same arithmetic holds (including the NEVER_FILLED 0=0 case).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import coverage as C  # noqa: E402

ART = REPO / "command-center/phase4/conformance/ARC-0111.json"
SENTINEL = "SUCCESS:ARC-0111"


def _fail(msg: str) -> int:
    print(f"FAILED:ARC-0111-probe1 {msg}")
    return 1


def main() -> int:
    fx = C.run_fixture(HERE)
    tot = fx["totality"]
    print(f"fixture {tot['equation']} holds={tot['holds']}")
    if not tot["holds"]:
        return _fail("fixture totality does not hold")
    if tot["selected_count"] < 1:
        return _fail("fixture selected set is empty (vacuous totality)")
    if tot["sum"] != tot["selected_count"]:
        return _fail("fixture sum != selected_count")

    mapped_ids = [r["id"] for r in fx["mapped"]]
    oos_ids = [r["id"] for r in fx["out_of_scope"]]
    sup_ids = [r["id"] for r in fx["superseded"]]
    unm_ids = [r["id"] for r in fx["unmapped"]]
    print(f"mapped={mapped_ids} oos={oos_ids} superseded={sup_ids} unmapped={unm_ids}")

    if "I5" not in mapped_ids:
        return _fail("known-present I5 not mapped")
    i5 = next(r for r in fx["mapped"] if r["id"] == "I5")
    clause_ids = [c.get("clause_id") for c in i5.get("clauses") or []]
    if "ARC-0078.C1" not in clause_ids:
        return _fail(f"I5 missing ARC-0078.C1 clauses={clause_ids}")
    if "J10" not in oos_ids:
        return _fail("J10 not in out_of_scope")
    if "C12" not in sup_ids:
        return _fail("C12 not in superseded")
    if "M04" not in unm_ids:
        return _fail("silently-dropped control M04 missing from unmapped")

    mutant = C.drop_unmapped_mutant(fx)
    print(f"mutant dropped={mutant['dropped']} holds={mutant['totality']['holds']}")
    if mutant["totality"]["holds"]:
        return _fail("totality stayed true after dropping an unmapped id")
    if mutant["dropped"] not in mutant["totality"]["missing_from_buckets"]:
        return _fail("dropped id not reported as missing_from_buckets")

    live = C.run_live(REPO)
    lt = live["totality"]
    print(
        f"live status={live['selected_status']} {lt['equation']} holds={lt['holds']}"
    )
    if not lt["holds"]:
        return _fail("live totality does not hold")
    if live["selected_status"] == "NEVER_FILLED" and live["selected_count"] != 0:
        return _fail("NEVER_FILLED selected_count must be 0")

    if not ART.is_file():
        return _fail("conformance artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return _fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return _fail(f"self-declared {doc.get('state')}")
    art_tot = ((doc.get("fixture_coverage") or {}).get("totality")) or {}
    if art_tot.get("selected_count") != tot["selected_count"]:
        return _fail("artifact fixture selected_count drift")
    if art_tot.get("holds") is not True:
        return _fail("artifact fixture totality not holds")
    live_doc = doc.get("live_coverage") or {}
    if live_doc.get("selected_status") != live["selected_status"]:
        return _fail("artifact live selected_status drift")
    live_tot = live_doc.get("totality") or {}
    if live_tot.get("selected_count") != live["selected_count"]:
        return _fail(
            f"artifact live selected_count drift "
            f"art={live_tot.get('selected_count')!r} live={live['selected_count']!r}"
        )
    print("SUCCESS:ARC-0111-probe1 totality both-states silent-drop")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
