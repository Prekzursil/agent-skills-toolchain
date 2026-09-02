#!/usr/bin/env python3
"""Negative-control reducer: always returns PASS. The harness MUST reject this."""
from __future__ import annotations

from typing import Any


def reduce(_snap: dict[str, Any]) -> dict[str, Any]:
    return {
        "failing_condition_id": None,
        "reason": "all 12 conditions satisfied",
        "verdict": "PASS",
    }
