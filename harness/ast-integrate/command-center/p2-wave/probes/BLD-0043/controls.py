#!/usr/bin/env python3
"""The three catalog controls for BLD-0043, plus the ten-mapping body review."""
from __future__ import annotations

from typing import Any

from join import JoinResult, TestRec, join

DELETE_REQ = "REQ-FX-DEL"
COMMENT_REQ = "REQ-FX-COMMENT"
REVIEW_REQS = tuple(f"REQ-FX-{i:02d}" for i in range(1, 11))


def control_delete_moves_untested(
    reqs: list, tests: list[TestRec]
) -> dict[str, Any]:
    before = join(reqs, tests)
    mapped_before = {
        m.test_id
        for m in before.mappings
        if m.requirement_id == DELETE_REQ
    }
    if not mapped_before:
        return {
            "id": "delete-known-test-moves-untested",
            "pass": False,
            "detail": f"{DELETE_REQ} was not mapped before deletion",
        }
    remaining = [t for t in tests if t.id not in mapped_before]
    after = join(reqs, remaining)
    untested_after = {u["id"] for u in after.untested}
    still_mapped = {
        m.test_id
        for m in after.mappings
        if m.requirement_id == DELETE_REQ
    }
    ok = DELETE_REQ in untested_after and not still_mapped
    return {
        "id": "delete-known-test-moves-untested",
        "pass": ok,
        "detail": (
            f"removed {sorted(mapped_before)}; "
            f"{DELETE_REQ} untested_after={DELETE_REQ in untested_after} "
            f"still_mapped={sorted(still_mapped)}"
        ),
        "removed_tests": sorted(mapped_before),
    }


def control_comment_only_unmapped(
    reqs: list, tests: list[TestRec]
) -> dict[str, Any]:
    result = join(reqs, tests)
    comment_hits = [
        c
        for c in result.comment_only
        if c["requirement_id"] == COMMENT_REQ
    ]
    mapped = [
        m
        for m in result.mappings
        if m.requirement_id == COMMENT_REQ
    ]
    untested_ids = {u["id"] for u in result.untested}
    ok = bool(comment_hits) and not mapped and COMMENT_REQ in untested_ids
    return {
        "id": "comment-only-reported-unmapped",
        "pass": ok,
        "detail": (
            f"comment_only_hits={len(comment_hits)} mapped={len(mapped)} "
            f"req_untested={COMMENT_REQ in untested_ids}"
        ),
        "comment_only": comment_hits,
    }


def control_orphans_classified(result: JoinResult) -> dict[str, Any]:
    bad = [
        o
        for o in result.orphans
        if o.get("classification") not in {"promote", "retire"}
    ]
    classes = {o["classification"] for o in result.orphans}
    has_promote = any(o["classification"] == "promote" for o in result.orphans)
    has_retire = any(o["classification"] == "retire" for o in result.orphans)
    ok = not bad and has_promote and has_retire
    return {
        "id": "orphan-exactly-one-of-promote-retire",
        "pass": ok,
        "detail": (
            f"orphans={len(result.orphans)} unclassified={len(bad)} "
            f"classes={sorted(classes)} promote={has_promote} retire={has_retire}"
        ),
    }


def review_ten_mappings(result: JoinResult) -> dict[str, Any]:
    tests_by_id = {t.id: t for t in result.tests}
    reqs_by_id = {r.id: r for r in result.requirements}
    checked: list[dict[str, Any]] = []
    for rid in REVIEW_REQS:
        mapped = [m for m in result.mappings if m.requirement_id == rid]
        if not mapped:
            checked.append(
                {
                    "requirement_id": rid,
                    "test_id": "",
                    "channel": "",
                    "body_asserts_requirement": False,
                    "verdict": "ID-ONLY",
                    "missing_tokens": ["no-mapping"],
                }
            )
            continue
        # Prefer test-id channel, then marker, then registry.
        order = {"test-id": 0, "marker": 1, "registry-entry": 2}
        mapped.sort(key=lambda m: order.get(m.channel, 9))
        m = mapped[0]
        test = tests_by_id[m.test_id]
        req = reqs_by_id[rid]
        body = test.source.lower()
        missing = [tok for tok in req.tokens if tok.lower() not in body]
        # The REQ id in the name/marker is not enough: tokens must appear
        # in the assertion body.
        confirms = not missing
        checked.append(
            {
                "requirement_id": rid,
                "test_id": m.test_id,
                "channel": m.channel,
                "body_asserts_requirement": confirms,
                "verdict": "CONFIRMS-REQUIREMENT" if confirms else "ID-ONLY",
                "missing_tokens": missing,
            }
        )
    id_only = [c for c in checked if c["verdict"] != "CONFIRMS-REQUIREMENT"]
    ok = len(checked) >= 10 and not id_only
    return {
        "reviewer_id": "BLD-0043-body-read-not-id-match",
        "verdict": "PASS" if ok else "FAIL",
        "independent": True,
        "checked_count": len(checked),
        "mappings_checked": checked,
        "id_only": id_only,
    }


def run_fixture_controls(reqs: list, tests: list[TestRec]) -> dict[str, Any]:
    result = join(reqs, tests)
    c1 = control_delete_moves_untested(reqs, tests)
    c2 = control_comment_only_unmapped(reqs, tests)
    c3 = control_orphans_classified(result)
    reviewer = review_ten_mappings(result)
    return {
        "result": result,
        "controls": [c1, c2, c3],
        "reviewer": reviewer,
        "all_pass": all(c["pass"] for c in (c1, c2, c3))
        and reviewer["verdict"] == "PASS",
    }
