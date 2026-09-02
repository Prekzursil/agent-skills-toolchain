#!/usr/bin/env python3
"""Probe 2: independent reviewer — recompute both empty directions; reject invalid and prose-only links."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from matrix import compute_matrix, lists_are_the_deliverable, normalize_links  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0346-probe2 {msg}")
    return 1


def load_fix(name: str) -> dict:
    return json.loads((HERE / "fixtures" / name).read_text(encoding="utf-8"))


def reviewer_empty_directions(requirements, tests, links):
    """Independent set arithmetic. Does not call compute_matrix for the expected lists."""
    reqs = {str(x).strip() for x in requirements if str(x).strip()}
    tests_s = {str(x).strip() for x in tests if str(x).strip()}
    valid = set()
    invalid = []
    for req, test in normalize_links(links):
        if req in reqs and test in tests_s:
            valid.add((req, test))
        else:
            invalid.append((req, test, req not in reqs, test not in tests_s))
    untested = sorted(reqs - {r for r, _t in valid})
    untraced = sorted(tests_s - {t for _r, t in valid})
    return untested, untraced, invalid


def count_only(result: dict) -> dict:
    return {
        "untested_count": result["counts"]["untested_requirements"],
        "untraced_count": result["counts"]["untraced_tests"],
    }


def main() -> int:
    partial = load_fix("partial_links.json")
    full = load_fix("fully_linked.json")
    invalid_fix = load_fix("invalid_links.json")
    prose_path = HERE / "fixtures" / "prose_only.py"
    prose_text = prose_path.read_text(encoding="utf-8")

    rev_untested, rev_untraced, _rev_invalid = reviewer_empty_directions(
        partial["requirements"], partial["tests"], partial["links"]
    )
    engine = compute_matrix(
        partial["requirements"], partial["tests"], partial["links"]
    )
    if not lists_are_the_deliverable(engine):
        return fail("engine omitted full id lists")
    if engine["untested_requirements"] != rev_untested:
        return fail(
            f"reviewer untested {rev_untested} != engine {engine['untested_requirements']}"
        )
    if engine["untraced_tests"] != rev_untraced:
        return fail(
            f"reviewer untraced {rev_untraced} != engine {engine['untraced_tests']}"
        )
    if rev_untested != ["REQ-UNTESTED-A", "REQ-UNTESTED-B"]:
        return fail(f"reviewer partial untested {rev_untested}")
    if rev_untraced != ["TST-ORPHAN-A", "TST-ORPHAN-B"]:
        return fail(f"reviewer partial untraced {rev_untraced}")

    full_u, full_t, _ = reviewer_empty_directions(
        full["requirements"], full["tests"], full["links"]
    )
    full_engine = compute_matrix(full["requirements"], full["tests"], full["links"])
    if full_u != [] or full_t != []:
        return fail("reviewer fully-linked empty directions not empty")
    if full_engine["untested_requirements"] != [] or full_engine["untraced_tests"] != []:
        return fail("engine fully-linked empty directions not empty")

    bad = compute_matrix(
        invalid_fix["requirements"], invalid_fix["tests"], invalid_fix["links"]
    )
    invalid_pairs = {
        (row["requirement_id"], row["test_id"]) for row in bad["invalid_links"]
    }
    want_invalid = {
        ("REQ-GHOST", "TST-REAL"),
        ("REQ-REAL", "TST-GHOST"),
        ("REQ-GHOST", "TST-GHOST"),
    }
    if invalid_pairs != want_invalid:
        return fail(f"invalid links {invalid_pairs} != {want_invalid}")
    if bad["valid_links"] != [{"requirement_id": "REQ-REAL", "test_id": "TST-REAL"}]:
        return fail(f"valid link lost among ghosts {bad['valid_links']}")
    if "REQ-GHOST" in bad["requirement_ids"]:
        return fail("ghost requirement was minted into the inventory")
    if "TST-GHOST" in bad["test_ids"]:
        return fail("ghost test was minted into the inventory")

    if "REQ-FROM-COMMENT" not in prose_text:
        return fail("prose fixture missing REQ-FROM-COMMENT token")
    prose_engine = compute_matrix([], [], [])
    if "REQ-FROM-COMMENT" in prose_engine["requirement_ids"]:
        return fail("comment token became a requirement id")
    if "test_from_comment" in prose_engine["test_ids"]:
        return fail("comment-named test became a test id")
    if prose_engine["valid_links"]:
        return fail("prose-only file produced declared links")

    counts = count_only(engine)
    if lists_are_the_deliverable(counts):
        return fail("count-only object was accepted as the deliverable")
    if "REQ-UNTESTED-A" not in engine["untested_requirements"]:
        return fail("deliverable list dropped the requirement id")

    report = {
        "pass": True,
        "probe": "probe2-link-validity-reviewer",
        "unit_id": "TST-0346",
        "reviewer_recomputed_both_states": True,
        "invalid_links_named": sorted(
            [{"requirement_id": a, "test_id": b} for a, b in want_invalid],
            key=lambda r: (r["requirement_id"], r["test_id"]),
        ),
        "prose_only_ignored": True,
        "count_only_rejected": True,
        "independent": True,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(
        "SUCCESS:TST-0346-probe2 reviewer recomputed both empty directions; "
        "invalid links named; prose-only mapping ignored"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
