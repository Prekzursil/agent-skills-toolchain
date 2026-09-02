"""Disagreeing / agreeing / double-count council-of-councils fixtures."""
from __future__ import annotations

from typing import Any

REL_A = "command-center/p2-wave/probes/CNF-0095/fixtures/complete-a.json"
REL_B = "command-center/p2-wave/probes/CNF-0095/fixtures/complete-b.json"
REL_F1 = "command-center/p2-wave/probes/CNF-0095/fixtures/complete-flat-1.json"
REL_F2 = "command-center/p2-wave/probes/CNF-0095/fixtures/complete-flat-2.json"
MISSING = "command-center/p2-wave/probes/CNF-0095/fixtures/does-not-exist.json"


def _member(sid: str, *, complete: bool, artifact: str, sentinel: str) -> dict[str, Any]:
    if complete:
        return {
            "id": sid,
            "source_id": sid,
            "state": "SUCCESS",
            "exit_code": 0,
            "artifact_path": artifact,
            "sentinel": sentinel,
        }
    return {
        "id": sid,
        "source_id": sid,
        "state": "BLOCKED",
        "exit_code": 0,
        "artifact_path": MISSING,
        "sentinel": "",
    }


def disagreeing_subcouncils() -> list[dict[str, Any]]:
    """One subcouncil COMPLETE, one BLOCKED — the required split."""
    return [
        {
            "id": "sub-A",
            "members": [_member("sub-A-m1", complete=True, artifact=REL_A, sentinel="SUCCESS:sub-A-member")],
        },
        {
            "id": "sub-B",
            "members": [_member("sub-B-m1", complete=False, artifact=MISSING, sentinel="")],
        },
    ]


def agreeing_subcouncils() -> list[dict[str, Any]]:
    return [
        {
            "id": "sub-A",
            "members": [_member("sub-A-m1", complete=True, artifact=REL_A, sentinel="SUCCESS:sub-A-member")],
        },
        {
            "id": "sub-B",
            "members": [_member("sub-B-m1", complete=True, artifact=REL_B, sentinel="SUCCESS:sub-B-member")],
        },
    ]


def double_counted_subcouncils() -> list[dict[str, Any]]:
    """Same COMPLETE subcouncil listed twice — tally must catch it."""
    a = {
        "id": "sub-A",
        "members": [_member("sub-A-m1", complete=True, artifact=REL_A, sentinel="SUCCESS:sub-A-member")],
    }
    return [a, dict(a)]


def flat_complete_receipts() -> tuple[list[dict[str, Any]], list[str]]:
    recs = [
        _member("flat-1", complete=True, artifact=REL_F1, sentinel="SUCCESS:flat-member-1"),
        _member("flat-2", complete=True, artifact=REL_F2, sentinel="SUCCESS:flat-member-2"),
    ]
    return recs, ["flat-1", "flat-2"]
