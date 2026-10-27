"""Directly-runnable tests for IMP-0356 (council.outcomes.completeness)."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PROBES = REPO / "command-center/p2-wave/probes/IMP-0356"
for p in (str(PROBES), str(REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

from council.outcomes.completeness import (  # noqa: E402
    check_artifact,
    census,
    complete_artifact,
    is_vacuous,
    vacuous_mutants,
)
from corpus_imp0356 import build_doc  # noqa: E402


def test_census_twenty_councils_lists_missing() -> None:
    docs = [build_doc(i) for i in range(20)]
    result = census(docs)
    assert result["n_councils"] == 20
    assert result["n_pass"] + result["n_fail"] == 20
    assert result["missing_most_often"] == "calibration"
    per = {r["output"]: r for r in result["per_output"]}
    assert per["calibration"]["incomplete"] == 12
    assert per["calibration"]["absent"] == 9
    assert per["calibration"]["vacuous"] == 3
    assert per["dissent"]["incomplete"] == 2
    for row in result["rows"]:
        if row["missing"]:
            assert row["pass"] is False


def test_empty_but_present_fails_nonvacuity() -> None:
    doc = complete_artifact("negctl-empty-but-present")
    doc["outputs"]["dissent"] = {"items": [], "note": "TBD"}
    row = check_artifact(doc)
    assert row["pass"] is False
    assert "dissent:vacuous" in row["fail_reasons"]


def test_vacuous_mutants_all_fail() -> None:
    for mutant in vacuous_mutants():
        row = check_artifact(mutant["artifact"])
        assert row["pass"] is False
        assert row["fail_reasons"] == [f"{mutant['section']}:vacuous"]


def test_complete_control_passes() -> None:
    row = check_artifact(complete_artifact("good-state-control"))
    assert row["pass"] is True
    assert row["missing"] == []


def test_is_vacuous_table() -> None:
    assert is_vacuous(None) is True
    assert is_vacuous("") is True
    assert is_vacuous("TBD") is True
    assert is_vacuous("TODO") is True
    assert is_vacuous([]) is True
    assert is_vacuous({"ok": 1}) is True
    assert is_vacuous({"items": [1]}) is False
    assert is_vacuous("real content") is False


if __name__ == "__main__":
    import traceback

    failed = []
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception:
                failed.append(name)
                print(f"FAIL {name}")
                traceback.print_exc()
    if failed:
        print(f"FAILED:IMP-0356-tests failures={len(failed)}")
        raise SystemExit(1)
    print("SUCCESS:IMP-0356-tests all pass")
    raise SystemExit(0)
