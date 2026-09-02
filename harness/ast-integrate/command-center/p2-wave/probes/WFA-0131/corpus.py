#!/usr/bin/env python3
"""Matched-case fixture used because WFA-0129's corpus is absent on disk.

Visible slice is what the naive WFA-0130 predicate scores. Held-out slice is
the first counter-control (capability that memorization cannot buy).
"""
from __future__ import annotations

from typing import Any

from registry import REGISTRY

REQUIRED_CAPABILITIES: tuple[str, ...] = tuple(REGISTRY["required_capabilities"])
OUTPUT_FIELDS: tuple[str, ...] = tuple(REGISTRY["output_fields"])

_ANSWERS = {
    "parse-input": "parsed-ok",
    "branch-policy": "branch-taken",
    "recover-fault": "fault-cleared",
    "emit-report": "report-ready",
}

_VISIBLE_COUNTS = {
    "parse-input": 4,
    "branch-policy": 4,
    "recover-fault": 4,
}
_HELDOUT_COUNTS = {
    "parse-input": 2,
    "branch-policy": 2,
    "recover-fault": 2,
    "emit-report": 2,
}


def _slug(cap: str) -> str:
    return {
        "parse-input": "a",
        "branch-policy": "b",
        "recover-fault": "c",
        "emit-report": "d",
    }[cap]


def build_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for cap, n in _VISIBLE_COUNTS.items():
        for i in range(1, n + 1):
            cid = f"vis-{_slug(cap)}-{i}"
            cases.append(
                {
                    "id": cid,
                    "slice": "visible",
                    "capability": cap,
                    "answer": f"{_ANSWERS[cap]}:{cid}",
                    "required_output_fields": list(OUTPUT_FIELDS),
                }
            )
    for cap, n in _HELDOUT_COUNTS.items():
        for i in range(1, n + 1):
            cid = f"hold-{_slug(cap)}-{i}"
            cases.append(
                {
                    "id": cid,
                    "slice": "held-out",
                    "capability": cap,
                    "answer": f"{_ANSWERS[cap]}:{cid}",
                    "required_output_fields": list(OUTPUT_FIELDS),
                }
            )
    return cases


CASES: list[dict[str, Any]] = build_cases()


def visible_cases() -> list[dict[str, Any]]:
    return [c for c in CASES if c["slice"] == "visible"]


def heldout_cases() -> list[dict[str, Any]]:
    return [c for c in CASES if c["slice"] == "held-out"]


def visible_answer_key() -> dict[str, str]:
    """Lookup table an overfit variant memorizes. Held-out ids are absent."""
    return {c["id"]: c["answer"] for c in visible_cases()}
