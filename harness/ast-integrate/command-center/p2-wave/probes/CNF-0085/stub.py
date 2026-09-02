#!/usr/bin/env python3
"""Always-true reducer stub: the detector control for CNF-0085.

A fan-in stubbed to PASS every receipt MUST fail the runner-vs-oracle
differential. If it does not, the harness is comparing aggregate silence.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def evaluate_receipt(receipt: Any, repo: Path) -> dict[str, Any]:
    del receipt, repo
    return {
        "verdict": "PASS",
        "failing_condition_id": None,
        "reason": "always-true stub",
        "evaluator": "always-true-stub",
    }
