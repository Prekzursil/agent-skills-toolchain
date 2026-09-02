#!/usr/bin/env python3
"""Probe 1: matrix is set operations; both empty directions listed in full; both states."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from matrix import compute_matrix, lists_are_the_deliverable  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0346-probe1 {msg}")
    return 1


def load_fix(name: str) -> dict:
    return json.loads((HERE / "fixtures" / name).read_text(encoding="utf-8"))


def main() -> int:
    partial = load_fix("partial_links.json")
    full = load_fix("fully_linked.json")

    state_partial = compute_matrix(
        partial["requirements"], partial["tests"], partial["links"]
    )
    state_full = compute_matrix(full["requirements"], full["tests"], full["links"])

    if not lists_are_the_deliverable(state_partial):
        return fail("partial result is counts-only or missing id lists")
    if not lists_are_the_deliverable(state_full):
        return fail("fully-linked result is counts-only or missing id lists")

    want_untested = ["REQ-UNTESTED-A", "REQ-UNTESTED-B"]
    want_untraced = ["TST-ORPHAN-A", "TST-ORPHAN-B"]
    got_untested = state_partial["untested_requirements"]
    got_untraced = state_partial["untraced_tests"]
    if got_untested != want_untested:
        return fail(f"partial untested {got_untested} != {want_untested}")
    if got_untraced != want_untraced:
        return fail(f"partial untraced {got_untraced} != {want_untraced}")
    if state_partial["matrix"].get("REQ-BOUND-1") != ["TST-BOUND-1"]:
        return fail("partial matrix cell REQ-BOUND-1")
    if state_partial["counts"]["untested_requirements"] != len(want_untested):
        return fail("partial count drifted from the listed ids")
    if state_partial["counts"]["untraced_tests"] != len(want_untraced):
        return fail("partial untraced count drifted from the listed ids")

    if state_full["untested_requirements"] != []:
        return fail(f"fully-linked untested not empty {state_full['untested_requirements']}")
    if state_full["untraced_tests"] != []:
        return fail(f"fully-linked untraced not empty {state_full['untraced_tests']}")
    if state_full["invalid_links"]:
        return fail(f"fully-linked invalid {state_full['invalid_links']}")
    for req, test in (
        ("REQ-BOUND-1", "TST-BOUND-1"),
        ("REQ-BOUND-2", "TST-BOUND-2"),
        ("REQ-BOUND-3", "TST-BOUND-3"),
    ):
        if state_full["matrix"].get(req) != [test]:
            return fail(f"fully-linked cell {req}")

    # Adding one declared link must move REQ-UNTESTED-A off the untested list.
    extra = list(partial["links"]) + [["REQ-UNTESTED-A", "TST-ORPHAN-A"]]
    after = compute_matrix(partial["requirements"], partial["tests"], extra)
    if "REQ-UNTESTED-A" in after["untested_requirements"]:
        return fail("added link did not remove REQ-UNTESTED-A from untested")
    if "REQ-UNTESTED-B" not in after["untested_requirements"]:
        return fail("unrelated untested id disappeared")
    if "TST-ORPHAN-A" in after["untraced_tests"]:
        return fail("added link did not remove TST-ORPHAN-A from untraced")

    report = {
        "pass": True,
        "probe": "probe1-set-ops-both-states",
        "unit_id": "TST-0346",
        "method": state_partial["method"],
        "partial": {
            "untested_requirements": got_untested,
            "untraced_tests": got_untraced,
            "valid_links": state_partial["valid_links"],
        },
        "fully_linked": {
            "untested_requirements": state_full["untested_requirements"],
            "untraced_tests": state_full["untraced_tests"],
        },
        "link_addition_moved_ids": True,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(
        "SUCCESS:TST-0346-probe1 set-ops matrix; both empty directions listed "
        "in full; both states discriminate"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
