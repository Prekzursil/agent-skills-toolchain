#!/usr/bin/env python3
"""Probe 1: both-states trivial-fork detector.

Planted renamed copy MUST be excluded. Similar-name distinct sibling MUST be
retained. A naive name-similarity matcher is the opposite instrument: it drops
the sibling and keeps the renamed copy — proving the production detector is
not a name grep.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from detector import both_states, detect  # noqa: E402
from fingerprint import fingerprint, mutate_one_gate  # noqa: E402
from scenario import (  # noqa: E402
    INCUMBENT_ID,
    PLANTED_ID,
    SIBLING_ID,
    corpus,
    planted_renamed_copy,
    similar_name_distinct_sibling,
)

ART = REPO / "command-center/receipts/IMP-0181.json"


def main() -> int:
    rows = corpus(include_plant=True, include_sibling=True)
    ids = {r["id"] for r in rows}
    if PLANTED_ID not in ids or SIBLING_ID not in ids or INCUMBENT_ID not in ids:
        print("FAILED:IMP-0181-probe1 corpus missing plant or sibling")
        return 1

    plant = planted_renamed_copy()
    base = next(r for r in rows if r["id"] == INCUMBENT_ID)
    if fingerprint(plant) != fingerprint(base):
        print("FAILED:IMP-0181-probe1 planted copy fingerprint diverged from incumbent")
        print(f"  plant={fingerprint(plant)}")
        print(f"  base={fingerprint(base)}")
        return 1

    sibling = similar_name_distinct_sibling()
    if fingerprint(sibling) == fingerprint(base):
        print("FAILED:IMP-0181-probe1 sibling collided with incumbent fingerprint")
        return 1

    mutated = mutate_one_gate(base, "unresolved_p0 == 99")
    if fingerprint(mutated) == fingerprint(base):
        print("FAILED:IMP-0181-probe1 gate mutation was fingerprint-silent")
        return 1

    result = both_states(rows, distinct_sibling_id=SIBLING_ID, planted_id=PLANTED_ID)
    print(json.dumps({k: v for k, v in result.items() if k not in {"structural", "naive"}}, sort_keys=True))
    print(
        "structural excluded={0} kept_has_sibling={1} naive_drops_sibling={2}".format(
            result["structural"]["excluded_ids"],
            SIBLING_ID in result["structural"]["kept_ids"],
            result["naive_name_matcher_drops_sibling"],
        )
    )

    if not result["planted_renamed_copy_excluded"]:
        print("FAILED:IMP-0181-probe1 planted renamed copy was not excluded")
        return 1
    if not result["distinct_similar_name_sibling_retained"]:
        print("FAILED:IMP-0181-probe1 similar-name distinct sibling was excluded")
        return 1
    if not result["false_positive_control_pass"]:
        print("FAILED:IMP-0181-probe1 naive name matcher did not drop the sibling (control inert)")
        return 1

    # Artifact must record the same both-states outcome; probes re-measure, they
    # do not trust a self-declared boolean.
    if not ART.is_file():
        print("FAILED:IMP-0181-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0181-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:IMP-0181" not in ART.read_text(encoding="utf-8"):
        print("FAILED:IMP-0181-probe1 sentinel absent")
        return 1
    live = detect(rows)
    art_floor = doc.get("floor") or {}
    if int(art_floor.get("raw_count")) != live["raw_count"]:
        print("FAILED:IMP-0181-probe1 artifact raw_count drifted")
        return 1
    if int(art_floor.get("de_forked_count")) != live["de_forked_count"]:
        print("FAILED:IMP-0181-probe1 artifact de_forked_count drifted")
        return 1
    both = doc.get("both_states") or {}
    if PLANTED_ID not in (both.get("excluded_ids") or live["excluded_ids"]):
        if PLANTED_ID not in live["excluded_ids"]:
            print("FAILED:IMP-0181-probe1 plant not in live excluded set")
            return 1
    print("SUCCESS:IMP-0181-probe1 planted copy excluded; similar-name sibling retained")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
