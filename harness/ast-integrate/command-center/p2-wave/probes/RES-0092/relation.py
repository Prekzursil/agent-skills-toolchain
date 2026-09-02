"""Metamorphic relation MR-REORDER-UNORDERED-CASES.

Follow-up: reverse an unordered collection of independent cases.
Expected: pass/fail rebound to case id is unchanged.
Violation of that equality is a genuine order-dependence defect.

Known-good fingerprint binds scores to case id.
Known-broken fingerprint is a positional score tuple (no rebinding).
A probe silent on both fixtures measures nothing.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from pipeline import execute_case, live_workflow
from threshold import (
    CHOSEN_BEFORE_RUN,
    DISTANCE_METRIC,
    RATIONALE,
    VARIANCE_THRESHOLD,
)

HERE = Path(__file__).resolve().parent
RELATION_ID = "MR-REORDER-UNORDERED-CASES"

# Mixed scores are required: an all-pass vector would make the positional
# tuple accidentally invariant under permutation (fixture-unrepresentative).
# Order is load-bearing for the known-broken positional tuple: a palindrome
# such as (1,0,1) stays identical under reverse and would make the checker
# silent in both states (fixture-unrepresentative). (1,1,0) reversed is (0,1,1).
MIXED_CASES: tuple[dict[str, Any], ...] = (
    {
        "id": "case.pass.parse",
        "family": "parse-only",
        "required_capabilities": ["parse"],
    },
    {
        "id": "case.pass.lookup",
        "family": "lookup",
        "required_capabilities": ["lookup"],
    },
    {
        "id": "case.fail.missing-capability",
        "family": "negative",
        "required_capabilities": ["capability-that-does-not-exist"],
    },
)

KNOWN_GOOD = {
    "id": "fixture.good.order-invariant-fingerprint",
    "pipeline": "fingerprint_by_case_id",
    "expect_violated": False,
}
KNOWN_BROKEN = {
    "id": "fixture.broken.positional-score-tuple",
    "pipeline": "fingerprint_positional_tuple",
    "expect_violated": True,
}


def permute_reverse(cases: list[dict] | tuple[dict, ...]) -> list[dict]:
    return list(reversed(list(cases)))


def scores_are_mixed(workflow: dict, cases: list[dict] | tuple[dict, ...]) -> bool:
    vals = {execute_case(workflow, c)["score"] for c in cases}
    return len(vals) >= 2


def positional_tuple_moves(workflow: dict, cases: list[dict] | tuple[dict, ...]) -> bool:
    """True iff reverse is a different positional score tuple (anti-palindrome)."""
    src = fingerprint_positional_tuple(workflow, cases)
    fol = fingerprint_positional_tuple(workflow, permute_reverse(cases))
    return src != fol


def fingerprint_by_case_id(workflow: dict, cases: list[dict] | tuple[dict, ...]) -> dict[str, float]:
    """Known-good: scores rebound to case id (order-invariant)."""
    out: dict[str, float] = {}
    for case in cases:
        cell = execute_case(workflow, case)
        out[str(case["id"])] = float(cell["score"])
    return out


def fingerprint_positional_tuple(
    workflow: dict, cases: list[dict] | tuple[dict, ...]
) -> tuple[float, ...]:
    """Known-broken: encounter-order score vector with no case-id rebinding."""
    return tuple(float(execute_case(workflow, case)["score"]) for case in cases)


def distance_dict(a: dict[str, float], b: dict[str, float]) -> int:
    keys = set(a) | set(b)
    return sum(1 for k in keys if a.get(k) != b.get(k))


def distance_tuple(a: tuple[float, ...], b: tuple[float, ...]) -> int:
    d = abs(len(a) - len(b))
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            d += 1
    return d


def check_relation(
    fingerprint_fn: Callable,
    distance_fn: Callable,
    workflow: dict,
    source_cases: list[dict] | tuple[dict, ...],
    followup_cases: list[dict] | tuple[dict, ...],
    threshold: int = VARIANCE_THRESHOLD,
) -> dict[str, Any]:
    source_fp = fingerprint_fn(workflow, source_cases)
    followup_fp = fingerprint_fn(workflow, followup_cases)
    dist = int(distance_fn(source_fp, followup_fp))
    return {
        "source": source_fp,
        "followup": followup_fp,
        "distance": dist,
        "threshold": int(threshold),
        "violated": dist > int(threshold),
        "threshold_stated_before_run": CHOSEN_BEFORE_RUN,
        "distance_metric": DISTANCE_METRIC,
    }


def independent_good_fingerprint(
    workflow: dict, cases: list[dict] | tuple[dict, ...]
) -> frozenset:
    """Mechanically different good fingerprint: unordered (id, score) pairs."""
    return frozenset(
        (str(c["id"]), float(execute_case(workflow, c)["score"])) for c in cases
    )


def independent_broken_fingerprint(
    workflow: dict, cases: list[dict] | tuple[dict, ...]
) -> str:
    """Mechanically different broken fingerprint: joined encounter-order scores."""
    return "|".join(
        f"{float(execute_case(workflow, c)['score']):.1f}" for c in cases
    )


def independent_set_distance(a: frozenset, b: frozenset) -> int:
    return len(a.symmetric_difference(b))


def independent_str_distance(a: str, b: str) -> int:
    return 0 if a == b else 1


def run_identity_and_reverse(kind: str) -> dict[str, Any]:
    workflow = live_workflow()
    source = list(MIXED_CASES)
    followup = permute_reverse(source)
    if kind == "good":
        fp, dist = fingerprint_by_case_id, distance_dict
        indep_fp, indep_dist = independent_good_fingerprint, independent_set_distance
    elif kind == "broken":
        fp, dist = fingerprint_positional_tuple, distance_tuple
        indep_fp, indep_dist = independent_broken_fingerprint, independent_str_distance
    else:
        raise ValueError(kind)
    identity = check_relation(fp, dist, workflow, source, source)
    reversed_run = check_relation(fp, dist, workflow, source, followup)
    indep_identity = {
        "source": _jsonable(indep_fp(workflow, source)),
        "followup": _jsonable(indep_fp(workflow, source)),
        "distance": int(indep_dist(indep_fp(workflow, source), indep_fp(workflow, source))),
    }
    indep_rev = {
        "source": _jsonable(indep_fp(workflow, source)),
        "followup": _jsonable(indep_fp(workflow, followup)),
        "distance": int(indep_dist(indep_fp(workflow, source), indep_fp(workflow, followup))),
    }
    indep_identity["violated"] = indep_identity["distance"] > VARIANCE_THRESHOLD
    indep_rev["violated"] = indep_rev["distance"] > VARIANCE_THRESHOLD
    return {
        "kind": kind,
        "workflow_id": workflow.get("id"),
        "pipeline_step": "command-center/p2-wave/probes/CNF-0075/harness.py:execute_case",
        "source_case_ids": [c["id"] for c in source],
        "followup_case_ids": [c["id"] for c in followup],
        "scores_mixed": scores_are_mixed(workflow, source),
        "positional_tuple_moves": positional_tuple_moves(workflow, source),
        "identity": identity,
        "reversed": reversed_run,
        "independent_identity": indep_identity,
        "independent_reversed": indep_rev,
        "threshold": VARIANCE_THRESHOLD,
        "threshold_rationale": RATIONALE,
        "distance_metric": DISTANCE_METRIC,
    }


def _jsonable(value: Any) -> Any:
    if isinstance(value, frozenset):
        return sorted((a, b) for a, b in value)
    return value


def live_relation_run() -> dict[str, Any]:
    """Implemented relation against the live pipeline (known-good fingerprint)."""
    row = run_identity_and_reverse("good")
    cells = []
    workflow = live_workflow()
    for case in MIXED_CASES:
        cell = execute_case(workflow, case)
        cells.append(
            {
                "case_id": case["id"],
                "score": cell["score"],
                "passed": cell["passed"],
                "capabilities": cell["capabilities"],
                "required_capabilities": cell["required_capabilities"],
            }
        )
    row["per_case"] = cells
    row["relation_id"] = RELATION_ID
    return row


def both_states_run() -> dict[str, Any]:
    good = run_identity_and_reverse("good")
    broken = run_identity_and_reverse("broken")
    silent_in_both = (
        good["reversed"]["violated"] == broken["reversed"]["violated"]
    )
    return {
        "good": good,
        "broken": broken,
        "fired_on_broken_reverse": broken["reversed"]["violated"] is True,
        "silent_on_good_reverse": good["reversed"]["violated"] is False,
        "identity_good_silent": good["identity"]["violated"] is False,
        "identity_broken_silent": broken["identity"]["violated"] is False,
        "independent_agrees": (
            good["independent_reversed"]["violated"] == good["reversed"]["violated"]
            and broken["independent_reversed"]["violated"]
            == broken["reversed"]["violated"]
        ),
        "silent_in_both_states": silent_in_both,
        "scores_mixed": good["scores_mixed"] and broken["scores_mixed"],
        "positional_tuple_moves": good["positional_tuple_moves"]
        and broken["positional_tuple_moves"],
    }


def dump_fixture_files() -> None:
    fx = HERE / "fixtures"
    fx.mkdir(parents=True, exist_ok=True)
    payload = {
        "relation_id": RELATION_ID,
        "threshold": VARIANCE_THRESHOLD,
        "cases": list(MIXED_CASES),
        "followup": "reverse",
        "known_good": KNOWN_GOOD,
        "known_broken": KNOWN_BROKEN,
    }
    (fx / "inline-fixtures.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
