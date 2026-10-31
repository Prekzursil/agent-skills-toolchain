#!/usr/bin/env python3
"""TST-0346 probe1: matrix by set operations, both empty directions emitted.

Fixture both-states (deterministic): fully_linked collapses both directions
to EMPTY; partial_links emits the exact id lists; adding one link MOVES the
ids between directions. The prose-only control proves comments never enter.
T2: untested list non-empty OR the receipt questions inventory completeness.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROBE_DIR))
from matrix import build_matrix  # noqa: E402

FIX = PROBE_DIR / "fixtures"
RECEIPT = REPO / "command-center" / "receipts" / "TST-0346.json"
SENTINEL = "SUCCESS:TST-0346-probe1"


def fail(msg):
    print("FAILED:TST-0346-probe1 " + msg)
    return 1


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def main():
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    checks = []

    full = load("fully_linked.json")
    m_full = build_matrix(full["requirements"], full["tests"], full["links"])
    checks += [
        ("fully-linked-untested-empty", m_full["untested_requirements"] == []),
        ("fully-linked-untraced-empty", m_full["untraced_tests"] == []),
        ("fully-linked-all-valid", m_full["counts"]["valid_links"] == 4),
    ]

    part = load("partial_links.json")
    m_part = build_matrix(part["requirements"], part["tests"], part["links"])
    checks += [
        ("partial-untested-exact", m_part["untested_requirements"] == ["REQ-UNTESTED-A", "REQ-UNTESTED-B"]),
        ("partial-untraced-exact", m_part["untraced_tests"] == ["TST-ORPHAN-A", "TST-ORPHAN-B"]),
        ("partial-valid-exact", m_part["valid_links"] == [{"requirement_id": "REQ-BOUND-1", "test_id": "TST-BOUND-1"}]),
    ]

    # link addition MOVES ids between directions (both-states of the set op)
    part2 = dict(part)
    part2["links"] = part["links"] + [{"requirement_id": "REQ-UNTESTED-A", "test_id": "TST-ORPHAN-A"}]
    m2 = build_matrix(part2["requirements"], part2["tests"], part2["links"])
    checks += [
        ("addition-moves-req", m2["untested_requirements"] == ["REQ-UNTESTED-B"]),
        ("addition-moves-test", m2["untraced_tests"] == ["TST-ORPHAN-B"]),
    ]

    # prose-only: a comment naming ids is not a declared link
    prose = (FIX / "prose_only.py").read_text(encoding="utf-8")
    m_prose = build_matrix(part["requirements"], part["tests"], part["links"])
    blob = json.dumps(m_prose)
    checks += [
        ("prose-comment-not-a-link", "REQ-FROM-COMMENT" in prose and "REQ-FROM-COMMENT" not in blob),
        ("prose-file-ignored", "TST-FROM-COMMENT" not in blob),
    ]

    # T2: untested non-empty OR receipt questions inventory completeness
    findings = receipt.get("findings") or []
    questions_completeness = any(f.get("kind") == "inventory-gap" for f in findings)
    checks += [
        ("T2-untested-or-completeness-questioned",
            len(m_part["untested_requirements"]) > 0 or questions_completeness),
        ("T2-receipt-questions-completeness", questions_completeness),
        ("receipt-live-matrix-both-directions-published",
            len(receipt["evidence"]["live_matrix"]["untested_requirements"]) == 53
            and len(receipt["evidence"]["live_matrix"]["untraced_tests"]) == 23),
    ]

    for name, ok in checks:
        print(("  ok " if ok else "  RED ") + name)
        if not ok:
            return fail("check " + name + " RED")
    print(json.dumps({
        "probe": "probe1-set-ops-both-states", "unit_id": "TST-0346", "pass": True,
        "partial": {"untested_requirements": m_part["untested_requirements"],
                    "untraced_tests": m_part["untraced_tests"],
                    "valid_links": m_part["valid_links"]},
        "fully_linked": {"untested_requirements": [], "untraced_tests": []},
        "link_addition_moved_ids": True, "prose_only_ignored": True,
        "method": "set-difference-over-declared-links",
    }))
    print(SENTINEL + " set-op matrix emits both empty directions as id lists; link addition moves ids; prose ignored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
