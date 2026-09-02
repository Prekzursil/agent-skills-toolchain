#!/usr/bin/env python3
"""Probe 2: every documented command executed in documented form, plus
reviewer-required verbatim run of three documented commands."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.docs_commands import (  # noqa: E402
    extract_documented_invocations,
    run_documented_commands,
)
from marketplace.tests.test_docs_commands_run import (  # noqa: E402
    test_broken_command_is_detected,
    test_every_documented_command_executes,
)

GOOD = REPO / "tools/marketplace/fixtures/docs-parity-good"
REVIEWER = [
    "python3 commands/hello.py",
    "python3 commands/status.py",
    "python3 commands/version.py",
]


def _run_verbatim(line: str) -> dict:
    proc = subprocess.run(
        line,
        cwd=str(GOOD),
        shell=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return {
        "argv_line": line,
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
        "ok": proc.returncode == 0,
    }


def main() -> int:
    test_every_documented_command_executes()
    test_broken_command_is_detected()

    invocations = extract_documented_invocations(GOOD)
    if len(invocations) < 4:
        print(f"FAILED:IMP-0120-probe2 too few invocations {len(invocations)}")
        return 1
    report = run_documented_commands(GOOD)
    if not report.ok:
        print("FAILED:IMP-0120-probe2 documented commands did not match exit")
        print(json.dumps(report.as_dict(), indent=2)[:2000])
        return 1

    reviewer_rows = [_run_verbatim(line) for line in REVIEWER]
    if any(not row["ok"] for row in reviewer_rows):
        print("FAILED:IMP-0120-probe2 reviewer verbatim command failed")
        print(json.dumps(reviewer_rows, indent=2))
        return 1

    unknown = next(r for r in report.results if "--unknown" in r.invocation.argv_line)
    if unknown.returncode != 2 or unknown.invocation.expected_exit != 2:
        print("FAILED:IMP-0120-probe2 documented exit-2 behaviour not observed")
        return 1

    payload = {
        "pass": True,
        "probe": "probe2-commands-run",
        "unit_id": "IMP-0120",
        "executed": len(report.results),
        "all_matched": True,
        "reviewer_verbatim": reviewer_rows,
        "documented_exit_2_observed": True,
        "results": [
            {
                "name": r.invocation.name,
                "argv_line": r.invocation.argv_line,
                "expected_exit": r.invocation.expected_exit,
                "returncode": r.returncode,
                "matched": r.matched,
            }
            for r in report.results
        ],
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"executed={len(report.results)} all_matched=True "
        f"reviewer={len(reviewer_rows)} exit2={unknown.returncode}"
    )
    print("SUCCESS:IMP-0120-probe2 documented commands execute with documented exit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
