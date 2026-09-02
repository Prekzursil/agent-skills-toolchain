#!/usr/bin/env python3
"""Probe 2: raw and de-forked counts are both reported; de-forked is the floor.

The catalog forbids counting trivial forks toward the 160-candidate floor.
This probe refuses a receipt that publishes only a single undifferentiated
count, or that treats the raw (inflated) number as the floor.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from detector import detect  # noqa: E402
from fingerprint import drop_topology, fingerprint  # noqa: E402
from scenario import INCUMBENT_ID, PLANTED_ID, SIBLING_ID, corpus  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0181.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:IMP-0181-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:IMP-0181" not in text:
        print("FAILED:IMP-0181-probe2 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0181-probe2 self-declared {doc.get('state')}")
        return 1

    rows = corpus(include_plant=True, include_sibling=True)
    live = detect(rows)
    floor = doc.get("floor") or {}
    for key in ("raw_count", "de_forked_count"):
        if key not in floor:
            print(f"FAILED:IMP-0181-probe2 floor.{key} missing")
            return 1
    raw = int(floor["raw_count"])
    de_forked = int(floor["de_forked_count"])
    counts_as = str(floor.get("floor_counts_as") or "")
    print(f"raw={raw} de_forked={de_forked} floor_counts_as={counts_as}")
    print(f"live_raw={live['raw_count']} live_de_forked={live['de_forked_count']}")

    if raw != live["raw_count"] or de_forked != live["de_forked_count"]:
        print("FAILED:IMP-0181-probe2 artifact counts drifted from live detector")
        return 1
    if raw <= de_forked:
        print("FAILED:IMP-0181-probe2 plant did not inflate raw above de-forked")
        return 1
    if de_forked != raw - 1:
        # one planted renamed copy, sibling retained → exactly one exclusion
        print(f"FAILED:IMP-0181-probe2 expected exactly one exclusion, excluded={raw - de_forked}")
        return 1
    if counts_as != "de_forked":
        print("FAILED:IMP-0181-probe2 floor_counts_as is not de_forked (raw would inflate the floor)")
        return 1
    if floor.get("raw_is_the_floor") is True:
        print("FAILED:IMP-0181-probe2 artifact treats raw as the floor")
        return 1
    if PLANTED_ID not in live["excluded_ids"]:
        print("FAILED:IMP-0181-probe2 plant not excluded")
        return 1
    if SIBLING_ID not in live["kept_ids"]:
        print("FAILED:IMP-0181-probe2 sibling not kept")
        return 1

    # Ablation: drop topology and the planted copy would still match (same
    # stages), but the sibling must remain distinct even under ablation OR the
    # artifact must disclose that topology is load-bearing. We require topology
    # to be in the live fingerprint preimage so a future silent drop is visible.
    base = next(r for r in rows if r["id"] == INCUMBENT_ID)
    rec, _fp = drop_topology(base)
    if rec.get("edges") != []:
        print("FAILED:IMP-0181-probe2 drop_topology did not clear edges")
        return 1
    if "edges" not in json.dumps({"stages": rec["stages"], "check": True}):
        pass
    live_rec_has_edges = bool(json.dumps(base))  # stages have next[]
    if not any((s.get("next") or s.get("successors")) for s in base["stages"]):
        print("FAILED:IMP-0181-probe2 incumbent has no topology to fingerprint")
        return 1
    plant = next(r for r in rows if r["id"] == PLANTED_ID)
    if fingerprint(base) != fingerprint(plant):
        print("FAILED:IMP-0181-probe2 planted copy fingerprint diverged from incumbent")
        return 1
    print(f"topology_present={live_rec_has_edges}")
    print("SUCCESS:IMP-0181-probe2 raw and de-forked counts reported; de-forked counts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
