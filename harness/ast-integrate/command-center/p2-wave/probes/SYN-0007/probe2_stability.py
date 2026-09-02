#!/usr/bin/env python3
"""Named probe 2: ranking stability, phase anachronism, ESTIMATE band.

Uses the planted fixture DAG (different field than probe 1's live artifact
subtree check). Shuffle must not change rank order. A Phase-16 intervention
over a Phase-1 finding is rejected. ESTIMATE without a band is rejected.
"""
from __future__ import annotations

import copy
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from rank import rank_interventions, ranking_ids  # noqa: E402

ART = REPO / "command-center/synthesis/SYN-0007.intervention-ranking.json"
FIXTURE = HERE / "fixtures" / "planted_hierarchy.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:SYN-0007-probe2 live artifact missing")
        return 1
    live = json.loads(ART.read_text(encoding="utf-8"))
    if live.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:SYN-0007-probe2 live state", live.get("state"))
        return 1

    planted = json.loads(FIXTURE.read_text(encoding="utf-8"))
    costs = planted.get("costs") or {}
    first = rank_interventions(planted, costs)
    ids1 = ranking_ids(first)
    if len(ids1) < 3:
        print(f"FAILED:SYN-0007-probe2 planted ranking too short {ids1}")
        return 1

    rng = random.Random(13)
    shuffled = copy.deepcopy(planted)
    rng.shuffle(shuffled["nodes"])
    rng.shuffle(shuffled["edges"])
    second = rank_interventions(shuffled, shuffled.get("costs") or costs)
    ids2 = ranking_ids(second)
    if ids1 != ids2:
        print("FAILED:SYN-0007-probe2 unstable ranking under shuffle")
        print(" ", ids1)
        print(" ", ids2)
        return 1

    # Equal-score tie: CAUSE-TIE-A must precede CAUSE-TIE-B by id.
    if "CAUSE-TIE-A" in ids1 and "CAUSE-TIE-B" in ids1:
        if ids1.index("CAUSE-TIE-A") > ids1.index("CAUSE-TIE-B"):
            print("FAILED:SYN-0007-probe2 tie-break not lexicographic", ids1)
            return 1

    rejected_cls = {r.get("intervention_id"): r.get("class") for r in first["rejected"]}
    if rejected_cls.get("CAUSE-LATE") != "phase-anachronism":
        print("FAILED:SYN-0007-probe2 CAUSE-LATE not rejected as phase-anachronism", first["rejected"])
        return 1
    if "CAUSE-LATE" in ids1:
        print("FAILED:SYN-0007-probe2 anachronism leaked into ranking")
        return 1

    mutant_costs = copy.deepcopy(costs)
    mutant_costs["CAUSE-EST"] = {"basis": "ESTIMATE"}  # band stripped
    mutant = rank_interventions(planted, mutant_costs)
    mutant_rej = {r.get("intervention_id"): r.get("class") for r in mutant["rejected"]}
    if mutant_rej.get("CAUSE-EST") != "asserted-cost-without-band":
        print("FAILED:SYN-0007-probe2 ESTIMATE without band not rejected", mutant["rejected"])
        return 1
    if "CAUSE-EST" in ranking_ids(mutant):
        print("FAILED:SYN-0007-probe2 unbanded ESTIMATE leaked into ranking")
        return 1

    # Live artifact must also use a deterministic sort_key on every row.
    live_rows = live.get("ranking") or []
    keys = [tuple(r.get("sort_key") or []) for r in live_rows]
    if keys != sorted(keys):
        print("FAILED:SYN-0007-probe2 live sort_key not ordered")
        return 1

    out = {
        "probe": "probe2-stability",
        "unit_id": "SYN-0007",
        "planted_ranked": ids1,
        "shuffle_stable": True,
        "phase_anachronism_rejected": True,
        "estimate_without_band_rejected": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:SYN-0007-probe2 stability, anachronism, estimate-band")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
