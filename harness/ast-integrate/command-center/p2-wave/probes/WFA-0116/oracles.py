#!/usr/bin/env python3
"""Independent strong and weak postcondition oracles.

The strong oracle recomputes the expected result from operands. It does not
import runners.compute. The weak oracle only checks that an artifact dict
with a `result` key exists — the measured shape of an oracle that measures
nothing.
"""
from __future__ import annotations

from typing import Any


def expected_result(case: dict[str, Any]) -> int | str:
    op = str(case["op"])
    a = int(case["a"])
    b = int(case["b"])
    if op == "add":
        return a + b
    if op == "mul":
        return a * b
    if op == "xor":
        return a ^ b
    if op == "cat":
        return f"{a}:{b}"
    raise ValueError(f"unknown op {op!r}")


def strong_oracle(artifact: Any, case: dict[str, Any]) -> bool:
    if not isinstance(artifact, dict) or "result" not in artifact:
        return False
    return artifact["result"] == expected_result(case)


def weak_oracle(artifact: Any, case: dict[str, Any]) -> bool:
    return isinstance(artifact, dict) and "result" in artifact
