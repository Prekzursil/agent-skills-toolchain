#!/usr/bin/env python3
"""Probe 2: planted-distinct control + independent live recount.

Two genuinely different units that share catalog vocabulary and the same
input set must NOT collide. An independent tokenizer (no stemmer, no synonym
map) must agree that the live assembled catalog has the same collision count
as the receipt. Blind sample of 20 is recorded as 0/0 when there are no
collisions to sample.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from controls import run_distinct_control  # noqa: E402
from fingerprint import normalize_input_set, target_text  # noqa: E402
from independent import independent_collisions  # noqa: E402
from scan import load_catalog, scan_catalog  # noqa: E402
from schema_gate import SENTINEL as GATE_SENTINEL  # noqa: E402
from schema_gate import assert_valid, errors_for  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0412.json"


def inputs_only_would_collide(a: dict, b: dict) -> bool:
    """Negative control: hashing inputs alone merges IMP-0412 with IMP-0456."""
    return normalize_input_set(a.get("inputs")) == normalize_input_set(b.get("inputs"))


def main() -> int:
    catalog = load_catalog()
    units = catalog.get("work_units") or []
    distinct = run_distinct_control(units)
    print(json.dumps(distinct, sort_keys=True, default=str))
    if not distinct["distinct_pair_did_not_collide"]:
        print("FAILED:IMP-0412-probe2 planted distinct pair collided")
        return 1
    if not distinct["planted_same_inputs"]:
        print("FAILED:IMP-0412-probe2 planted distinct inputs were not equal")
        return 1
    if not distinct["similar_vocabulary"]:
        print("FAILED:IMP-0412-probe2 planted pair did not share vocabulary")
        return 1
    if distinct["live_imp0412_vs_imp0456_collided"]:
        print("FAILED:IMP-0412-probe2 live IMP-0412 vs IMP-0456 collided")
        return 1

    by_id = {u["id"]: u for u in units}
    a, b = by_id["IMP-0412"], by_id["IMP-0456"]
    if not inputs_only_would_collide(a, b):
        print("FAILED:IMP-0412-probe2 expected IMP-0412 and IMP-0456 to share inputs")
        return 1
    if target_text(a).strip() == target_text(b).strip():
        print("FAILED:IMP-0412-probe2 live pair has identical target text")
        return 1

    live = scan_catalog(REPO)
    indep = independent_collisions(units)
    if live["too_coarse"]["abort"]:
        print("FAILED:IMP-0412-probe2 fingerprint too coarse", live["too_coarse"])
        return 1
    if live["collision_pair_count"] != len(indep):
        print(
            "FAILED:IMP-0412-probe2 independent recount disagrees "
            f"primary={live['collision_pair_count']} independent={len(indep)}"
        )
        print(json.dumps(indep[:8], indent=2))
        return 1

    if not ART.is_file():
        print("FAILED:IMP-0412-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SENTINEL:IMP-0412:DUPLICATES-FINGERPRINTED" not in ART.read_text(encoding="utf-8"):
        print("FAILED:IMP-0412-probe2 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0412-probe2 receipt state={doc.get('state')}")
        return 1
    if int(doc["catalog_scan"]["collision_pair_count"]) != live["collision_pair_count"]:
        print("FAILED:IMP-0412-probe2 receipt collision count != live scan")
        return 1
    if int(doc["catalog_scan"]["assembled_work_unit_count"]) != live["unit_count"]:
        print("FAILED:IMP-0412-probe2 receipt unit count != live scan")
        return 1

    try:
        assert_valid(doc)
    except SystemExit as exc:
        print(str(exc))
        print("FAILED:IMP-0412-probe2 local schema gate")
        for line in errors_for(doc)[:12]:
            print(" ", line)
        return 1
    if GATE_SENTINEL not in ART.read_text(encoding="utf-8"):
        print("FAILED:IMP-0412-probe2 schema_gate sentinel drifted")
        return 1

    requested = int(doc["reviewer"]["requested_blind_sample"])
    available = int(doc["reviewer"]["available_collisions"])
    if available != live["collision_pair_count"]:
        print("FAILED:IMP-0412-probe2 reviewer available_collisions mismatch")
        return 1
    if available == 0 and requested != 20:
        print("FAILED:IMP-0412-probe2 reviewer should still request a sample of 20")
        return 1

    print(
        f"distinct_ok=True live_pairs={live['collision_pair_count']} "
        f"independent_pairs={len(indep)} n={live['unit_count']} "
        f"fp_rate={doc['false_positive_rate']['rate_display']}"
    )
    print("SUCCESS:IMP-0412-probe2 planted-distinct and independent recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
