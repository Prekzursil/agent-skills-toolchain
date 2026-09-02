#!/usr/bin/env python3
"""IMP-0129 probe 1: pytest 3-level nest shows namespaced ids; two-level validates."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))
sys.path.insert(0, str(REPO / "tools" / "agentspec" / "tests"))
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

from test_subworkflow import (  # noqa: E402
    check_subworkflow_frozen,
    check_three_level_namespaced_ids,
    check_two_level_validates,
)

TEST_FILE = REPO / "tools" / "agentspec" / "tests" / "test_subworkflow.py"


def main() -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO / "tools" / "agentspec")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    py = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "-q",
            f"{TEST_FILE}::test_three_level_namespaced_ids",
            f"{TEST_FILE}::test_two_level_validates",
            f"{TEST_FILE}::test_subworkflow_frozen",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    pytest_out = ((py.stdout or "") + (py.stderr or "")).strip()
    frozen = check_subworkflow_frozen()
    two = check_two_level_validates()
    three = check_three_level_namespaced_ids()
    payload = {
        "probe": "probe1-three-level-namespace",
        "unit_id": "IMP-0129",
        "pass": bool(frozen["pass"] and two["pass"] and three["pass"] and py.returncode == 0),
        "pytest_rc": py.returncode,
        "pytest_tail": pytest_out[-2000:],
        "frozen": frozen,
        "two_level": two,
        "three_level": three,
    }
    print(json.dumps(payload, sort_keys=True))
    if py.returncode != 0:
        print("FAILED:IMP-0129-probe1 pytest did not exit 0")
        print(pytest_out[-2000:])
        return 1
    if not payload["pass"]:
        print("FAILED:IMP-0129-probe1 namespaced 3-level nest or two-level validate")
        return 1
    print("SUCCESS:IMP-0129-probe1 pytest 3-level nest namespaced ids; two-level validates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
