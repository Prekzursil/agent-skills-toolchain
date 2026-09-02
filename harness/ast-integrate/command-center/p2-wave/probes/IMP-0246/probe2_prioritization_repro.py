#!/usr/bin/env python3
"""Named probe 2: prioritization is a pure function of recorded inputs.

Independent of probe 1. Hidden ranking state (clock, PRNG, salted hash,
module-level weights) would fail one of the controls below.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from product_blueprints.engine import run_blueprint  # noqa: E402
from product_blueprints.hidden_state import scan_hidden_state  # noqa: E402
from product_blueprints.prioritize import RankingRefusal  # noqa: E402

PRIO_PY = REPO / "tools/product_blueprints/prioritize.py"
RECORDED = HERE / "fixtures" / "recorded-ranking.json"


def _dump(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _no_module_level_weights(path: Path) -> bool:
    """Refuse a hidden default-weights constant used when input omits weights."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id.upper().endswith("WEIGHTS"):
                    return False
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id.upper().endswith("WEIGHTS"):
                return False
    return True


def main() -> int:
    recorded = json.loads(RECORDED.read_text(encoding="utf-8"))
    run_a = run_blueprint("roadmap-prioritization", recorded)
    run_b = run_blueprint("roadmap-prioritization", recorded)
    shuffled = {
        "weights": dict(recorded["weights"]),
        "items": list(reversed(list(recorded["items"]))),
    }
    run_c = run_blueprint("roadmap-prioritization", shuffled)

    identical_ab = _dump(run_a["ranking"]) == _dump(run_b["ranking"])
    order_invariant = run_a["ranking_ids"] == run_c["ranking_ids"]
    ast_scan = scan_hidden_state(PRIO_PY)
    no_hidden_weights = _no_module_level_weights(PRIO_PY)

    missing_field = dict(recorded)
    missing_field["items"] = [
        {"id": "x", "reach": 1, "impact": 1, "confidence": 50}
    ]
    refused_incomplete = False
    try:
        run_blueprint("roadmap-prioritization", missing_field)
    except RankingRefusal as exc:
        refused_incomplete = exc.code == "ranking-item-incomplete"

    no_weights = {"items": list(recorded["items"])}
    refused_weights = False
    try:
        run_blueprint("roadmap-prioritization", no_weights)
    except RankingRefusal as exc:
        refused_weights = exc.code == "ranking-weights-missing"

    payload = {
        "probe": "probe2-prioritization-repro",
        "unit_id": "IMP-0246",
        "identical_two_runs": identical_ab,
        "input_order_invariant": order_invariant,
        "ranking_ids": run_a.get("ranking_ids"),
        "hidden_state_flag": run_a.get("hidden_state"),
        "ast_clean": ast_scan["clean"],
        "ast_scan": ast_scan,
        "no_module_level_weights": no_hidden_weights,
        "refused_incomplete_item": refused_incomplete,
        "refused_missing_weights": refused_weights,
        "arithmetic": run_a.get("arithmetic"),
        "pass": bool(
            identical_ab
            and order_invariant
            and ast_scan["clean"]
            and no_hidden_weights
            and refused_incomplete
            and refused_weights
            and run_a.get("hidden_state") is False
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:IMP-0246-probe2 prioritization not reproducible")
        return 1
    print(
        "SUCCESS:IMP-0246-probe2 ranking reproducible from recorded inputs"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
