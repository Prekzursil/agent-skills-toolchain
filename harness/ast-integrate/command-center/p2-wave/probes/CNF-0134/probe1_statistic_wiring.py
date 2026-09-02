#!/usr/bin/env python3
"""Probe 1: statistic wiring — forced agreement kappa~1, permuted kappa~0.

Also recomputes kappa from the published receipt table (reviewer path) when
the receipt is on disk.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import kappa as K  # noqa: E402

UNIT = "CNF-0134"
RECEIPT = REPO / "command-center" / "receipts" / "CNF-0134.json"
# Under independence with 4 equal categories, pe=0.25, simple SE(kappa)≈0.09
# for n=40. Bound 0.40 is >4 SE; a wiring bug (identity / not-shuffled) fails.
PERMUTE_ABS_MAX = 0.40


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    prereg = K.load_prereg()
    labels = K.labels_from_prereg(prereg)
    vec = K.forced_agree_vector(labels, per_cat=10)
    if len(set(vec)) != len(labels):
        return fail("forced-agree vector missing a category")
    forced = K.cohen_kappa(vec, list(vec), labels)
    print(
        f"forced_agree kappa={forced['kappa']:.12f} po={forced['po']:.6f} "
        f"pe={forced['pe']:.6f} n={forced['n']}"
    )
    if abs(forced["kappa"] - 1.0) > 1e-12:
        return fail(f"forced-agree kappa {forced['kappa']} not near 1")

    perm_seed = int(prereg["permute_control_seed"])
    shuffled = K.permute(vec, perm_seed)
    if shuffled == vec:
        return fail("permutation was the identity; statistic not stressed")
    if sorted(shuffled) != sorted(vec):
        return fail("permutation changed the multiset")
    perm = K.cohen_kappa(vec, shuffled, labels)
    print(
        f"permuted kappa={perm['kappa']:.12f} po={perm['po']:.6f} "
        f"pe={perm['pe']:.6f} seed={perm_seed}"
    )
    if abs(perm["kappa"]) >= PERMUTE_ABS_MAX:
        return fail(
            f"permuted kappa {perm['kappa']} not near 0 "
            f"(bound {PERMUTE_ABS_MAX})"
        )

    if not RECEIPT.is_file():
        return fail("receipt missing; cannot recompute published table")
    rec = json.loads(RECEIPT.read_text(encoding="utf-8"))
    view = K.domain_view(rec)
    table = view.get("raw_table") or {}
    counts = table.get("counts")
    pub_labels = table.get("labels")
    if not counts or not pub_labels:
        return fail("receipt raw_table missing")
    recomputed = K.kappa_from_counts(counts)
    published = float(view["point_estimate"])
    print(
        f"reviewer_recompute kappa={recomputed['kappa']:.12f} "
        f"published={published:.12f} po={recomputed['po']:.6f}"
    )
    if abs(recomputed["kappa"] - published) > 1e-12:
        return fail("published kappa does not match raw_table")
    rev_block = view.get("reviewer_recompute")
    if isinstance(rev_block, dict) and "kappa" in rev_block:
        published_rev = float(rev_block["kappa"])
    elif isinstance(rec.get("reviewer"), dict) and "recomputed_kappa" in rec["reviewer"]:
        published_rev = float(rec["reviewer"]["recomputed_kappa"])
    else:
        return fail("reviewer recompute missing")
    if abs(recomputed["kappa"] - published_rev) > 1e-12:
        return fail("reviewer.recomputed_kappa does not match table")
    thr = view.get("threshold_preregistration") or {}
    if float(thr.get("value")) != float(prereg["kappa_threshold"]):
        return fail("receipt threshold does not match prereg file")
    if thr.get("recorded_before_computation") is not True:
        return fail("threshold not marked recorded_before_computation")
    prereg_sha, _ = K.sha256_file(K.PREREG_PATH)
    cited = str(thr.get("prereg_sha256") or "")
    if cited != prereg_sha:
        return fail("receipt prereg_sha256 does not match threshold_prereg.json")
    print(
        json.dumps(
            {
                "forced_kappa": forced["kappa"],
                "pass": True,
                "permuted_kappa": perm["kappa"],
                "probe": "probe1-statistic-wiring",
                "reviewer_kappa": recomputed["kappa"],
                "unit_id": UNIT,
            },
            sort_keys=True,
        )
    )
    print(f"SUCCESS:{UNIT}-probe1 forced-agree~1 permute~0 table-recompute")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
