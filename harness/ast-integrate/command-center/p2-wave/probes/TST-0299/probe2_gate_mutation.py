#!/usr/bin/env python3
"""Probe 2: certification gate consumes CORRECTED; uncorrected mutant goes red."""
from __future__ import annotations

import json

import paths as P
from bench.certification import certification_gate, mutant_reads_uncorrected
from bench.tournament import mixed_tournament


def fail(msg: str) -> int:
    print(f"FAILED:TST-0299-probe2 {msg}")
    return 1


def lucky_not_certified(gate: dict, lucky_id: str) -> bool:
    """The production test: a chance winner must not be certified."""
    return lucky_id not in gate["certified_ids"]


def main() -> int:
    mixed = mixed_tournament()
    rows = mixed["family"]["comparisons"]
    live = certification_gate(rows, consume="corrected")
    mutant = mutant_reads_uncorrected(rows)

    print(f"family_size={len(rows)}")
    print(f"live_consume={live['consume']} live_source=holm_rejected certified={live['certified_ids']}")
    print(
        f"mutant_consume={mutant['consume']} mutant_source=uncorrected_significant "
        f"certified={mutant['certified_ids']}"
    )
    if live["consume"] != "corrected":
        return fail("live gate did not consume corrected")
    if mutant["consume"] != "uncorrected":
        return fail("mutant gate did not consume uncorrected")
    if live["certified_count"] >= mutant["certified_count"]:
        return fail("mutant did not certify a strictly larger set than Holm")

    planted = set(mixed["true_ids"])
    live_set = set(live["certified_ids"])
    if planted != live_set:
        return fail(f"Holm certified {sorted(live_set)} != planted true {sorted(planted)}")

    luckies = [
        r["id"]
        for r in rows
        if r["uncorrected_significant"] and r["id"] not in live_set
    ]
    print(f"lucky_uncorrected_only={luckies}")
    if not luckies:
        return fail("no uncorrected-only winner to distinguish the mutant")
    lucky = luckies[0]

    live_test = lucky_not_certified(live, lucky)
    mutant_test = lucky_not_certified(mutant, lucky)
    print(f"test_lucky_not_certified live={live_test} mutant={mutant_test} lucky_id={lucky}")
    if live_test is not True:
        return fail("live gate certified an uncorrected-only lucky winner")
    if mutant_test is not False:
        return fail("mutant did not go red: it also refused the lucky winner")
    print("mutant_goes_red=True")

    for decision in live["decisions"]:
        if decision["source"] != "holm_rejected":
            return fail(f"live decision source is {decision['source']}, not holm_rejected")
    for decision in mutant["decisions"]:
        if decision["source"] != "uncorrected_significant":
            return fail(f"mutant decision source is {decision['source']}")

    if not P.RECEIPT.is_file():
        return fail("receipt missing")
    text = P.RECEIPT.read_text(encoding="utf-8")
    if P.SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in P.NOT_DELIVERING:
        return fail(f"self-declared:{st}")
    gate = doc.get("gate") or {}
    if gate.get("live_consumes") != "corrected":
        return fail("receipt live gate does not consume corrected")
    if gate.get("mutant_goes_red") is not True:
        return fail("receipt does not record mutant-goes-red")
    if gate.get("lucky_id") not in luckies:
        return fail("receipt lucky_id is not an uncorrected-only winner")
    if doc.get("certification_list_shrinks") is not True:
        return fail("receipt certification list did not shrink")

    print(
        "shrink "
        f"uncorrected={len(mixed['uncorrected_certified_ids'])} "
        f"holm={live['certified_count']} delta={mixed['shrink_delta']}"
    )
    print("SUCCESS:TST-0299-probe2 certification-gate mutant-reads-uncorrected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
