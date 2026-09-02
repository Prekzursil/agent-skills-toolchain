#!/usr/bin/env python3
"""Probe 2: below-minimum intersection blocks; complementarity stays out of H2H.

Bad state: fusion-only exotic cases folded into the head-to-head score, or a
low-n comparison reporting a winner.
Good state: fold refused; complementarity listed separately; low-n blocked.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
from bench.matched_pairing import (  # noqa: E402
    PairingError,
    load_scenario,
    pair_comparison,
)

SCENARIO = HERE / "fixtures" / "scenario.json"
ART = REPO / "command-center/receipts/TST-0296.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0296-probe2 {msg}")
    return 1


def main() -> int:
    scenario = load_scenario(SCENARIO)
    cases = scenario["cases"]
    workflows = scenario["workflows"]

    h2h = next(c for c in scenario["comparisons"] if c["id"] == "cmp-h2h-sufficient")
    low = next(c for c in scenario["comparisons"] if c["id"] == "cmp-low-n-blocked")

    good = pair_comparison(
        cases=cases,
        workflows=workflows,
        fusion_id=h2h["fusion"],
        source_ids=list(h2h["sources"]),
        min_intersection=int(h2h["min_intersection"]),
        comparison_id=h2h["id"],
    )
    blocked = pair_comparison(
        cases=cases,
        workflows=workflows,
        fusion_id=low["fusion"],
        source_ids=list(low["sources"]),
        min_intersection=int(low["min_intersection"]),
        comparison_id=low["id"],
    )

    fold_refused = False
    try:
        pair_comparison(
            cases=cases,
            workflows=workflows,
            fusion_id=h2h["fusion"],
            source_ids=list(h2h["sources"]),
            min_intersection=int(h2h["min_intersection"]),
            comparison_id=h2h["id"],
            fold_complementarity=True,
        )
    except PairingError as exc:
        fold_refused = "complementarity_fold_forbidden" in str(exc)
    if not fold_refused:
        return fail("fold_complementarity was not refused")

    exo = {str(c["id"]) for c in cases if c["required_capabilities"] == ["exotic"]}
    if not exo:
        return fail("no exotic complementarity cases in fixture")
    if set(good["complementarity"]["case_ids"]) != exo:
        return fail(f"complementarity={good['complementarity']} want={sorted(exo)}")
    if good["complementarity"]["folded_into_head_to_head"]:
        return fail("complementarity folded into head-to-head")
    leaked = set(good["complementarity"]["case_ids"]) & set(
        good["intersection_case_ids"]
    )
    if leaked:
        return fail(f"complementarity leaked into intersection {sorted(leaked)}")
    h2h_ids = set((good.get("head_to_head") or {}).get("case_ids") or [])
    if exo & h2h_ids:
        return fail("exotic cases scored in head-to-head")
    if not good["union_inflation_diagnostic"]["manufactures_fusion_win"]:
        return fail("union diagnostic did not show manufactured fusion win")
    if good["union_inflation_diagnostic"]["not_used_for_official_result"] is not True:
        return fail("union diagnostic was treated as official")
    if good["reported_win"] or good["winner"] is not None:
        return fail("official result crowned a winner from union inflation")

    if blocked["comparison_status"] != "BLOCKED_LOW_N":
        return fail(f"low-n status={blocked['comparison_status']}")
    if blocked["intersection_size"] >= blocked["min_intersection"]:
        return fail("low-n fixture is not actually below minimum")
    if blocked["reported_win"] or blocked["winner"] is not None:
        return fail("low-n comparison reported a win")
    if blocked["head_to_head"] is not None:
        return fail("low-n comparison emitted a head-to-head score")
    if blocked["block_reason"] != "intersection_below_minimum":
        return fail(f"block_reason={blocked['block_reason']}")
    if not blocked["excluded"]:
        return fail("blocked comparison missing exclusion list")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        by_id = {r["comparison_id"]: r for r in doc.get("comparisons") or []}
        pub_h = by_id.get("cmp-h2h-sufficient")
        pub_b = by_id.get("cmp-low-n-blocked")
        if not pub_h or not pub_b:
            return fail("receipt missing published comparisons")
        if pub_h.get("complementarity", {}).get("folded_into_head_to_head"):
            return fail("receipt folded complementarity")
        if sorted(pub_h.get("complementarity", {}).get("case_ids") or []) != sorted(
            exo
        ):
            return fail("receipt complementarity ids mismatch")
        if pub_b.get("comparison_status") != "BLOCKED_LOW_N":
            return fail("receipt did not block low-n")
        if pub_b.get("reported_win"):
            return fail("receipt reported a low-n win")

    summary = {
        "probe": "probe2-asymmetric",
        "unit_id": "TST-0296",
        "fold_refused": True,
        "complementarity_count": good["complementarity"]["count"],
        "low_n_blocked": True,
        "low_n_intersection": blocked["intersection_size"],
        "union_would_manufacture_win": True,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "fold_refused=True complementarity="
        + str(good["complementarity"]["count"])
        + " low_n="
        + str(blocked["intersection_size"])
        + " blocked=True"
    )
    print("SUCCESS:TST-0296-probe2 complementarity and below-minimum block")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
