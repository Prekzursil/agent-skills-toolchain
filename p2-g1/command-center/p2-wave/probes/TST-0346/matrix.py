#!/usr/bin/env python3
"""TST-0346 requirement-to-test traceability matrix engine.

Pure set operations over DECLARED links - never prose. A link is valid only
when both endpoints exist in the inventories; ghost endpoints surface in
invalid_links and are never minted into the inventories.

  untested_requirements = requirements - {r | (r,t) in valid_links}
  untraced_tests        = tests       - {t | (r,t) in valid_links}
"""
from __future__ import annotations


class CountsOnlyMatrix(ValueError):
    """A counts-only object is rejected: the deliverable is the id lists."""


def build_matrix(requirements, tests, links):
    reqs = set(requirements)
    tset = set(tests)
    valid, invalid = [], []
    for link in links or []:
        r = link.get("requirement_id")
        t = link.get("test_id")
        if r in reqs and t in tset:
            valid.append({"requirement_id": r, "test_id": t})
        else:
            invalid.append({"requirement_id": r, "test_id": t})
    linked_reqs = {l["requirement_id"] for l in valid}
    linked_tests = {l["test_id"] for l in valid}
    matrix = {
        "requirement_ids": sorted(reqs),
        "test_ids": sorted(tset),
        "valid_links": sorted(valid, key=lambda x: (x["requirement_id"], x["test_id"])),
        "invalid_links": sorted(invalid, key=lambda x: (x["requirement_id"], x["test_id"])),
        "untested_requirements": sorted(reqs - linked_reqs),
        "untraced_tests": sorted(tset - linked_tests),
    }
    matrix["counts"] = {
        "requirements": len(reqs),
        "tests": len(tset),
        "valid_links": len(matrix["valid_links"]),
        "invalid_links": len(matrix["invalid_links"]),
        "untested_requirements": len(matrix["untested_requirements"]),
        "untraced_tests": len(matrix["untraced_tests"]),
    }
    assert_not_counts_only(matrix)
    return matrix


def assert_not_counts_only(obj):
    """The deliverable is requirement ids and test ids, never bare counts."""
    if not isinstance(obj, dict):
        raise CountsOnlyMatrix("matrix must be a dict")
    for key in ("requirement_ids", "test_ids", "untested_requirements", "untraced_tests"):
        if not isinstance(obj.get(key), list):
            raise CountsOnlyMatrix("matrix missing id list: " + key)
    if "counts" in obj and not obj["requirement_ids"] and obj["counts"].get("requirements"):
        raise CountsOnlyMatrix("counts claim requirements but no id list emitted")
