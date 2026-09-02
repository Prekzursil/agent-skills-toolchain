"""Classify red/green pairs. Green-at-pre-fix is already-satisfied, not success."""
from __future__ import annotations


def classify(pre_verdict: str, post_verdict: str) -> dict:
    pre = pre_verdict.upper()
    post = post_verdict.upper()
    observed = f"{pre}-then-{post}"
    if pre == "RED" and post == "GREEN":
        kind = "red-then-green"
    elif pre == "GREEN" and post == "GREEN":
        kind = "requirement-already-satisfied"
    elif pre == "GREEN" and post == "RED":
        kind = "overfitted-patch"
    else:
        kind = "spec-miss"
    return {
        "expected": "red-then-green",
        "observed": observed,
        "classification": kind,
    }
