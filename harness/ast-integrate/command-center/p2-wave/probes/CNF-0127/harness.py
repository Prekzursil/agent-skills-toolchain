#!/usr/bin/env python3
"""Dedupe benchmark variants and repetition measurement for CNF-0127.

Metric for keep/revert (except the planted wall-clock noise claim) is an
operation count: every compare and hash lookup ticks. Wall-clock is recorded
alongside but is only decisive for the noise-dominated planted claim.
"""
from __future__ import annotations

import time
from typing import Callable

REPETITIONS = 11

# Workload includes case-duplicates so the original failure is observable.
ITEMS: list[str] = (
    ["alpha", "Alpha", "BETA", "beta", "gamma", "Gamma", "delta"]
    + [f"item{i}" for i in range(40)]
    + [f"item{i}" for i in range(10)]
    + ["Hello", "HELLO"]
)

# Spec: unique by casefold, keep first folded form.
SPEC_OUT: list[str] = []
_seen_spec: set[str] = set()
for _x in ITEMS:
    _f = _x.casefold()
    if _f not in _seen_spec:
        _seen_spec.add(_f)
        SPEC_OUT.append(_f)


def _baseline(items: list[str]) -> tuple[list[str], int]:
    """Linear membership, no casefold — original failure lives here."""
    ops = 0
    out: list[str] = []
    for x in items:
        ops += 1
        found = False
        for y in out:
            ops += 1
            if y == x:
                found = True
                break
        if not found:
            ops += 1
            out.append(x)
    return out, ops


def _casefold_set(items: list[str]) -> tuple[list[str], int]:
    """Hashed membership + casefold — genuine measured improvement."""
    ops = 0
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        ops += 1
        folded = x.casefold()
        ops += 1
        if folded not in seen:
            ops += 1
            seen.add(folded)
            out.append(folded)
    return out, ops


def _neutral_comments(items: list[str]) -> tuple[list[str], int]:
    """Byte-different comments only; same compares as baseline."""
    # Retention-auditor note: comments are not a speedup.
    return _baseline(items)


def _extra_scan(items: list[str]) -> tuple[list[str], int]:
    """Harmful: extra full scan of `out` on every insert."""
    ops = 0
    out: list[str] = []
    for x in items:
        ops += 1
        found = False
        for y in out:
            ops += 1
            if y == x:
                found = True
                break
        for y in out:
            ops += 1
            _ = y
        if not found:
            ops += 1
            out.append(x)
    return out, ops


def _set_no_casefold(items: list[str]) -> tuple[list[str], int]:
    """Faster hashed membership that still misses case-duplicates."""
    ops = 0
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        ops += 1
        ops += 1
        if x not in seen:
            ops += 1
            seen.add(x)
            out.append(x)
    return out, ops


def _tiny_noop(items: list[str]) -> tuple[list[str], int]:
    """Same algorithm as baseline; claimed wall-clock win is noise."""
    return _baseline(items)


VARIANTS: dict[str, Callable[[list[str]], tuple[list[str], int]]] = {
    "baseline": _baseline,
    "casefold_set": _casefold_set,
    "neutral_comments": _neutral_comments,
    "extra_scan": _extra_scan,
    "set_no_casefold": _set_no_casefold,
    "tiny_noop": _tiny_noop,
}

GUARD_CASES = {
    "casefold-dup": ["Hello", "HELLO"],
    "identity-roundtrip": ["solo"],
}


def spec_for(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        f = x.casefold()
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    if n == 0:
        raise ValueError("median of empty")
    if n % 2:
        return float(s[n // 2])
    return (s[n // 2 - 1] + s[n // 2]) / 2.0


def iqr(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    if n == 0:
        raise ValueError("iqr of empty")

    def pct(p: float) -> float:
        if n == 1:
            return float(s[0])
        i = (n - 1) * p
        lo = int(i)
        hi = min(lo + 1, n - 1)
        w = i - lo
        return s[lo] * (1.0 - w) + s[hi] * w

    return pct(0.75) - pct(0.25)


def run_once(variant: str, items: list[str] | None = None) -> dict:
    fn = VARIANTS[variant]
    payload = list(ITEMS if items is None else items)
    t0 = time.perf_counter()
    out, ops = fn(payload)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    ok = out == spec_for(payload)
    return {
        "out": out,
        "ops": int(ops),
        "elapsed_ms": float(elapsed_ms),
        "correct": bool(ok),
    }


def guard_result(variant: str, guard_id: str) -> dict:
    items = GUARD_CASES[guard_id]
    got = run_once(variant, items)
    expected = spec_for(items)
    catches_failure = not got["correct"] if variant == "baseline" else got["correct"]
    return {
        "guard_id": guard_id,
        "variant": variant,
        "correct": got["correct"],
        "expected": expected,
        "got": got["out"],
        "ops": got["ops"],
        "passes_spec": got["out"] == expected,
        "baseline_fails_this_guard": not run_once("baseline", items)["correct"],
        "catches_or_holds": catches_failure,
    }


def measure_variant(
    variant: str,
    *,
    agent_id: str,
    repetitions: int = REPETITIONS,
    items: list[str] | None = None,
) -> dict:
    """Independent remesurer entry. Every repetition is retained (no last-green-wins)."""
    if variant not in VARIANTS:
        raise KeyError(variant)
    raw_ops: list[float] = []
    raw_ms: list[float] = []
    outcomes: list[str] = []
    last_out = None
    for _ in range(repetitions):
        row = run_once(variant, items)
        raw_ops.append(float(row["ops"]))
        raw_ms.append(float(row["elapsed_ms"]))
        outcomes.append("green" if row["correct"] else "red")
        last_out = row["out"]
    greens = outcomes.count("green")
    return {
        "agent_id": agent_id,
        "variant": variant,
        "repetitions": repetitions,
        "raw_ops": raw_ops,
        "raw_ms": raw_ms,
        "outcomes": outcomes,
        "reported_as": f"{greens}/{repetitions}",
        "ops_median": median(raw_ops),
        "ops_iqr": iqr(raw_ops),
        "ms_median": median(raw_ms),
        "ms_iqr": iqr(raw_ms),
        "all_outcomes_recorded": True,
        "last_green_does_not_overwrite": True,
        "correct": greens == repetitions,
        "sample_out": last_out,
    }


def flake_demo_1_of_7() -> dict:
    """Retry policy: six reds then one green is 1/7, never a green overwrite."""
    outcomes = ["red"] * 6 + ["green"]
    greens = outcomes.count("green")
    return {
        "outcomes": outcomes,
        "reported_as": f"{greens}/{len(outcomes)}",
        "forbidden_overwrite": "7/7",
        "policy": (
            "Re-runs are flake measurement only. EVERY run is recorded; "
            "a green on run 7 of 7 does not overwrite the 6 reds; it is 1/7."
        ),
    }
