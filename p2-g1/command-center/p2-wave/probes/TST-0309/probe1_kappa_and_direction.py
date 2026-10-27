#!/usr/bin/env python3
"""Probe 1: Cohen kappa on the overlap subset with per-class error direction.

Signal A (source): pairwise-marginals kappa + error_direction on live labels.
Signal B (verifier): confusion-matrix kappa on the same labels, rebuilt as n_ij
without walking the pairwise Counter path.

Controls:
  * forced agreement (judge := oracle) => kappa == 1
  * permutation of judge labels (fixed seed) => |kappa| small
  * estate precedent: n=50, accuracy=0.86, 100% of errors toward-match

Does not trust copied numbers in the receipt: it recomputes from cases.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from bench.cases import (  # noqa: E402
    CORPUS_REL,
    load_corpus,
    materialize_corpus,
    overlap_only,
)
from bench.judges import JUDGE_A, judge_label  # noqa: E402
from bench.kappa import (  # noqa: E402
    cohen_kappa_from_matrix,
    cohen_kappa_pairwise,
    confusion_counts,
    error_direction,
    permute_labels,
)
from bench.oracle import oracle_label  # noqa: E402

UNIT = "TST-0309"
ART = REPO / "command-center/receipts/TST-0309.json"
PERM_SEED = 20260824


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def close(a: float, b: float, atol: float = 1e-12) -> bool:
    return math.isclose(a, b, rel_tol=0.0, abs_tol=atol)


def main() -> int:
    materialize_corpus(REPO)
    cases = load_corpus(REPO)
    overlap = overlap_only(cases)
    if len(overlap) != 50:
        return fail(f"overlap n={len(overlap)} want 50")

    oracle = [oracle_label(c) for c in overlap]
    judge_a = [judge_label(c, JUDGE_A) for c in overlap]

    pairwise = cohen_kappa_pairwise(oracle, judge_a)
    grid = confusion_counts(oracle, judge_a)
    from_grid = cohen_kappa_from_matrix(grid)
    direction = error_direction(oracle, judge_a)

    if not close(pairwise["kappa"], from_grid["kappa"]):
        return fail(
            f"kappa paths disagree pairwise={pairwise['kappa']} matrix={from_grid['kappa']}"
        )
    if not close(pairwise["po"], from_grid["po"]):
        return fail("observed-agreement paths disagree")
    if pairwise["n"] != 50 or direction["n"] != 50:
        return fail(f"n={pairwise['n']} dir_n={direction['n']}")
    if not close(direction["accuracy"], 0.86):
        return fail(f"accuracy={direction['accuracy']} want 0.86")
    if direction["errors"] != 7 or direction["false_match"] != 7:
        return fail(f"errors={direction['errors']} fm={direction['false_match']}")
    if direction["false_mismatch"] != 0:
        return fail(f"false_mismatch={direction['false_mismatch']} want 0")
    if direction["direction"] != "toward-match" or not direction["all_errors_one_way"]:
        return fail(f"direction={direction['direction']} one_way={direction['all_errors_one_way']}")
    per_class = direction["per_class"]
    if per_class["match"]["errors"] != 0:
        return fail("match-class should have zero errors (no false-mismatch)")
    if per_class["mismatch"]["errors"] != 7:
        return fail("mismatch-class should carry all 7 false-match errors")
    if not close(pairwise["kappa"], 0.72):
        return fail(f"kappa={pairwise['kappa']} want 0.72")

    forced = cohen_kappa_pairwise(oracle, list(oracle))
    if not close(forced["kappa"], 1.0):
        return fail(f"forced-agree kappa={forced['kappa']} want 1")

    permuted = cohen_kappa_pairwise(oracle, permute_labels(judge_a, PERM_SEED))
    if abs(permuted["kappa"]) > 0.35:
        return fail(f"permutation kappa={permuted['kappa']} not near 0")
    if close(permuted["kappa"], pairwise["kappa"]):
        return fail("permutation kappa identical to live kappa (control is not independent)")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if "SUCCESS:TST-0309" not in ART.read_text(encoding="utf-8"):
            return fail("receipt sentinel absent")
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"receipt self-declared {st}")
        reported = doc.get("kappa_overlap") or {}
        if not close(float(reported.get("kappa")), pairwise["kappa"]):
            return fail(
                f"receipt kappa {reported.get('kappa')} != live {pairwise['kappa']}"
            )
        raw = doc.get("raw_overlap_pairs") or []
        if len(raw) != 50:
            return fail(f"receipt raw pairs n={len(raw)}")
        re_o = [r["oracle"] for r in raw]
        re_a = [r["judge_a"] for r in raw]
        recomputed = cohen_kappa_pairwise(re_o, re_a)
        if not close(recomputed["kappa"], pairwise["kappa"]):
            return fail("receipt raw pairs do not reproduce live kappa")
        if re_o != oracle or re_a != judge_a:
            return fail("receipt raw pairs do not match live per-case labels")

    payload = {
        "pass": True,
        "probe": "probe1-kappa-and-direction",
        "unit_id": UNIT,
        "n": 50,
        "kappa": pairwise["kappa"],
        "accuracy": direction["accuracy"],
        "direction": direction["direction"],
        "false_match": direction["false_match"],
        "false_mismatch": direction["false_mismatch"],
        "per_class": per_class,
        "pairwise_method": pairwise["method"],
        "matrix_method": from_grid["method"],
        "forced_kappa": forced["kappa"],
        "permuted_kappa": permuted["kappa"],
        "corpus": CORPUS_REL,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"kappa={pairwise['kappa']} n=50 accuracy=0.86 "
        f"direction=toward-match false_match=7 false_mismatch=0"
    )
    print("SUCCESS:TST-0309-probe1 kappa and one-way error direction (computed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
