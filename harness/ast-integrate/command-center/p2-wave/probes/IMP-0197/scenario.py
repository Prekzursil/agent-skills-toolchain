"""Frozen hermetic fixtures for IMP-0197 paired A/B probes."""

from __future__ import annotations

from typing import Any

UNDERPOWERED_N = 3
POWERED_N = 24
DEFAULT_MIN_N = 20
CORPUS_ID = "imp-0197-fixture-corpus-v1"

WF_LEN = {
    "id": "wf.payload-len",
    "scorer": "payload_len",
    "params": {},
    "kind": "hermetic-scorer",
}
WF_PLUS = {
    "id": "wf.payload-len.plus1",
    "scorer": "payload_len",
    "params": {"offset": 1.0},
    "kind": "hermetic-scorer",
}


def make_cases(n: int, *, prefix: str) -> list[dict[str, Any]]:
    """Deterministic matched cases. Prefix isolates underpowered vs powered ids."""
    cases: list[dict[str, Any]] = []
    strata = ("easy", "med", "hard")
    for i in range(int(n)):
        text = f"case {i} " + ("word " * (1 + (i % 7)))
        cases.append(
            {
                "id": f"{prefix}-{i:04d}",
                "stratum": strata[i % 3],
                "payload": {"text": text.strip(), "i": i},
            }
        )
    return cases


def underpowered_cases() -> list[dict[str, Any]]:
    return make_cases(UNDERPOWERED_N, prefix="under")


def powered_cases() -> list[dict[str, Any]]:
    return make_cases(POWERED_N, prefix="power")
