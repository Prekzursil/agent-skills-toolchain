#!/usr/bin/env python3
"""Probe 2: live scaling curve, independent refit, linear vs super-linear controls.

Re-fits from raw (n, wall_s) only. Does not take the author's exponent as input.
Requires: one genuinely linear stage, one predicted-linear stage that measures
super-linear (prediction failure, not silently corrected), resource guard that
can trip without freezing the box, 20,480 either completed or ceiling-aborted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fit import classify_exponent  # noqa: E402
from measure import LINEAR_MAX, SUPERLINEAR_MIN, census, reviewer_refit  # noqa: E402

RAW = HERE / "probe2-fit.raw.json"


def _fail(msg: str) -> int:
    print(f"FAILED:BLD-0055-probe2 {msg}")
    return 1


def main() -> int:
    doc = census()
    refits = reviewer_refit(doc)
    by_stage = {r["stage"]: r["reviewer_fit"] for r in refits}

    graph = by_stage.get("dependency_graph_closure") or {}
    hashing = by_stage.get("manifest_hashing") or {}
    pairwise = by_stage.get("pairwise_duplicate_detection") or {}

    if not graph.get("ok") or graph.get("saw_author_exponent") is not False:
        RAW.write_text(json.dumps({"census": "partial", "graph": graph}, default=str) + "\n")
        return _fail("reviewer fit of dependency_graph_closure missing or saw author exponent")
    if not hashing.get("ok"):
        return _fail("reviewer fit of manifest_hashing failed")

    g_exp = float(graph["exponent"])
    h_exp = float(hashing["exponent"])
    graph_class = classify_exponent(g_exp)
    hash_class = classify_exponent(h_exp)

    if hash_class != "linear" or h_exp > LINEAR_MAX:
        return _fail(
            f"manifest_hashing not linear exponent={h_exp} class={hash_class}"
        )
    if g_exp < SUPERLINEAR_MIN or graph_class not in {"super-linear", "quadratic-or-worse"}:
        return _fail(
            f"dependency_graph_closure not super-linear exponent={g_exp} class={graph_class}"
        )

    pred_fail = None
    for row in doc.get("prediction_failures") or []:
        if row.get("stage") == "dependency_graph_closure":
            pred_fail = row
            break
    if pred_fail is None:
        return _fail("predicted-linear graph closure was not reported as prediction failure")

    linear = doc.get("linear_stage")
    if not linear or linear.get("stage") != "manifest_hashing":
        return _fail(f"linear_stage missing or wrong: {linear}")

    planted = (doc.get("resource_guard") or {}).get("planted_trip") or {}
    if not planted.get("tripped") or planted.get("froze_box"):
        return _fail(f"resource guard planted trip failed {planted}")

    top = None
    for row in doc.get("rows") or []:
        if row.get("n") == 20480:
            top = row
            break
    if top is None:
        return _fail("n=20480 row absent")
    if not top.get("validator_ok") and not top.get("aborted"):
        return _fail("n=20480 corpus failed validator and was not aborted")
    if top.get("aborted") and not top.get("extrapolated") and top.get("abort_reason") == "validator-rejected-corpus":
        return _fail("n=20480 rejected by validator")

    coll = doc.get("collision_control") or {}
    if not coll.get("disjoint_ok") or not coll.get("overlap_rejected"):
        return _fail(f"catalog merger both-states failed {coll}")

    # Pairwise is the named quadratic candidate; require it not classify linear.
    if pairwise.get("ok"):
        p_exp = float(pairwise["exponent"])
        if p_exp <= LINEAR_MAX:
            return _fail(f"pairwise classified linear exponent={p_exp}")

    out = {
        "pass": True,
        "n_grid": doc.get("n_grid"),
        "reviewer_fits": refits,
        "graph_exponent": g_exp,
        "hash_exponent": h_exp,
        "pairwise_exponent": pairwise.get("exponent"),
        "prediction_failure": pred_fail,
        "linear_stage": linear,
        "resource_guard": doc.get("resource_guard"),
        "top_n_aborted": bool(top.get("aborted")),
        "top_n_abort_reason": top.get("abort_reason"),
        "saw_author_exponent": False,
        "hardware": doc.get("hardware"),
        "rows": [
            {
                "n": r.get("n"),
                "validator_ok": r.get("validator_ok"),
                "aborted": r.get("aborted"),
                "stages": {
                    k: {"wall_s": v.get("wall_s"), "aborted": v.get("aborted")}
                    for k, v in (r.get("stages") or {}).items()
                },
            }
            for r in doc.get("rows") or []
        ],
        "real_catalog_reference": doc.get("real_catalog_reference"),
        "collision_control": coll,
        "census": doc,
    }
    RAW.write_text(json.dumps(out, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(
        f"graph_exp={g_exp:.3f} hash_exp={h_exp:.3f} "
        f"pairwise_exp={pairwise.get('exponent')} "
        f"pred_fail=dependency_graph_closure linear=manifest_hashing "
        f"guard_tripped={planted.get('tripped')} n20480_aborted={top.get('aborted')}"
    )
    print("SUCCESS:BLD-0055-probe2 independent refit; prediction-failure reported")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
