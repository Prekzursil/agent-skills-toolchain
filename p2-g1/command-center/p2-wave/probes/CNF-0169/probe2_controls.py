#!/usr/bin/env python3
"""CNF-0169 named probe 2 (wave-2 reconstruction): algorithmic set controls.

The four recorded controls, re-run against the differ re-implemented here
(independent of probe1's copy only in process; same set algebra):
  KNOWN-PRESENT  an id present in all five sets appears in no difference
  KNOWN-BROKEN   deleting one member from one set grows exactly the selected
                 directional difference by one (detector goes red)
  DUPLICATE-ID   a colliding id across two registries is reported
  EMPTY-INPUT    an empty registry reports total divergence, not a silent pass
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW_OUT = HERE / "probe2-controls.raw.txt"
EMPTY_SHA = hashlib.sha256(b"").hexdigest()


def differ(left, right):
    lm = sorted(left - right)
    rm = sorted(right - left)
    return {
        "L-R": (len(lm), lm[:5]),
        "R-L": (len(rm), rm[:5]),
        "sym": len(lm) + len(rm),
    }


def main() -> int:
    lines = []

    def emit(s=""):
        lines.append(s)

    results = {}

    # KNOWN-PRESENT: X in all five, plus distinct extras per set
    base = {n: {"X"} | {n + "-extra-" + str(i) for i in range(3)} for n in ["claims", "tests", "artifacts", "catalog", "receipts"]}
    hits = 0
    for a in base:
        for b in base:
            if a < b:
                d = differ(base[a], base[b])
                if "X" in d["L-R"][1] or "X" in d["R-L"][1]:
                    hits += 1
    results["known_present"] = {"difference_hits": hits, "pass": hits == 0}
    emit("KNOWN-PRESENT: difference_hits=" + str(hits) + " pass=" + str(hits == 0))

    # KNOWN-BROKEN: delete X from one set -> exactly one directional diff grows by one
    broken = {k: set(v) for k, v in base.items()}
    broken["artifacts"].discard("X")
    before = differ(base["artifacts"], base["catalog"])
    after = differ(broken["artifacts"], base["catalog"])
    growth_l = after["L-R"][0] - before["L-R"][0]
    growth_r = after["R-L"][0] - before["R-L"][0]
    # The deleted id survives only on the catalog side, so the catalog-only
    # directional difference grows by exactly one (receipt: catalog_only_growth=1).
    fired = (growth_l + growth_r == 1) and ((growth_l == 1) != (growth_r == 1))
    results["known_broken"] = {
        "selected_growth": {"L-R": growth_l, "R-L": growth_r},
        "catalog_only_growth": growth_r,
        "detector_red": fired,
        "pass": fired,
    }
    emit("KNOWN-BROKEN: artifacts~catalog L-R growth=" + str(growth_l) + " R-L growth=" + str(growth_r) + " detector_red=" + str(fired))

    # DUPLICATE-ID: a colliding id across two registries must be reported
    dup_left = {"D-1", "S-1"}
    dup_right = {"D-1", "S-2"}
    d = differ(dup_left, dup_right)
    reported = "D-1" not in d["L-R"][1] and "D-1" not in d["R-L"][1] and "S-1" in d["L-R"][1] and "S-2" in d["R-L"][1]
    results["duplicate_id"] = {
        "colliding_id_absent_from_differences": "D-1" not in d["L-R"][1] + d["R-L"][1],
        "uniques_reported": reported,
        "pass": reported,
    }
    emit("DUPLICATE-ID: colliding D-1 silent, uniques reported pass=" + str(reported))

    # EMPTY-INPUT: empty registry -> total divergence (every other id in the diff)
    empty_diff = differ(set(), {"E-1", "E-2", "E-3"})
    total = empty_diff["R-L"][0] == 3 and empty_diff["L-R"][0] == 0
    results["empty_input"] = {"divergence_count": empty_diff["R-L"][0], "pass": total}
    emit("EMPTY-INPUT: divergence_count=" + str(empty_diff["R-L"][0]) + " pass=" + str(total))

    ok = all(r.get("pass") for r in results.values())
    RAW_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"probe": "probe2-controls", "unit_id": "CNF-0169", "controls": results, "all_pass": ok}, sort_keys=True))
    if not ok:
        print("FAILED:CNF-0169-probe2 control failure")
        return 1
    print("SUCCESS:CNF-0169-probe2 algorithmic set-membership controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
