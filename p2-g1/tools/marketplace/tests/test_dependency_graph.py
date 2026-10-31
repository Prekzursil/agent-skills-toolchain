#!/usr/bin/env python3
"""IMP-0082 unit tests for the publish-time dependency cycle detector."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from marketplace import cycle_cases as cases  # noqa: E402
from marketplace.cycle_ref import independent_report  # noqa: E402
from marketplace.dependency import (  # noqa: E402
    KIND_DEV,
    KIND_OPTIONAL,
    KIND_PEER,
    KIND_REQUIRED,
    DependencyCycleError,
    check_at_publish,
    cycle_matches,
    detect_cycles,
    graph_from_document,
    naive_recursive_walk,
)
from marketplace.index_linter import lint_index  # noqa: E402

SCHEMA = REPO / "tools/marketplace/schema/dependency.schema.json"
PASSED = 0
FAILED = 0


def _ok(name: str) -> None:
    global PASSED
    PASSED += 1
    print(f"PASS {name}")


def _fail(name: str, msg: str) -> None:
    global FAILED
    FAILED += 1
    print(f"FAIL {name} {msg}")


def test_self_cycle_exact_path() -> None:
    g = graph_from_document(cases.self_cycle())
    if cycle_matches(detect_cycles(g), cases.EXPECTED_SELF):
        _ok("test_self_cycle_exact_path")
    else:
        _fail("test_self_cycle_exact_path", str([list(c.path) for c in detect_cycles(g)]))


def test_two_node_cycle_exact_path() -> None:
    g = graph_from_document(cases.two_node_cycle())
    if cycle_matches(detect_cycles(g), cases.EXPECTED_TWO):
        _ok("test_two_node_cycle_exact_path")
    else:
        _fail("test_two_node_cycle_exact_path", str([list(c.path) for c in detect_cycles(g)]))


def test_long_cycle_exact_path() -> None:
    g = graph_from_document(cases.long_cycle())
    if cycle_matches(detect_cycles(g), cases.EXPECTED_LONG):
        _ok("test_long_cycle_exact_path")
    else:
        _fail("test_long_cycle_exact_path", str([list(c.path) for c in detect_cycles(g)]))


def test_diamond_negative_control_is_silent() -> None:
    g = graph_from_document(cases.diamond())
    if detect_cycles(g) == []:
        _ok("test_diamond_negative_control_is_silent")
    else:
        _fail("test_diamond_negative_control_is_silent", "diamond reported as cycle")


def test_publish_refuses_two_node_with_exact_path() -> None:
    g = graph_from_document(cases.two_node_cycle())
    try:
        check_at_publish(g)
        _fail("test_publish_refuses_two_node_with_exact_path", "not refused")
        return
    except DependencyCycleError as exc:
        if exc.stage == "publish" and "a -> b -> a" in str(exc):
            _ok("test_publish_refuses_two_node_with_exact_path")
        else:
            _fail("test_publish_refuses_two_node_with_exact_path", f"{exc.stage} {exc}")


def test_optional_and_peer_classified_distinctly() -> None:
    g = graph_from_document(cases.kinds_distinct())
    by = g.classify()
    ok = (
        by[KIND_REQUIRED] == [("consumer", "lib-req", "^2.0.0")]
        and by[KIND_OPTIONAL] == [("consumer", "lib-opt", "~1.4.0")]
        and by[KIND_PEER] == [("consumer", "lib-peer", ">=3.0.0 <4.0.0")]
        and by[KIND_DEV] == [("consumer", "lib-dev", "*")]
        and detect_cycles(g) == []
    )
    if ok:
        _ok("test_optional_and_peer_classified_distinctly")
    else:
        _fail("test_optional_and_peer_classified_distinctly", str(by))


def test_peer_only_mutual_is_not_an_install_cycle() -> None:
    g = graph_from_document(cases.peer_only_mutual())
    if detect_cycles(g) == [] and detect_cycles(g, kinds=(KIND_PEER,)) != []:
        _ok("test_peer_only_mutual_is_not_an_install_cycle")
    else:
        _fail("test_peer_only_mutual_is_not_an_install_cycle", "peer classified as install cycle")


def test_independent_library_agrees_on_existence_and_membership() -> None:
    g = graph_from_document(cases.two_node_cycle())
    report = independent_report(g.pair_list())
    ok = (
        report["graphlib"]["cyclic"] is True
        and set(report["members"]) == {"a", "b"}
        and report["internal_existence_agree"]
    )
    if ok:
        _ok("test_independent_library_agrees_on_existence_and_membership")
    else:
        _fail("test_independent_library_agrees_on_existence_and_membership", str(report))


def test_index_linter_emits_dependency_cycle_path() -> None:
    findings = lint_index(cases.two_node_cycle())
    texts = json.dumps(findings)
    if "a" in texts and "b" in texts and ("cycle" in texts.lower() or "dependency_cycle" in texts):
        _ok("test_index_linter_emits_dependency_cycle_path")
    else:
        _fail("test_index_linter_emits_dependency_cycle_path", texts[:400])


def test_naive_walker_recursion_error_control() -> None:
    g = graph_from_document(cases.two_node_cycle())
    old = sys.getrecursionlimit()
    fired = False
    try:
        sys.setrecursionlimit(64)
        try:
            naive_recursive_walk(g, "a")
        except RecursionError:
            fired = True
    finally:
        sys.setrecursionlimit(old)
    if fired:
        _ok("test_naive_walker_recursion_error_control")
    else:
        _fail("test_naive_walker_recursion_error_control", "no RecursionError")


def test_schema_file_exists_and_names_four_kinds() -> None:
    if not SCHEMA.is_file():
        _fail("test_schema_file_exists_and_names_four_kinds", "missing schema")
        return
    text = SCHEMA.read_text(encoding="utf-8")
    kinds = ("required", "optional", "peer", "dev")
    if all(k in text for k in kinds):
        _ok("test_schema_file_exists_and_names_four_kinds")
    else:
        _fail("test_schema_file_exists_and_names_four_kinds", "kinds missing")


def main() -> int:
    test_self_cycle_exact_path()
    test_two_node_cycle_exact_path()
    test_long_cycle_exact_path()
    test_diamond_negative_control_is_silent()
    test_publish_refuses_two_node_with_exact_path()
    test_optional_and_peer_classified_distinctly()
    test_peer_only_mutual_is_not_an_install_cycle()
    test_independent_library_agrees_on_existence_and_membership()
    test_index_linter_emits_dependency_cycle_path()
    test_naive_walker_recursion_error_control()
    test_schema_file_exists_and_names_four_kinds()
    print(f"SUCCESS:test_dependency_graph passed={PASSED}")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
