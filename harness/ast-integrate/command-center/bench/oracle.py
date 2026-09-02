"""Benchmark-case oracle (TST-0295).

Every case in ``command-center/bench/cases`` carries an ``oracle`` block whose
``kind`` selects a machine-checkable evaluator below.  A solution is accepted
only when the evaluator for that kind says so; ``sanity`` re-runs the oracle on
the case's own known-good and known-bad solutions so a vacuous (always-pass)
oracle is caught, never silently retained.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CASES_DIR = HERE / "cases"
INDEX_PATH = HERE / "INDEX.json"

VACUOUS_KINDS = frozenset({"always_pass", "vacuous"})


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_cases() -> list[dict[str, Any]]:
    """Return the corpus the TST-0295 emitter wrote (index order, CASE-* only).

    The cases directory is shared with other units' fixtures, so the loader is
    index-driven and never synthesises cases: an empty corpus stays empty.
    """
    rows: list[dict[str, Any]] = []
    if INDEX_PATH.is_file():
        idx = _read(INDEX_PATH)
        for cid in list(idx.get("ids") or idx.get("case_ids") or []):
            path = CASES_DIR / f"{cid}.json"
            if path.is_file():
                rows.append(_read(path))
    if not rows and CASES_DIR.is_dir():
        rows = [_read(p) for p in sorted(CASES_DIR.glob("CASE-*.json"))]
    return rows


def split_intersections(cases: list[dict[str, Any]]) -> dict[str, list[str]]:
    by: dict[str, set[str]] = {"dev": set(), "test": set(), "held-out-shadow": set()}
    for c in cases:
        by.setdefault(str(c.get("split") or "dev"), set()).add(str(c["id"]))
    held = by["held-out-shadow"] | by.get("held_out", set())
    return {
        "dev_and_test": sorted(by["dev"] & by["test"]),
        "dev_and_held_out": sorted(by["dev"] & held),
        "test_and_held_out": sorted(by["test"] & held),
    }


# --- evaluators -----------------------------------------------------------


def _run_detector(detector: dict[str, Any], state: dict[str, Any]) -> bool:
    name = detector.get("detector")
    if name == "always_true":
        return True
    if name == "always_false":
        return False
    if name == "pattern_match":
        match = detector.get("match")
        if not isinstance(match, dict) or not match:
            return False
        return all(key in state and state[key] == value for key, value in match.items())
    return False


def _both_states(case: dict[str, Any], solution: dict[str, Any]) -> bool:
    oracle = case.get("oracle") or {}
    task = case.get("task_input") or {}
    broken = task.get("broken")
    fixed = task.get("fixed")
    if not isinstance(broken, dict) or not isinstance(fixed, dict):
        return False
    fires_broken = _run_detector(solution, broken)
    fires_fixed = _run_detector(solution, fixed)
    return fires_broken is bool(oracle.get("expect_broken", True)) and fires_fixed is bool(
        oracle.get("expect_fixed", False)
    )


def _as_sorted(value: Any) -> list[str] | None:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        return None
    return sorted(value)


def _capability_partition(case: dict[str, Any], solution: dict[str, Any]) -> bool:
    task = case.get("task_input") or {}
    shared = _as_sorted(task.get("shared_capabilities"))
    fusion_only = _as_sorted(task.get("fusion_only_capabilities"))
    if shared is None or fusion_only is None:
        return False
    head = _as_sorted(solution.get("head_to_head"))
    comp = _as_sorted(solution.get("complementarity"))
    return head == shared and comp == fusion_only


def _intersection_gate(case: dict[str, Any], solution: dict[str, Any]) -> bool:
    task = case.get("task_input") or {}
    a = _as_sorted(task.get("source_a_cases"))
    b = _as_sorted(task.get("source_b_cases"))
    if a is None or b is None:
        return False
    minimum = task.get("minimum_intersection", 1)
    if not isinstance(minimum, int) or isinstance(minimum, bool):
        return False
    expected = sorted(set(a) & set(b))
    got = _as_sorted(solution.get("intersection"))
    blocked = solution.get("blocked")
    if got is None or not isinstance(blocked, bool):
        return False
    return got == expected and blocked is (len(expected) < minimum)


def _judged_rubric(case: dict[str, Any], solution: dict[str, Any]) -> bool:
    oracle = case.get("oracle") or {}
    text = solution.get("text")
    if not isinstance(text, str) or not text.strip():
        return False
    required = [s for s in (oracle.get("required_spans") or []) if isinstance(s, str)]
    forbidden = [s for s in (oracle.get("forbidden_spans") or []) if isinstance(s, str)]
    if not required:
        return False
    return all(span in text for span in required) and not any(span in text for span in forbidden)


EVALUATORS = {
    "both_states_detector": _both_states,
    "capability_partition": _capability_partition,
    "intersection_gate": _intersection_gate,
    "judged_rubric": _judged_rubric,
}


def is_vacuous(case: dict[str, Any]) -> bool:
    oracle = case.get("oracle") or {}
    return (
        oracle.get("kind") in VACUOUS_KINDS
        or oracle.get("oracle_type") == "vacuous"
        or oracle.get("always_pass") is True
    )


def evaluate(case: dict[str, Any], solution: dict[str, Any]) -> bool:
    """Return True iff ``solution`` satisfies the case's oracle."""
    if is_vacuous(case):
        return True
    if not isinstance(solution, dict) or not solution:
        return False
    evaluator = EVALUATORS.get((case.get("oracle") or {}).get("kind"))
    if evaluator is None:
        return False
    return bool(evaluator(case, solution))


def sanity(case: dict[str, Any]) -> dict[str, Any]:
    """Both-states check of the oracle against the case's own solutions."""
    vacuous = is_vacuous(case)
    good = case.get("known_good_solution") or {}
    bad = case.get("known_bad_solution") or {}
    good_ok = evaluate(case, good)
    bad_rejected = not evaluate(case, bad)
    if vacuous:
        # An always-pass oracle accepts the known-bad too; it must be stripped.
        good_ok, bad_rejected = True, False
    return {
        "id": case.get("id"),
        "ok": (not vacuous) and good_ok and bad_rejected,
        "vacuous": vacuous,
        "good_ok": good_ok,
        "bad_rejected": bad_rejected,
    }


__all__ = ["evaluate", "is_vacuous", "load_cases", "sanity", "split_intersections"]
