#!/usr/bin/env python3
"""Probe 2: matrix_expansion is NOT-NECESSARY; wish-list mutant fires; two-pass."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from grade import grade, wish_list  # noqa: E402
import sources as S  # noqa: E402

REPO = HERE.parents[3]
ART = REPO / S.OUT_REL
SENTINEL = S.SENTINEL


def fail(msg: str) -> int:
    print(f"FAILED:RES-0161-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if SENTINEL not in ART.read_text(encoding="utf-8"):
        return fail("sentinel-absent")

    live = grade()
    tp = live["two_pass"]
    if tp["relative_delta"] > 0.10:
        return fail(
            f"two-pass delta {tp['relative_delta']} exceeds 10% "
            f"(a={tp['pass_a_count']} b={tp['pass_b_count']})"
        )
    if not tp["within_10_percent"]:
        return fail("within_10_percent flag is false")
    art_tp = doc.get("two_pass") or {}
    if art_tp.get("pass_a_count") != tp["pass_a_count"] or art_tp.get(
        "pass_b_count"
    ) != tp["pass_b_count"]:
        return fail("artifact two-pass counts drifted from live re-count")

    neg = live["negative_control"]
    if neg["feature"] != "matrix_expansion" or neg["verdict"] != "NOT-NECESSARY":
        return fail("negative control is not matrix_expansion NOT-NECESSARY")
    if neg["github_actions_presence"] != "PRESENT":
        return fail("negative control feature is not PRESENT on github-actions")
    art_neg = doc.get("negative_control") or {}
    if art_neg.get("verdict") != "NOT-NECESSARY" or art_neg.get("feature") != "matrix_expansion":
        return fail("artifact negative_control drifted")

    if live["wish_list"]:
        return fail("live necessity is a wish list")
    mutant = copy.deepcopy(S.NECESSITY)
    for feat in mutant:
        mutant[feat] = dict(mutant[feat])
        mutant[feat]["verdict"] = "NECESSARY"
        mutant[feat]["negative_control"] = False
    if not wish_list(mutant):
        return fail("wish-list mutant silent")
    if wish_list(S.NECESSITY):
        return fail("live necessity detected as wish list")

    fam = live["families"]
    if not fam["sums_agree"]:
        return fail("family parsed_sum != definition_sum")
    if fam["parsed_sum"] != doc.get("blueprint_family_sum"):
        return fail("artifact family sum drifted")
    if len(fam["parsed"]) != 6:
        return fail("expected six family tokens")

    nec = {r["feature"]: r["verdict"] for r in live["necessity"]}
    if nec.get("matrix_expansion") != "NOT-NECESSARY":
        return fail("matrix_expansion not NOT-NECESSARY")
    necessary_n = sum(1 for v in nec.values() if v == "NECESSARY")
    if necessary_n != 7:
        return fail(f"expected 7 NECESSARY features, got {necessary_n}")

    payload = {
        "probe": "probe2-negative-control-and-two-pass",
        "unit_id": S.UNIT,
        "negative_control_feature": "matrix_expansion",
        "negative_control_verdict": "NOT-NECESSARY",
        "github_actions_matrix_present": True,
        "wish_list_mutant_fires": True,
        "live_not_wishlist": True,
        "pass_a_count": tp["pass_a_count"],
        "pass_b_count": tp["pass_b_count"],
        "relative_delta": tp["relative_delta"],
        "within_10_percent": True,
        "family_sum": fam["parsed_sum"],
        "necessary_n": necessary_n,
        "live_matches_artifact": True,
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        "SUCCESS:RES-0161-probe2 matrix_expansion NOT-NECESSARY; "
        "wish-list mutant fires; two-pass counts agree"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
