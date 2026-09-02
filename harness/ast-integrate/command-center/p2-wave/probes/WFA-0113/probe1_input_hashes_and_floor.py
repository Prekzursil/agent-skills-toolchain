#!/usr/bin/env python3
"""Probe 1: matched input hashes and variance floor measured before comparison."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fixtures import BUDGET_LIMIT, SEED, cases  # noqa: E402
from harness import input_fingerprint, run_experiment  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0113-benchmark-matched-pair-harness.json"
SENTINEL = "SUCCESS:WFA-0113"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0113-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text or doc.get("unit_id") != "WFA-0113":
        return fail("sentinel/unit")

    live = run_experiment(seed=SEED, budget_limit=BUDGET_LIMIT, planted_floor=0.05)
    floor = live["variance_floor"]
    if not floor["measured_before_comparisons"]:
        return fail("floor flag false")
    if int(floor["max_control_seq"]) >= int(floor["min_comparison_seq"]):
        return fail(
            f"floor not first max_control={floor['max_control_seq']} "
            f"min_compare={floor['min_comparison_seq']}"
        )
    if not live["control_runs"]:
        return fail("no control runs")
    if any(r["phase"] != "variance-floor" for r in live["control_runs"]):
        return fail("control phase mismatch")
    if any(
        r["phase"] == "comparison" and r["seq"] <= floor["max_control_seq"]
        for r in live["runs"]
    ):
        return fail("comparison leaked into control seq")

    independent = {
        case["id"]: input_fingerprint(case, SEED, BUDGET_LIMIT) for case in cases()
    }

    kept = [p for p in live["pairs"] if not p.get("dropped_arm")]
    if not kept:
        return fail("no kept pairs")
    for pair in kept:
        cid = pair["case_id"]
        expect = independent[cid]
        if pair["left_input_hash"] != expect or pair["right_input_hash"] != expect:
            return fail(
                f"hash mismatch {pair['left_workflow']}/{pair['right_workflow']} "
                f"{cid} live={pair['left_input_hash'][:12]} expect={expect[:12]}"
            )
        if not pair["input_hashes_match"]:
            return fail(f"pair hashes disagree {cid}")
        if pair["left_budget_limit"] != pair["right_budget_limit"]:
            return fail(f"budget mismatch {cid}")
        if pair["left_seed"] != pair["right_seed"]:
            return fail(f"seed mismatch {cid}")

    art_pairs = [p for p in (doc.get("pairs") or []) if not p.get("dropped_arm")]
    if len(art_pairs) != len(kept):
        return fail(f"artifact pair count {len(art_pairs)} != live {len(kept)}")
    live_index = {
        (p["left_workflow"], p["right_workflow"], p["case_id"]): p for p in kept
    }
    for p in art_pairs:
        key = (p["left_workflow"], p["right_workflow"], p["case_id"])
        got = live_index.get(key)
        if not got:
            return fail(f"artifact pair missing in live {key}")
        if p["left_input_hash"] != got["left_input_hash"]:
            return fail(f"artifact hash drift {key}")

    art_floor = doc.get("variance_floor") or {}
    if not art_floor.get("measured_before_comparisons"):
        return fail("artifact floor not measured first")
    if int(art_floor.get("max_control_seq") or 0) >= int(
        art_floor.get("min_comparison_seq") or 0
    ):
        return fail("artifact seq order")
    if float(art_floor.get("live_oracle_floor")) != float(floor["live_oracle_floor"]):
        return fail("artifact floor drift")

    if not doc.get("budget_parity", {}).get("equal"):
        return fail("artifact budget_parity.equal is not true")
    if not doc.get("input_hash_parity", {}).get("all_matched_pairs_agree"):
        return fail("artifact input_hash_parity false")

    print(
        json.dumps(
            {
                "probe": "probe1-input-hashes-and-floor",
                "unit_id": "WFA-0113",
                "pairs": len(kept),
                "distinct_input_hashes": len(set(independent.values())),
                "max_control_seq": floor["max_control_seq"],
                "min_comparison_seq": floor["min_comparison_seq"],
                "live_oracle_floor": floor["live_oracle_floor"],
                "hashes_match": True,
                "floor_first": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        "pairs={0} hashes={1} floor_first=True floor={2}".format(
            len(kept),
            len(set(independent.values())),
            floor["live_oracle_floor"],
        )
    )
    print("SUCCESS:WFA-0113-probe1 input hashes match and variance floor precedes comparison")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
