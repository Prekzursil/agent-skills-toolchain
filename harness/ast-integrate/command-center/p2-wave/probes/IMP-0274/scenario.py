#!/usr/bin/env python3
"""Deterministic IMP-0274 council-run fixtures."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

QUESTION = "Should we ship the parser.c workaround?"
CONSENSUS = (
    "Ship the workaround that skips the bounds check and mark the ticket closed."
)
EVIDENCE = [
    "build failed on parser.c:42",
    "null dereference reproduced in unit tests",
]
CATCH_UP = [
    "asan report: heap-buffer-overflow in parser.c:42",
]


def base_run(**overrides: Any) -> dict[str, Any]:
    run: dict[str, Any] = {
        "question": QUESTION,
        "min_seats": 3,
        "max_seats": 6,
        "required_coverage": ["parser-c", "testing", "security"],
        "mid_run_topics": [],
        "shared_evidence": list(EVIDENCE),
        "catch_up_facts": list(CATCH_UP),
        "running_consensus": CONSENSUS,
        "transcript": [
            {"seat_id": "s1", "position": CONSENSUS},
            {"seat_id": "s2", "position": CONSENSUS},
            {"seat_id": "s3", "position": CONSENSUS},
        ],
        "seats": [
            {
                "seat_id": "s1",
                "role": "proposer",
                "expertise": ["parser-c"],
                "original": True,
            },
            {
                "seat_id": "s2",
                "role": "reviewer",
                "expertise": ["testing"],
                "original": True,
            },
            {
                "seat_id": "s3",
                "role": "chair",
                "expertise": ["process"],
                "original": True,
            },
        ],
        "candidates": [
            {
                "seat_id": "r-security",
                "role": "security-refuter",
                "expertise": ["security"],
            },
            {
                "seat_id": "r-crypto",
                "role": "cryptographer",
                "expertise": ["cryptography"],
            },
        ],
    }
    run.update(overrides)
    return deepcopy(run)


def covered_run() -> dict[str, Any]:
    """No coverage gap: security is already seated."""
    run = base_run()
    run["seats"][2]["expertise"] = ["process", "security"]
    return run


def at_max_with_gap() -> dict[str, Any]:
    run = base_run(max_seats=3)
    return run
