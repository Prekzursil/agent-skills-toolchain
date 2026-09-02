#!/usr/bin/env python3
"""Probe 2: both-states pair + independent census/oracle reviewer.

Mechanically different from probe 1: does not reuse probe 1's injection
object. Re-runs the pair, asserts the present-artifact state is SUCCESS
at condition 2, asserts the AST census detector fires on a planted
short-circuit, and (when present) asks IMP-0241 oracle.judge about c2.
A classifier that treats exit 0 as SUCCESS without an artifact must FAIL.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

UNIT = "TST-0004"
SRC = HERE / "harness.py"


def classify_never_success_on_missing_in_source() -> list[str]:
    """AST: classify() must not return SUCCESS before the existence check."""
    source = SRC.read_text(encoding="utf-8")
    tree = ast.parse(source)
    classify_fn = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "classify":
            classify_fn = node
            break
    if classify_fn is None:
        return ["classify() missing"]
    problems: list[str] = []
    exists_checked = False
    for node in classify_fn.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "exists":
                    exists_checked = True
        if isinstance(node, ast.Return):
            text = ast.get_source_segment(source, node) or ""
            if "SUCCESS" in text and not exists_checked:
                problems.append("classify returns SUCCESS before exists is bound")
    saw_missing_branch = False
    for node in ast.walk(classify_fn):
        if isinstance(node, ast.If):
            seg = ast.get_source_segment(source, node.test) or ""
            if "exists" in seg and "not" in seg:
                saw_missing_branch = True
                for inner in ast.walk(node):
                    if isinstance(inner, ast.Return):
                        ret = ast.get_source_segment(source, inner) or ""
                        if (
                            '"verdict": "SUCCESS"' in ret
                            or "'verdict': 'SUCCESS'" in ret
                        ):
                            problems.append(
                                "missing-artifact branch returns SUCCESS"
                            )
    if not saw_missing_branch:
        problems.append("classify has no `if not exists` missing-artifact branch")
    return problems


def main() -> int:
    pair = H.run_injection_pair()
    census = H.run_census()
    nc = H.negative_control_rejects_rc0_short_circuit()
    oracle = H.independent_oracle_c2(
        Path(pair["missing"]["classification"]["artifact_path"]),
        Path(pair["present"]["classification"]["artifact_path"]),
    )
    ast_problems = classify_never_success_on_missing_in_source()
    pres = pair["present"]["classification"]
    miss = pair["missing"]["classification"]
    print(
        json.dumps(
            {
                "probe": "probe2-both-states",
                "unit_id": UNIT,
                "both_states_pair": pair["both_states_pair"],
                "present_verdict": pres["verdict"],
                "missing_verdict": miss["verdict"],
                "missing_failing_condition_id": miss["failing_condition_id"],
                "planted_fired": census["planted_control"][
                    "fired_on_known_short_circuit"
                ],
                "short_circuit_count": census["short_circuit_count"],
                "negative_control": nc,
                "oracle": {
                    "available": oracle.get("available"),
                    "missing_c2_false_and_not_complete": oracle.get(
                        "missing_c2_false_and_not_complete"
                    ),
                    "present_c2_true": oracle.get("present_c2_true"),
                    "missing_result": oracle.get("missing_result"),
                },
                "ast_problems": ast_problems,
            },
            sort_keys=True,
            default=str,
        )
    )
    fail = False
    if not pair["test_exit0_with_valid_artifact_is_success"]:
        print("FAILED:TST-0004-probe2 present-artifact state was not SUCCESS")
        fail = True
    if not pair["test_exit0_no_artifact_is_failed"]:
        print("FAILED:TST-0004-probe2 missing-artifact state was not FAILED at c2")
        fail = True
    if pres["verdict"] != "SUCCESS" or miss["verdict"] != "FAILED":
        print("FAILED:TST-0004-probe2 both-states pair collapsed")
        fail = True
    if miss["failing_condition_id"] != 2:
        print("FAILED:TST-0004-probe2 missing state not condition 2")
        fail = True
    if not nc["fired_on_bad_classifier"]:
        print("FAILED:TST-0004-probe2 rc0-as-success classifier was not rejected")
        fail = True
    if not census["planted_control"]["fired_on_known_short_circuit"]:
        print("FAILED:TST-0004-probe2 planted short-circuit not detected")
        fail = True
    if ast_problems:
        print(f"FAILED:TST-0004-probe2 classify AST {ast_problems}")
        fail = True
    if oracle.get("available") and not oracle.get(
        "missing_c2_false_and_not_complete"
    ):
        print("FAILED:TST-0004-probe2 independent oracle did not fail c2 on missing")
        fail = True
    if fail:
        print("FAILED:TST-0004-probe2 both-states + independent reviewer")
        return 1
    print(
        f"both_states={pair['both_states_pair']} "
        f"present={pres['verdict']} missing={miss['verdict']} "
        f"c2={miss['failing_condition_id']} "
        f"oracle={oracle.get('available')} "
        f"short_circuits={census['short_circuit_count']}"
    )
    print("SUCCESS:TST-0004-probe2 both-states pair and independent census/oracle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
