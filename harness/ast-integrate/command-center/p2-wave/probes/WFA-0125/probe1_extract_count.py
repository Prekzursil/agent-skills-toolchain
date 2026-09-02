#!/usr/bin/env python3
"""Probe 1: mechanical extract, count assertion, both-states deletion.

Known-good: parsed item count equals IMP-0178 family sum.
Known-bad: dropping IMP-0234 changes the item count (hardcoded 96 would not).
Mutating research/evidence 15 -> 14 changes the family sum.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import extract as X  # noqa: E402

ART = REPO / X.OUT_REL


def main() -> int:
    units = X.catalog_units()
    extracted = X.extract_requirements(units)
    print(f"EXTRACT source={extracted['source']} n={extracted['n']}")
    print(f"EXTRACT unique={extracted['unique_n']}")
    print(f"EXTRACT errors={extracted['errors']}")
    print(f"EXTRACT spec_bytes_present={extracted['spec_bytes_present']}")
    print(f"FAMILY_IMP0178 {extracted['family_counts_imp0178']}")
    print(f"FAMILY_PARSED {extracted['family_counts_parsed']}")
    print(f"IMP0178_SUM {extracted['expected_total_from_imp0178']}")
    print(f"QUESTION_FAMS {extracted['wfa0125_question_families']}")

    if extracted["errors"]:
        print("FAILED:WFA-0125-probe1 extraction errors")
        return 1
    expected = extracted["expected_total_from_imp0178"]
    if expected is None or expected < 1:
        print("FAILED:WFA-0125-probe1 IMP-0178 family sum missing")
        return 1
    if extracted["n"] != expected:
        print(
            f"FAILED:WFA-0125-probe1 n={extracted['n']} != "
            f"imp0178_sum={expected}"
        )
        return 1
    if extracted["unique_n"] != extracted["n"]:
        print("FAILED:WFA-0125-probe1 duplicate requirement ids")
        return 1
    if extracted["family_counts_parsed"] != extracted["family_counts_imp0178"]:
        print("FAILED:WFA-0125-probe1 per-family mismatch")
        return 1
    if len(extracted["wfa0125_question_families"]) != 6:
        print("FAILED:WFA-0125-probe1 question does not list 6 families")
        return 1

    controls = X.both_states_extract(units)
    print(
        f"BOTH-STATES drop={controls['drop_unit']} "
        f"full_n={controls['full_n']} reduced_n={controls['reduced_n']} "
        f"changed={controls['count_changed']}"
    )
    print(
        f"BOTH-STATES family_sum_full={controls['family_sum_full']} "
        f"mutated={controls['family_sum_mutated']} "
        f"changed={controls['family_sum_changed']}"
    )
    if not controls["count_changed"]:
        print("FAILED:WFA-0125-probe1 dropping IMP-0234 did not change count")
        return 1
    if controls["reduced_n"] >= controls["full_n"]:
        print("FAILED:WFA-0125-probe1 reduced count not smaller")
        return 1
    if not controls["family_sum_changed"]:
        print("FAILED:WFA-0125-probe1 family-sum mutation silent")
        return 1

    if not ART.is_file():
        print("FAILED:WFA-0125-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("sentinel") != "SUCCESS:WFA-0125":
        print("FAILED:WFA-0125-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:WFA-0125-probe1 self-declared {doc.get('state')}")
        return 1
    art_n = int((doc.get("counts") or {}).get("total") or 0)
    if art_n != extracted["n"]:
        print(f"FAILED:WFA-0125-probe1 artifact total {art_n} != {extracted['n']}")
        return 1
    art_ids = [
        c.get("requirement_id")
        for c in (doc.get("cells") or [])
        if isinstance(c, dict)
    ]
    live_ids = [r["id"] for r in extracted["requirements"]]
    if art_ids != live_ids:
        print("FAILED:WFA-0125-probe1 artifact ids diverge from live extract")
        return 1

    print(
        "NEGATIVE CONTROL verbatim: dropping IMP-0234 changes parsed n "
        f"{controls['full_n']}->{controls['reduced_n']}; mutating "
        "research/evidence 15->14 changes family sum "
        f"{controls['family_sum_full']}->{controls['family_sum_mutated']}."
    )
    print("SUCCESS:WFA-0125-probe1 extract-count both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
