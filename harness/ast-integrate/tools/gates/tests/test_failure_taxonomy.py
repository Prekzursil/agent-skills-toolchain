#!/usr/bin/env python3
"""Tests for tools/gates/failure_taxonomy.py (TST-0244). Stdlib only; runnable directly."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gates.failure_taxonomy import (  # noqa: E402
    TAXONOMY_CLASSES,
    UNCLASSIFIED,
    _induce,
    _message,
    _score,
    classify,
    measure_coverage,
    measure_negative_control,
    repair,
)


def test_every_class_is_induced_and_classified_from_signals() -> None:
    for cls in TAXONOMY_CLASSES:
        obs = _induce(cls)
        obs_no_label = {k: v for k, v in obs.items() if k != "inducer"}
        assert classify(obs_no_label) == cls, (cls, obs_no_label)


def test_unknown_observation_is_unclassified() -> None:
    assert classify({}) == UNCLASSIFIED
    assert classify({"exit_code": 0}) == UNCLASSIFIED


def test_catalog_message_scores_three_and_bare_error_zero() -> None:
    for cls in TAXONOMY_CLASSES:
        assert _score(_message(cls), cls)["score"] == 3
    assert _score("KeyError: 'x'", "timeout")["score"] == 0
    neg = measure_negative_control()
    assert neg["pass"] and neg["bare_score"] == 0 and neg["catalog_score"] == 3


def test_coverage_without_execution_is_full_and_unsampled() -> None:
    report = measure_coverage(execute_next=False)
    matrix = report["matrix"]
    assert matrix["n_triggered"] == len(TAXONOMY_CLASSES) and not matrix["sampled"]
    assert not matrix["missing"] and not matrix["mismatches"] and not matrix["low_scores"]
    assert report["next_commands"] == {"executed": False, "pass": [], "failed": [], "runs": []}


def test_repair_cli_exit_codes() -> None:
    assert repair("timeout") == 0
    assert repair("no-such-class") == 2


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for test in tests:
        test()
        print(f"ok {test.__name__}")
    print(f"SUCCESS:failure-taxonomy-tests {len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
