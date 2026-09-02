#!/usr/bin/env python3
"""Probe 1: six spec-named expressions parse, evaluate, and both evaluators agree.

Both-states: each expression FIRES on a state where it is true and stays SILENT
on a state where it is false. An expression silent in both states measures nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from grammar import (  # noqa: E402
    SPEC_EXPRESSIONS,
    evaluate_pair,
    spec_conformance,
    synthetic_states,
)

OUT = REPO / "command-center/wfa/WFA-0039-extract-stopping-rules.json"


def _true_false_states() -> dict[str, tuple[dict, dict]]:
    """Hand-built fire/silent states per spec expression, independent of the 20-vector mix."""
    fire = {
        "unique_ideas": 120,
        "completeness_score": 0.95,
        "consensus": 0.99,
        "no_new_objection_rounds": 3,
        "unanimity": True,
        "max_rounds": 12,
        "quality_gate": "PASS",
        "unresolved_load_bearing_counterexample": 0,
        "evidence_saturation": True,
        "time_minutes": 200,
        "proof_of_impossibility": True,
    }
    silent = {
        "unique_ideas": 10,
        "completeness_score": 0.1,
        "consensus": 0.1,
        "no_new_objection_rounds": 0,
        "unanimity": False,
        "max_rounds": 3,
        "quality_gate": "FAIL",
        "unresolved_load_bearing_counterexample": 4,
        "evidence_saturation": False,
        "time_minutes": 12,
        "proof_of_impossibility": False,
    }
    return {sid: (fire, silent) for sid, _line, _src in SPEC_EXPRESSIONS}


def main() -> int:
    states = synthetic_states()
    conf = spec_conformance(states)
    if len(conf) != 6:
        print("FAILED:WFA-0039-probe1 expected 6 spec expressions")
        return 1
    both = _true_false_states()
    lines = []
    for row in conf:
        sid = row["id"]
        src = row["source"]
        if not row["parsed"]:
            print(f"FAILED:WFA-0039-probe1 parse {sid} {row['errors']}")
            return 1
        if row["disagreements"] != 0:
            print(f"FAILED:WFA-0039-probe1 disagreement {sid}")
            return 1
        if row["degenerate"]:
            print(f"FAILED:WFA-0039-probe1 spec degenerate {sid} {row['degenerate']}")
            return 1
        if row["n_true"] == 0 or row["n_false"] == 0:
            print(
                f"FAILED:WFA-0039-probe1 spec not both-states on 20-vector "
                f"{sid} n_true={row['n_true']} n_false={row['n_false']}"
            )
            return 1
        fire, silent = both[sid]
        pf = evaluate_pair(src, fire)
        ps = evaluate_pair(src, silent)
        if not (pf["normalized"] and pf["direct"] and pf["agree"]):
            print(f"FAILED:WFA-0039-probe1 FIRE silent-or-disagree {sid} {pf}")
            return 1
        if ps["normalized"] or ps["direct"] or not ps["agree"]:
            print(f"FAILED:WFA-0039-probe1 SILENT fired-or-disagree {sid} {ps}")
            return 1
        lines.append(
            f"{sid} line={row['spec_line']} parsed=True fire=True silent=False "
            f"n_true={row['n_true']} n_false={row['n_false']} disagreements=0"
        )

    if not OUT.is_file():
        print("FAILED:WFA-0039-probe1 artifact missing")
        return 1
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    art = {s["id"]: s for s in doc.get("spec_named_expressions") or []}
    for sid, _line, _src in SPEC_EXPRESSIONS:
        if sid not in art or not art[sid].get("parsed"):
            print(f"FAILED:WFA-0039-probe1 artifact missing {sid}")
            return 1
    if "SUCCESS:WFA-0039" not in json.dumps(doc):
        print("FAILED:WFA-0039-probe1 sentinel-absent")
        return 1

    print("six_spec=6 parsed=6 both_states=True two_evaluators_agree=True")
    for line in lines:
        print(line)
    print("SUCCESS:WFA-0039-probe1 six spec-named expressions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
