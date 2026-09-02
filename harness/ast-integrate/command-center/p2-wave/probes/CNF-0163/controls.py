"""Planted both-states controls for CNF-0163.

Four required tests plus an explicit drift case so line-move is not merged
into missing-at-revision.
"""
from __future__ import annotations

from typing import Any

from fixture import Fixture, worktree_cr_construct
from resolve import (
    VERDICT_DRIFTED,
    VERDICT_MISSING,
    VERDICT_RESOLVED,
    VERDICT_WORKTREE,
    classify,
)


def run_controls(fix: Fixture) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def one(
        cid: str,
        expected: str,
        path: str,
        line: int,
        construct: str,
        revision: str,
        description: str,
    ) -> None:
        got = classify(
            fix.repo,
            path=path,
            line=line,
            construct=construct,
            revision=revision,
        )
        rows.append(
            {
                "id": cid,
                "description": description,
                "expected": expected,
                "verdict": got.verdict,
                "pass": got.verdict == expected,
                "resolution": got.as_dict(),
            }
        )

    one(
        "known-present",
        VERDICT_RESOLVED,
        fix.evidence_rel,
        1,
        "ALPHA-CONSTRUCT",
        fix.rev_a,
        "Hand-verified anchor at rev-a evidence.txt:1 must resolve via cat-file.",
    )
    one(
        "known-broken-past-eof",
        VERDICT_MISSING,
        fix.evidence_rel,
        999,
        "PAST-EOF-SENTINEL",
        fix.rev_a,
        "Anchor past end-of-file at that revision must be caught.",
    )
    one(
        "worktree-only",
        VERDICT_WORKTREE,
        fix.evidence_rel,
        5,
        "WORKTREE-ONLY-CONSTRUCT",
        fix.rev_b,
        "Anchor valid only in the dirty worktree must be flagged worktree-only.",
    )
    one(
        "line-drift",
        VERDICT_DRIFTED,
        fix.evidence_rel,
        1,
        "ALPHA-CONSTRUCT",
        fix.rev_b,
        "After a header insert, citing the old line is drift, not a bad/missing merge.",
    )
    cr_construct = worktree_cr_construct(fix, 1)
    one(
        "eol-crlf-agnostic",
        VERDICT_RESOLVED,
        fix.eol_rel,
        1,
        cr_construct,
        fix.rev_b,
        "Construct taken from a CRLF worktree line must still resolve against the LF blob.",
    )
    return rows


def all_passed(rows: list[dict[str, Any]]) -> bool:
    return bool(rows) and all(r.get("pass") for r in rows)
