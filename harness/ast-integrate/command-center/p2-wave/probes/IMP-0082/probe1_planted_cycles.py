#!/usr/bin/env python3
"""Probe 1: planted-cycle exact sequences + diamond negative control.

Evidence signal (1): the primary detector reports the exact node sequence of
self-cycle, two-node cycle, and long cycle, and is silent on an acyclic
diamond. Cycle detection is a publish-time gate, not RecursionError at install.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace import cycle_cases as cases  # noqa: E402
from marketplace.dependency import (  # noqa: E402
    DependencyCycleError,
    check_at_publish,
    cycle_matches,
    detect_cycles,
    graph_from_document,
    install_order,
    naive_recursive_walk,
    publish_verdict,
)

TEST = REPO / "tools/marketplace/tests/test_dependency_graph.py"


def _paths(g) -> list[list[str]]:
    return [list(c.path) for c in detect_cycles(g)]


def main() -> int:
    proc = subprocess.run(
        [sys.executable, "-B", str(TEST)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    test_out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        print(test_out)
        print("FAILED:IMP-0082-probe1 unit tests")
        return 1

    self_g = graph_from_document(cases.self_cycle())
    two_g = graph_from_document(cases.two_node_cycle())
    long_g = graph_from_document(cases.long_cycle())
    diamond_g = graph_from_document(cases.diamond())

    self_found = detect_cycles(self_g)
    two_found = detect_cycles(two_g)
    long_found = detect_cycles(long_g)
    diamond_found = detect_cycles(diamond_g)

    if not cycle_matches(self_found, cases.EXPECTED_SELF):
        print("FAILED:IMP-0082-probe1 self-cycle sequence", _paths(self_g))
        return 1
    if not cycle_matches(two_found, cases.EXPECTED_TWO):
        print("FAILED:IMP-0082-probe1 two-node sequence", _paths(two_g))
        return 1
    if not cycle_matches(long_found, cases.EXPECTED_LONG):
        print("FAILED:IMP-0082-probe1 long-cycle sequence", _paths(long_g))
        return 1
    if diamond_found:
        print("FAILED:IMP-0082-probe1 NEGATIVE CONTROL diamond reported as cycle", _paths(diamond_g))
        return 1

    publish_ok = check_at_publish(diamond_g)
    if not publish_ok.get("ok") or publish_ok.get("stage") != "publish":
        print("FAILED:IMP-0082-probe1 diamond publish gate", publish_ok)
        return 1

    try:
        check_at_publish(two_g)
        print("FAILED:IMP-0082-probe1 two-node cycle was not refused at publish")
        return 1
    except DependencyCycleError as exc:
        if exc.stage != "publish" or "a -> b -> a" not in str(exc):
            print("FAILED:IMP-0082-probe1 cycle error shape", exc.stage, exc)
            return 1

    try:
        install_order(two_g)
        print("FAILED:IMP-0082-probe1 install_order accepted a cycle")
        return 1
    except DependencyCycleError:
        pass

    recursion_fired = False
    old = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(64)
        try:
            naive_recursive_walk(two_g, "a")
        except RecursionError:
            recursion_fired = True
    finally:
        sys.setrecursionlimit(old)
    if not recursion_fired:
        print("FAILED:IMP-0082-probe1 naive walker did not RecursionError (control is dead)")
        return 1

    report = {
        "probe": "probe1-planted-cycles",
        "unit_id": "IMP-0082",
        "stage": "publish",
        "self_cycle": {"path": _paths(self_g), "matches_expected": True},
        "two_node_cycle": {"path": _paths(two_g), "matches_expected": True},
        "long_cycle": {"path": _paths(long_g), "matches_expected": True},
        "diamond_negative_control": {
            "cycles": _paths(diamond_g),
            "silent": True,
            "publish_ok": True,
        },
        "publish_refuses_two_node": True,
        "naive_walker_recursion_error": True,
        "detector_is_not_recursion_error": True,
        "unit_tests_ok": True,
        "publish_verdict_two_node": publish_verdict(two_g),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print("SUCCESS:IMP-0082-probe1 planted sequences plus diamond negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
