"""Eval-harness gate: scenario replays graded by code, reported as pass@1 / pass^3.

The scenarios under evals/scenarios/ are capability + regression evals in the
eval-harness sense: each replays a process table (the flagship one is the owner's
02.09.2026 measurement) through the real engine and asserts the exact kill set,
the never-touched set, the tier, and the rules that must surface. The runner is
deterministic, so pass^3 (three consecutive trials) doubles as a stability check.
"""

from __future__ import annotations

import copy
import json
import pathlib

import pytest

import run_evals

SCENARIOS = pathlib.Path(run_evals.SCENARIO_DIR)


def test_every_shipped_scenario_passes_and_is_stable():
    results = run_evals.run_all(trials=3)
    failing = [r for r in results if not r.passed]
    assert failing == [], [(r.name, r.failures) for r in failing]
    assert all(r.trials_passed == 3 for r in results)
    assert len(results) >= 6


def test_report_carries_pass_at_k_metrics(capsys):
    code = run_evals.main([])
    out = capsys.readouterr().out
    assert code == 0
    assert "EVAL REPORT: process-hygiene-supervisor" in out
    assert "pass@1:" in out and "pass^3:" in out
    assert "Status: READY" in out


def test_runner_goes_red_when_an_expectation_is_wrong(tmp_path):
    # Both-states proof: a scenario that expects a protected daemon to be killed
    # must FAIL, otherwise the grader is not grading.
    scenario = json.loads(
        (SCENARIOS / "measurement-2026-09-02.json").read_text(encoding="utf-8")
    )
    broken = copy.deepcopy(scenario)
    broken["expect"]["stop_pids"].append(4001)  # auth2api
    result = run_evals.run_scenario(broken, trials=1)
    assert result.passed is False
    assert any("stop_pids" in failure for failure in result.failures)


def test_runner_reports_a_missing_rule_and_a_wrong_tier():
    scenario = json.loads((SCENARIOS / "quiet-box.json").read_text(encoding="utf-8"))
    broken = copy.deepcopy(scenario)
    broken["expect"]["tier"] = "critical"
    broken["expect"]["rules_present"] = ["retired"]
    result = run_evals.run_scenario(broken, trials=1)
    assert result.passed is False
    assert any("tier" in failure for failure in result.failures)
    assert any("rules_present" in failure for failure in result.failures)


def test_every_grader_axis_can_fail():
    scenario = json.loads(
        (SCENARIOS / "measurement-2026-09-02.json").read_text(encoding="utf-8")
    )
    broken = copy.deepcopy(scenario)
    broken["expect"] = {
        "never_touched": [402],  # the retired bridge IS stopped
        "rules_absent": ["retired"],  # but it IS present
        "delegate_reaper": False,  # the cursor orphans ARE delegated
        "wsl_shutdown": True,  # WSL is NOT shut down here
    }
    result = run_evals.run_scenario(broken, trials=1)
    joined = "\n".join(result.failures)
    for axis in ("never_touched", "rules_absent", "delegate_reaper", "wsl_shutdown"):
        assert axis in joined
    # An expectation block that names nothing grades as a pass.
    assert run_evals.run_scenario(dict(scenario, expect={}), trials=1).passed


def test_runner_rejects_malformed_scenarios():
    with pytest.raises(run_evals.ScenarioError, match="processes"):
        run_evals.run_scenario({"name": "x", "expect": {}}, trials=1)
    with pytest.raises(run_evals.ScenarioError, match="count"):
        run_evals.run_scenario(
            {
                "name": "x",
                "processes": [{"pid": 1, "ppid": 0, "name": "a", "count": 0}],
                "expect": {},
            },
            trials=1,
        )


def test_main_exits_one_on_failure(tmp_path, capsys, monkeypatch):
    scenario = json.loads((SCENARIOS / "quiet-box.json").read_text(encoding="utf-8"))
    scenario["expect"]["tier"] = "critical"
    (tmp_path / "broken.json").write_text(json.dumps(scenario), encoding="utf-8")
    assert run_evals.main(["--scenarios", str(tmp_path)]) == 1
    assert "Status: FAILING" in capsys.readouterr().out
