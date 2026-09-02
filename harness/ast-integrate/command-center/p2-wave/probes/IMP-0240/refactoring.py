"""Refactoring blueprint: equivalence argument for pure functions.

A claim of 'no functional change' without a differential run is rejected.
Generated inputs are the control, not a hand-picked happy path.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Iterable

Input = tuple[str, ...]
PureFn = Callable[[Input], tuple[str, ...]]


def generate_inputs(seed: int = 240, n: int = 24) -> list[Input]:
    """Deterministic generated corpus. Includes case, space, empty, and unicode."""
    raw = [
        ("Ab", "ab", "aB"),
        ("  Foo", "foo  ", "FOO"),
        ("", " ", "\t"),
        ("Ä", "ä", "A"),
        ("zeta", "Alpha", "beta"),
        ("12", "2", "1"),
    ]
    out: list[Input] = []
    for i in range(n):
        base = raw[i % len(raw)]
        tag = f"s{seed + i}"
        mixed = tuple(f"{item}{tag if j == 0 else ''}" for j, item in enumerate(base))
        out.append(mixed)
    return out


def normalize_v1(items: Input) -> tuple[str, ...]:
    return tuple(sorted(s.strip().casefold() for s in items))


def normalize_v2_equivalent(items: Input) -> tuple[str, ...]:
    buf = [s.strip().casefold() for s in items]
    buf.sort()
    return tuple(buf)


def normalize_mutant_drops_casefold(items: Input) -> tuple[str, ...]:
    """Planted 'pure refactor' that changes behavior on mixed-case input."""
    return tuple(sorted(s.strip() for s in items))


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def equivalence_argument(
    before: PureFn,
    after: PureFn,
    inputs: Iterable[Input] | None = None,
    *,
    label: str = "after",
) -> dict[str, Any]:
    corpus = list(inputs) if inputs is not None else generate_inputs()
    mismatches: list[dict[str, Any]] = []
    for idx, item in enumerate(corpus):
        left = before(item)
        right = after(item)
        if left != right:
            mismatches.append(
                {
                    "index": idx,
                    "input": list(item),
                    "before": list(left),
                    "after": list(right),
                    "before_sha256": _digest(left),
                    "after_sha256": _digest(right),
                }
            )
    equivalent = not mismatches
    return {
        "method": "differential-testing",
        "claim": "equivalence" if equivalent else "behavior-change-caught",
        "label": label,
        "input_count": len(corpus),
        "mismatch_count": len(mismatches),
        "equivalent": equivalent,
        "mismatches": mismatches[:8],
        "generated": True,
        "bare_assertion": False,
    }


def naive_no_functional_change(*, declared: bool = True) -> dict[str, Any]:
    """Negative control: assert 'no functional change' without running inputs."""
    return {
        "method": "assertion",
        "claim": "no functional change",
        "equivalent": bool(declared),
        "input_count": 0,
        "mismatch_count": 0,
        "mismatches": [],
        "generated": False,
        "bare_assertion": True,
    }


def accept_refactor_claim(argument: dict[str, Any]) -> dict[str, Any]:
    """Bare 'no functional change' is not an equivalence argument."""
    if argument.get("bare_assertion") or argument.get("method") != "differential-testing":
        return {
            "ok": False,
            "fired": True,
            "reason": "bare-no-functional-change",
        }
    if int(argument.get("input_count") or 0) < 8:
        return {
            "ok": False,
            "fired": True,
            "reason": "underpowered-corpus",
        }
    if argument.get("equivalent") is True:
        return {"ok": True, "fired": False, "reason": "equivalence-holds"}
    return {
        "ok": False,
        "fired": True,
        "reason": "behavior-change-caught",
        "mismatch_count": argument.get("mismatch_count"),
    }
