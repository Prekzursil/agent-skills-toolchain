#!/usr/bin/env python3
"""Control the JACCARD near-duplicate path specifically.

The main control seeded an exact string copy, which the exact-normalised-string detector
caught. That leaves the Jaccard/high-overlap path UNCONTROLLED, and it reported zero pairs
at every threshold on the real corpus. Zero could mean "no padding" or "broken detector".
This probe settles it: feed the checker synthetic unit pairs with KNOWN overlap and confirm
the reported Jaccard matches a hand-computed value.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _catalog_integrity as ci  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def mk(uid, title, target):
    return {
        "id": uid,
        "title": title,
        "question_or_target": target,
        "__file": "synthetic.json",
        "__idx": 0,
    }


print("=" * 78)
print("PART 1 - hand-checked Jaccard on synthetic pairs")
print("=" * 78)
cases = [
    (
        "identical",
        "Verify the shared completion predicate rejects an empty artifact",
        "Verify the shared completion predicate rejects an empty artifact",
        1.0,
    ),
    (
        "one word differs",
        "Verify the shared completion predicate rejects an empty artifact",
        "Verify the shared completion predicate rejects an absent artifact",
        None,
    ),
    (
        "stopwords only differ",
        "Verify the shared completion predicate rejects an empty artifact",
        "Verify a shared completion predicate that rejects the empty artifact",
        1.0,
    ),
    (
        "half overlap",
        "alpha beta gamma delta epsilon zeta eta theta",
        "alpha beta gamma delta iota kappa lambda mu",
        None,
    ),
]
for name, t1, t2, expect in cases:
    s1 = frozenset(ci.norm_tokens(t1))
    s2 = frozenset(ci.norm_tokens(t2))
    j = len(s1 & s2) / len(s1 | s2)
    units = [mk("AAA-0001", t1, ""), mk("AAA-0002", t2, "")]
    rep = ci.check_near_duplicates(units, jaccard_threshold=0.50)
    got = rep["pair_count_at_threshold"]
    print(
        f"  {name:24s} handJ={j:.4f} pairs>=0.50={got} "
        f"tokens={sorted(s1)} / {sorted(s2)}"
    )
    if expect is not None:
        assert abs(j - expect) < 1e-9, f"{name}: expected J={expect}, hand-computed {j}"

print()
print("=" * 78)
print("PART 2 - inject a near-duplicate into the REAL corpus and require a fire")
print("=" * 78)
units, _ = ci.load_dir(ci.SLICES)
base = dict(units[0])
print(f"  donor id={base['id']}")
print(f"  donor title={base['title'][:110]}")

# 2a. exact copy under a new id -> J must be 1.0
clone = dict(base)
clone["id"] = "ZZZ-0001"
clone["__file"] = "synthetic-clone.json"
rep = ci.check_near_duplicates(units + [clone], jaccard_threshold=0.80)
hit = any(
    "ZZZ-0001" in c["ids"] and base["id"] in c["ids"]
    for c in rep["high_overlap_clusters_worst"]
)
print(
    f"  [exact clone]  pairs>=0.80={rep['pair_count_at_threshold']} "
    f"clusters={rep['high_overlap_cluster_count']} seeded-pair-clustered={hit}"
)
print(f"                 histogram={rep['pair_count_by_threshold']}")
assert hit, "FAIL: Jaccard path did not cluster an exact clone"

# 2b. mutate ~15% of tokens -> should still exceed 0.80
toks = ci.norm_tokens(f"{base['title']} {base['question_or_target']}")
n_change = max(1, len(set(toks)) // 7)
keep = list(dict.fromkeys(toks))
mutated = keep[:-n_change] + [f"zqxw{i}" for i in range(n_change)]
part = dict(base)
part["id"] = "ZZZ-0002"
part["title"] = " ".join(mutated)
part["question_or_target"] = ""
part["__file"] = "synthetic-partial.json"
rep2 = ci.check_near_duplicates(units + [part], jaccard_threshold=0.80)
hit2 = any("ZZZ-0002" in c["ids"] for c in rep2["high_overlap_clusters_worst"])
s1 = frozenset(keep)
s2 = frozenset(mutated)
print(
    f"  [{n_change}/{len(keep)} tokens changed] handJ="
    f"{len(s1 & s2) / len(s1 | s2):.4f} pairs>=0.80={rep2['pair_count_at_threshold']} "
    f"seeded-clustered={hit2}"
)

print()
print("=" * 78)
print("PART 3 - what IS the real corpus' maximum pairwise similarity?")
print("=" * 78)
rep3 = ci.check_near_duplicates(units, jaccard_threshold=0.35)
print(f"  pairs>=0.35 = {rep3['pair_count_at_threshold']}")
print(f"  histogram   = {rep3['pair_count_by_threshold']}")
print(
    f"  clusters    = {rep3['high_overlap_cluster_count']} "
    f"covering {rep3['units_in_high_overlap_cluster']} units"
)
top = rep3["high_overlap_clusters_worst"][:6]
for i, c in enumerate(top, 1):
    print(
        f"  {i}. size={c['size']} meanJ={c['mean_jaccard']} maxJ={c['max_jaccard']} "
        f"files={c['files']}"
    )
    for uid, t in list(zip(c["ids"], c["titles"]))[:4]:
        print(f"       {uid}  {t[:100]}")

out = os.path.join(HERE, "_catalog_jaccard_control_out.json")
with open(out, "w", encoding="utf-8") as fh:
    json.dump(
        {
            "exact_clone_fires": hit,
            "partial_clone_fires": hit2,
            "real_corpus_at_0.35": {
                "pairs": rep3["pair_count_at_threshold"],
                "histogram": rep3["pair_count_by_threshold"],
                "cluster_count": rep3["high_overlap_cluster_count"],
                "units_covered": rep3["units_in_high_overlap_cluster"],
                "worst": rep3["high_overlap_clusters_worst"][:20],
            },
        },
        fh,
        ensure_ascii=False,
        indent=1,
    )
print(f"\nwrote {out}")
print("CONTROL RESULT: exact_clone_fires=%s partial_clone_fires=%s" % (hit, hit2))
