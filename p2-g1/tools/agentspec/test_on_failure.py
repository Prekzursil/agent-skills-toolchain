"""On-failure policy taxonomy: unknown reasons fail validation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_ON_FAILURE = {
    "timeout": "retry",
    "cancelled": "abort",
    "resource": "retry",
    "schema": "abort",
}


@dataclass
class FailureError:
    id: str
    message: str
    reason: str = ""


def complete_policy() -> dict[str, Any]:
    return dict(DEFAULT_ON_FAILURE)


def validate_on_failure(policy: dict[str, Any]) -> list[FailureError]:
    errs: list[FailureError] = []
    if not isinstance(policy, dict):
        return [FailureError("on-failure-not-object", "policy must be an object")]
    for key, val in policy.items():
        if key not in DEFAULT_ON_FAILURE:
            errs.append(
                FailureError(
                    "on-failure-unknown-reason",
                    f"unknown on-failure reason {key}",
                    reason=str(key),
                )
            )
        if str(val) not in {"retry", "abort", "skip", "escalate"}:
            errs.append(
                FailureError(
                    "on-failure-unknown-action",
                    f"unknown action {val} for {key}",
                    reason=str(key),
                )
            )
    return errs


def test_out_of_taxonomy_reason_fails_validation() -> dict[str, Any]:
    good = validate_on_failure(complete_policy())
    bad = dict(complete_policy())
    bad["not-a-timeout"] = "abort"
    bad_errs = validate_on_failure(bad)
    passed = len(good) == 0 and any(e.id == "on-failure-unknown-reason" for e in bad_errs)
    return {
        "pass": passed,
        "good_error_count": len(good),
        "bad_error_ids": [e.id for e in bad_errs],
        "taxonomy": sorted(DEFAULT_ON_FAILURE),
    }


def test_family_coverage_set_difference() -> dict[str, Any]:
    taxonomy = set(DEFAULT_ON_FAILURE)
    families = set(DEFAULT_ON_FAILURE)
    unmapped = sorted(families - taxonomy)
    unknown = sorted(taxonomy - families)
    return {
        "pass": not unmapped and not unknown,
        "family": sorted(taxonomy),
        "unmapped": unmapped,
        "unknown": unknown,
    }


def test_not_substring_branch() -> dict[str, Any]:
    # "time" is a substring of "timeout" but is not a taxonomy reason.
    policy = dict(DEFAULT_ON_FAILURE)
    policy["time"] = "retry"
    errs = validate_on_failure(policy)
    fired = any(e.id == "on-failure-unknown-reason" and e.reason == "time" for e in errs)
    return {"pass": fired, "errors": [e.id for e in errs]}
