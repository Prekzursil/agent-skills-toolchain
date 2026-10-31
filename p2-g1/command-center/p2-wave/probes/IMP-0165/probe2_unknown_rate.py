"""IMP-0165 probe 2: the UNKNOWN rate is a computed number over the whole candidate set.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0165/probe2_unknown_rate.py
An independent recount of unknown/total must equal unknown_rate(); appending one more
UNKNOWN moves the number; an all-known subset rates exactly 0.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools"))

from workflow_foundry.role_extract import UNKNOWN, normalize_role, unknown_rate  # noqa: E402


def main() -> int:
    known_roles = [
        "critic", "red team", "refuter", "author", "chair", "judge", "scribe",
        "builder", "moderator", "peer reviewer", "skeptic", "challenger",
        "architect", "redteam", "adversarial refuter", "implementer",
        "observer", "voter",
    ]
    unknown_names = ["unknown-%02d" % i for i in range(12)]
    rows = []
    for i, s in enumerate(known_roles + unknown_names):
        canon = normalize_role(s)
        rows.append(
            {
                "candidate_id": "c-%02d" % i,
                "surface": s,
                "canonical": canon,
                "label": UNKNOWN if canon == UNKNOWN else "known",
            }
        )

    stats = unknown_rate(rows)
    recount_unknown = sum(1 for r in rows if r["canonical"] == UNKNOWN)
    recount_rate = recount_unknown / len(rows) if rows else 0.0
    mismatches = [
        r["candidate_id"]
        for r in rows
        if (r["canonical"] == UNKNOWN) != (r["label"] == UNKNOWN)
    ]

    mutated = rows + [
        {"candidate_id": "c-extra", "surface": "novel-role-xq", "canonical": UNKNOWN,
         "label": UNKNOWN}
    ]
    mutated_stats = unknown_rate(mutated)

    all_known = [r for r in rows if r["canonical"] != UNKNOWN]
    zero_subset_rate = unknown_rate(all_known)["rate"]

    recomputed = (unknown_rate(mutated)["unknown"]) / (mutated_stats["total"])

    doc = {
        "unit_id": "IMP-0165",
        "probe": "probe2-unknown-rate",
        "stats": stats,
        "recount_rate": recount_rate,
        "recount_equals": abs(stats["rate"] - recount_rate) < 1e-12,
        "computed": isinstance(stats.get("rate"), float),
        "label_match": not mismatches,
        "mismatches": mismatches,
        "rate_moves_on_extra_unknown": mutated_stats["rate"] > stats["rate"],
        "mutated_rate": mutated_stats["rate"],
        "mutated_recount_equals": abs(mutated_stats["rate"] - recomputed) < 1e-12,
        "zero_subset_rate": zero_subset_rate,
        "both_states_rate": (
            mutated_stats["rate"] > stats["rate"] >= 0.0 and zero_subset_rate == 0.0
        ),
    }
    doc["pass"] = (
        doc["recount_equals"]
        and doc["computed"]
        and doc["label_match"]
        and doc["rate_moves_on_extra_unknown"]
        and doc["mutated_recount_equals"]
        and zero_subset_rate == 0.0
        and stats["total"] == 30
        and stats["unknown"] == 12
        and abs(stats["rate"] - 0.4) < 1e-12
    )
    out = Path(__file__).resolve().parent / "probe2-unknown-rate.raw.json"
    out.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps(doc, sort_keys=True))
    print("unknown_rate=%s unknown=%s/%s" % (stats["rate"], stats["unknown"], stats["total"]))
    if doc["pass"]:
        print("SUCCESS:IMP-0165-probe2 UNKNOWN rate is a computed number over the whole"
              " candidate set")
        return 0
    print("FAILED:IMP-0165-probe2 rate recount/mutation/subset control failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
