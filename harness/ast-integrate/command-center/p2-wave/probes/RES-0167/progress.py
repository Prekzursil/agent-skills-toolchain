#!/usr/bin/env python3
"""Computable fix-review progress predicate (consecutive attempts).

PROGRESS vs NO-PROGRESS is a function of the last two attempts' error
fingerprints and the latest outcome. It does not inspect prose, diffs,
or 'it felt like progress'.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

PROGRESS = "PROGRESS"
NO_PROGRESS = "NO-PROGRESS"
SUCCESS_OUTCOMES = frozenset({"SUCCESS", "DELIVERED", "PASS", "OK", "DONE-OK"})

# Recorded grind (ADV-0059 retry.attempts): same fingerprint twice, still BLOCKED.
GRIND_SEQUENCE: list[dict[str, Any]] = [
    {
        "attempt": 1,
        "error_fingerprint": "partial-clone-hydration-transport",
        "outcome": "TIMEOUT",
        "source": "command-center/p2-wave/probes/ADV-0059/_validate_out.json",
    },
    {
        "attempt": 2,
        "error_fingerprint": "partial-clone-hydration-transport",
        "outcome": "FAILED",
        "source": "command-center/p2-wave/probes/ADV-0059/_validate_out.json",
    },
]

# Known productive sequence: fingerprint changes, then a distinct failure
# class (AUD-0084 recorded two different fingerprints) — retry is working.
PRODUCTIVE_SEQUENCE: list[dict[str, Any]] = [
    {
        "attempt": 1,
        "error_fingerprint": "probe1-json-lone-surrogate-serialization",
        "outcome": "FAILED",
        "source": "command-center/p2-wave/probes/AUD-0084/_refute_out.json",
    },
    {
        "attempt": 2,
        "error_fingerprint": "probe1-discovery-read-toctou",
        "outcome": "FAILED",
        "source": "command-center/p2-wave/probes/AUD-0084/_refute_out.json",
    },
]

# Productive sequence that ends in success (synthetic control; not claimed
# as an estate conversion rate).
PRODUCTIVE_THEN_SUCCESS: list[dict[str, Any]] = [
    {
        "attempt": 1,
        "error_fingerprint": "predicate:absent",
        "outcome": "FAILED",
    },
    {
        "attempt": 2,
        "error_fingerprint": "",
        "outcome": "SUCCESS",
    },
]


def _fp(attempt: Mapping[str, Any]) -> str:
    for key in ("error_fingerprint", "fp", "fingerprint"):
        val = attempt.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def _outcome(attempt: Mapping[str, Any]) -> str:
    return str(attempt.get("outcome") or attempt.get("result") or "").strip().upper()


def classify_attempts(attempts: Sequence[Mapping[str, Any]]) -> str:
    """Return PROGRESS or NO-PROGRESS.

    Let F(i) be the error fingerprint of attempt i and O(i) its outcome.
    n = len(attempts).

      if n == 0: ValueError
      if O(n) is a success outcome: PROGRESS
      if n == 1: PROGRESS   # a first failure is not a grind
      if F(n) != '' and F(n) == F(n-1): NO-PROGRESS
      else: PROGRESS
    """
    if not attempts:
        raise ValueError("classify_attempts requires at least one attempt")
    last = attempts[-1]
    if _outcome(last) in SUCCESS_OUTCOMES:
        return PROGRESS
    if len(attempts) == 1:
        return PROGRESS
    prev = attempts[-2]
    fa, fb = _fp(prev), _fp(last)
    if fa and fb and fa == fb:
        return NO_PROGRESS
    return PROGRESS


def consecutive_same_fingerprint_run(attempts: Sequence[Mapping[str, Any]]) -> int:
    """Trailing count of equal non-empty fingerprints (1 if none/unique)."""
    if not attempts:
        return 0
    last = _fp(attempts[-1])
    if not last:
        return 1 if attempts else 0
    n = 0
    for a in reversed(attempts):
        if _fp(a) == last:
            n += 1
        else:
            break
    return n


def park_decision(attempts: Sequence[Mapping[str, Any]], same_fp_limit: int = 2) -> dict[str, Any]:
    """Two same-fingerprint structural failures → park BLOCKED + required_fix."""
    verdict = classify_attempts(attempts) if attempts else PROGRESS
    run = consecutive_same_fingerprint_run(attempts)
    fp = _fp(attempts[-1]) if attempts else ""
    park = verdict == NO_PROGRESS and run >= same_fp_limit
    required_fix = ""
    if park:
        required_fix = f"break-same-fingerprint:{fp}"
    return {
        "verdict": verdict,
        "consecutive_same_fingerprint": run,
        "park": park,
        "status_if_park": "BLOCKED" if park else None,
        "required_fix": required_fix or None,
        "fingerprint": fp or None,
        "attempt_count": len(attempts),
    }


def always_progress(_attempts: Sequence[Mapping[str, Any]]) -> str:
    """Known-broken detector: silent on grind."""
    return PROGRESS


def both_states(classifier=classify_attempts) -> dict[str, Any]:
    prod = classifier(PRODUCTIVE_SEQUENCE)
    grind = classifier(GRIND_SEQUENCE)
    success = classifier(PRODUCTIVE_THEN_SUCCESS)
    broken_grind = always_progress(GRIND_SEQUENCE)
    return {
        "productive_sequence": PRODUCTIVE_SEQUENCE,
        "grind_sequence": GRIND_SEQUENCE,
        "productive_verdict": prod,
        "grind_verdict": grind,
        "productive_then_success_verdict": success,
        "good_discriminator": prod == PROGRESS and grind == NO_PROGRESS,
        "broken_always_progress_on_grind": broken_grind,
        "broken_silent_on_grind": broken_grind == PROGRESS,
        "printed": (
            f"productive={prod} grind={grind} "
            f"discriminator={prod == PROGRESS and grind == NO_PROGRESS}"
        ),
        "good_discriminator": prod == PROGRESS and grind == NO_PROGRESS,
        "broken_always_progress_on_grind": broken_grind,
    }


both_states = both_states
classify_attempts = classify_attempts
PRODUCTIVE_SEQUENCE = PRODUCTIVE_SEQUENCE
GRIND_SEQUENCE = GRIND_SEQUENCE
park_decision = park_decision
classify_attempts = classify_attempts
park_decision = park_decision
park_decision = park_decision
park_decision = park_decision
