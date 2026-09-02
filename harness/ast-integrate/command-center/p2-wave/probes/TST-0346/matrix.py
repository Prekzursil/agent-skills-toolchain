"""Requirement × test traceability by set operations over declared links.

The matrix is (requirement_ids × test_ids) joined by an explicit link set.
Empty directions are set differences, never a prose scan and never a count
without the id lists.

    untested_requirements = requirements − {r | (r, t) ∈ valid_links}
    untraced_tests        = tests − {t | (r, t) ∈ valid_links}

A link is valid only when both endpoints exist in the declared inventories.
Comments, docstrings, and counts-only summaries are not inputs.
"""
from __future__ import annotations

from typing import Iterable


def id_set(values: Iterable[object]) -> set[str]:
    out: set[str] = set()
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            out.add(text)
    return out


def normalize_links(links: Iterable[object]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for item in links or []:
        req = test = ""
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            req = str(item[0]).strip()
            test = str(item[1]).strip()
        elif isinstance(item, dict):
            req = str(
                item.get("requirement_id")
                or item.get("req_id")
                or item.get("requirement")
                or ""
            ).strip()
            test = str(item.get("test_id") or item.get("test") or "").strip()
        if req and test:
            pairs.append((req, test))
    return pairs


def compute_matrix(
    requirements: Iterable[object],
    tests: Iterable[object],
    links: Iterable[object],
) -> dict:
    reqs = id_set(requirements)
    tests_s = id_set(tests)
    declared = normalize_links(links)

    invalid: list[dict] = []
    valid: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for req, test in declared:
        missing_req = req not in reqs
        missing_test = test not in tests_s
        if missing_req or missing_test:
            invalid.append(
                {
                    "missing_requirement": missing_req,
                    "missing_test": missing_test,
                    "requirement_id": req,
                    "test_id": test,
                }
            )
            continue
        if (req, test) not in seen:
            seen.add((req, test))
            valid.append((req, test))

    covered_reqs = {req for req, _test in valid}
    traced_tests = {test for _req, test in valid}
    untested = sorted(reqs - covered_reqs)
    untraced = sorted(tests_s - traced_tests)

    cells = {req: [] for req in sorted(reqs)}
    reverse = {test: [] for test in sorted(tests_s)}
    for req, test in valid:
        cells[req].append(test)
        reverse[test].append(req)
    for req in cells:
        cells[req] = sorted(set(cells[req]))
    for test in reverse:
        reverse[test] = sorted(set(reverse[test]))

    return {
        "counts": {
            "invalid_links": len(invalid),
            "requirements": len(reqs),
            "tests": len(tests_s),
            "untested_requirements": len(untested),
            "untraced_tests": len(untraced),
            "valid_links": len(valid),
        },
        "counts_are_not_the_deliverable": True,
        "invalid_links": invalid,
        "matrix": cells,
        "method": "set-difference-over-declared-links",
        "prose_not_consulted": True,
        "requirement_ids": sorted(reqs),
        "test_ids": sorted(tests_s),
        "tests_to_requirements": reverse,
        "untested_requirements": untested,
        "untraced_tests": untraced,
        "valid_links": [
            {"requirement_id": req, "test_id": test} for req, test in valid
        ],
    }


def lists_are_the_deliverable(result: dict) -> bool:
    return (
        isinstance(result, dict)
        and isinstance(result.get("untested_requirements"), list)
        and isinstance(result.get("untraced_tests"), list)
        and isinstance(result.get("invalid_links"), list)
        and result.get("counts_are_not_the_deliverable") is True
        and result.get("method") == "set-difference-over-declared-links"
        and result.get("prose_not_consulted") is True
    )
