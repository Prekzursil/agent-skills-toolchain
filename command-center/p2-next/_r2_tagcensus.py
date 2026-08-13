"""ROUND-2: re-measure the tag figure this lane inherited and repeated without checking.

Round 1's residual 6 asserted: "blocker_census.py:185-190 prints a tag-sum (137 occurrences)
directly under a unit count (51), reading as 'all are review-gated'". Two claims, both re-measured
here from the COMMITTED blobs, with the tool's own live output as the second signal.

Reports the number that actually answers the question -- DISTINCT UNITS carrying a review-naming
classification tag -- not an occurrence sum, and cross-checks it against the ladder's rail count.
"""

from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "vs", REPO / "command-center/p2-next/vendor_satisfiability.py"
)
vs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vs)

rows = vs.load_units("committed")
paths = [r["output_path"] for r in rows]
blobs = vs.batch_blobs("HEAD", paths)

tag_occurrences = Counter()
units_with_review_tag, units_with_any_tag = set(), set()
REVIEWISH = ("review", "refut")

for r in rows:
    rec = json.loads(blobs[r["output_path"]])
    tags = []
    for container in (rec.get("failure") or {}, rec):
        c = container.get("classification") if isinstance(container, dict) else None
        if isinstance(c, list):
            tags += [t for t in c if isinstance(t, str)]
        elif isinstance(c, str):
            tags.append(c)
    tags = sorted(set(tags))
    if tags:
        units_with_any_tag.add(r["id"])
    for t in tags:
        tag_occurrences[t] += 1
        if any(k in t.lower() for k in REVIEWISH):
            units_with_review_tag.add(r["id"])

total_occ = sum(tag_occurrences.values())
reviewish_occ = sum(
    n for t, n in tag_occurrences.items() if any(k in t.lower() for k in REVIEWISH)
)
rail = {r["id"] for r in rows if r["verdict"] == vs.BLOCKED_RAIL}

print(f"blocked units (committed basis)          : {len(rows)}")
print(f"units carrying >=1 classification tag    : {len(units_with_any_tag)}")
print(f"DISTINCT tags                            : {len(tag_occurrences)}")
print(f"TOTAL tag OCCURRENCES                    : {total_occ}")
print(f"review/refut-naming tag OCCURRENCES      : {reviewish_occ}")
print(
    f"DISTINCT UNITS with a review-naming tag  : {len(units_with_review_tag)}  <-- the answerable number"
)
print(f"ladder: units requiring an openai reviewer: {len(rail)}")
print(
    f"  review-tagged but NOT rail-blocked     : {sorted(units_with_review_tag - rail)}"
)
print(f"  rail-blocked but NO review tag         : {len(rail - units_with_review_tag)}")

print("\nround-1 residual 6 said '137 occurrences'. Measured here:", total_occ)
print("REFUTED" if total_occ != 137 else "reproduced")

(REPO / "command-center/p2-next/R2-TAG-CENSUS.json").write_text(
    json.dumps(
        {
            "basis": "committed HEAD blobs",
            "blocked_units": len(rows),
            "distinct_tags": len(tag_occurrences),
            "total_tag_occurrences": total_occ,
            "reviewish_tag_occurrences": reviewish_occ,
            "distinct_units_with_review_tag": len(units_with_review_tag),
            "rail_blocked_units": len(rail),
            "review_tagged_not_rail": sorted(units_with_review_tag - rail),
            "rail_without_review_tag": sorted(rail - units_with_review_tag),
            "round1_claimed_occurrences": 137,
            "round1_claim_status": "REFUTED" if total_occ != 137 else "reproduced",
            "tag_histogram": dict(tag_occurrences.most_common()),
        },
        indent=2,
    ),
    encoding="utf-8",
    newline="\n",
)
print("wrote command-center/p2-next/R2-TAG-CENSUS.json")
