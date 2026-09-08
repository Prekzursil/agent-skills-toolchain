#!/usr/bin/env python3
"""IMP-0005 negative control: raise ceiling above fixture → over-budget test goes red.

Catalog tests_required:
  NEGATIVE CONTROL: raise the ceiling above the fixture size and assert the
  over-budget test goes red.

Procedure:
  1. Run test_over_budget_fails in the healthy state → PASS (detector fires).
  2. Mutate check_budget to use a raised ceiling (always within budget) while
     the test still expects BudgetError → the test goes red.
  3. Restore and confirm healthy PASS again.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
TEST_NODE = "tools/plugin/tests/test_size_budget.py::test_over_budget_fails"


def _pytest(extra_env: dict[str, str] | None = None) -> tuple[int, str]:
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", TEST_NODE, "--tb=line"],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def main() -> int:
    lines = [
        "NEGATIVE CONTROL: raise ceiling above fixture → over-budget test goes red",
        "NEGATIVE-CONTROL-BEGIN:IMP-0005",
        f"test_node={TEST_NODE}",
    ]

    # Healthy state: detector fires → test PASS.
    good_rc, good_out = _pytest()
    lines.append(f"good_state_pytest_exit={good_rc}")
    lines.append("good_state_pytest_output_begin")
    lines.append(good_out.rstrip())
    lines.append("good_state_pytest_output_end")
    if good_rc != 0:
        lines.append("FAILED:IMP-0005-negative-control healthy-state-not-green")
        raw = "\n".join(lines) + "\n"
        (PROBE / "negative-control.raw.txt").write_text(raw, encoding="utf-8")
        print(raw, end="")
        return 1

    # Bad state: monkeypatch via sitecustomize-style injection — rewrite the
    # test temporarily so max_bytes is raised above fixture size (ceiling up),
    # which makes the expected BudgetError never fire → test RED.
    test_path = REPO / "tools/plugin/tests/test_size_budget.py"
    original = test_path.read_text(encoding="utf-8")
    # Replace the tight ceiling with a raised one (fixture size * 10).
    mutated = original.replace(
        "tight_bytes = max(1, size_bytes // 2)",
        "tight_bytes = size_bytes * 10  # NEGATIVE CONTROL: raise ceiling above fixture",
    )
    if mutated == original:
        lines.append("FAILED:IMP-0005-negative-control could-not-mutate-ceiling")
        raw = "\n".join(lines) + "\n"
        (PROBE / "negative-control.raw.txt").write_text(raw, encoding="utf-8")
        print(raw, end="")
        return 1
    try:
        test_path.write_text(mutated, encoding="utf-8")
        bad_rc, bad_out = _pytest()
    finally:
        test_path.write_text(original, encoding="utf-8")

    lines.append(f"bad_state_pytest_exit={bad_rc}")
    lines.append("bad_state_pytest_output_begin")
    lines.append(bad_out.rstrip())
    lines.append("bad_state_pytest_output_end")

    # Restore confirmation.
    restore_rc, restore_out = _pytest()
    lines.append(f"restored_pytest_exit={restore_rc}")

    fired_on_bad = bad_rc != 0  # test went red when ceiling raised
    silent_on_good = good_rc == 0 and restore_rc == 0
    control_passed = fired_on_bad and silent_on_good

    meas = {
        "control_passed": control_passed,
        "fired_on_bad_state": fired_on_bad,
        "silent_on_good_state": silent_on_good,
        "good_state_exit": good_rc,
        "bad_state_exit": bad_rc,
        "restored_exit": restore_rc,
        "mutation": "raise tight_bytes from size_bytes//2 to size_bytes*10",
    }
    (PROBE / "negative-control-measurement.json").write_text(
        json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines.append(json.dumps(meas, indent=2, sort_keys=True))
    lines.append("NEGATIVE-CONTROL-COMPLETE:IMP-0005")
    lines.append(
        "SUCCESS:IMP-0005-negative-control"
        if control_passed
        else "FAILED:IMP-0005-negative-control"
    )
    raw = "\n".join(lines) + "\n"
    (PROBE / "negative-control.raw.txt").write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if control_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
