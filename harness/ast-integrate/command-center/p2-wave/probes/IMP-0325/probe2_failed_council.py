#!/usr/bin/env python3
"""Probe 2: failed-council fixture + spec-11312 missing-artifact gate.

Independent of probe 1's TSV: invokes the live CLI as a subprocess and checks
(1) failed council is non-zero AND the success sentinel is absent from the
artifact; (2) a run that writes no artifact does not exit 0; (3) the happy
control still writes the sentinel and uses the documented run-success code.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "council" / "cli"))

import exit_codes as EC  # noqa: E402
from runtime import COUNCIL_SUCCESS_SENTINEL  # noqa: E402

UNIT = "IMP-0325"
CLI = REPO / "tools/council/cli/main.py"
FIX = HERE / "fixtures"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def invoke(args: list[str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        ["python3", "-B", str(CLI), *args],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0325-probe2-") as tmp:
        tmp_path = Path(tmp)
        failed_out = tmp_path / "failed.json"
        nowrite_out = tmp_path / "nowrite.json"
        happy_out = tmp_path / "happy.json"

        failed = invoke(
            [
                "run",
                "--spec",
                str(FIX / "failed-council.json"),
                "--out",
                str(failed_out),
            ]
        )
        nowrite = invoke(
            [
                "run",
                "--spec",
                str(FIX / "no-write.json"),
                "--out",
                str(nowrite_out),
            ]
        )
        happy = invoke(
            [
                "run",
                "--spec",
                str(FIX / "happy.json"),
                "--out",
                str(happy_out),
            ]
        )

        failed_text = failed_out.read_text(encoding="utf-8") if failed_out.is_file() else ""
        payload = {
            "probe": "probe2-failed-council-and-11312",
            "unit_id": UNIT,
            "failed_council": {
                "exit_code": failed.returncode,
                "artifact_present": failed_out.is_file(),
                "artifact_bytes": failed_out.stat().st_size if failed_out.is_file() else 0,
                "success_sentinel_present": COUNCIL_SUCCESS_SENTINEL in failed_text,
                "stdout_has_sentinel": COUNCIL_SUCCESS_SENTINEL in (failed.stdout or ""),
            },
            "no_write": {
                "exit_code": nowrite.returncode,
                "artifact_present": nowrite_out.is_file(),
            },
            "happy_control": {
                "exit_code": happy.returncode,
                "artifact_present": happy_out.is_file(),
                "success_sentinel_present": (
                    COUNCIL_SUCCESS_SENTINEL in happy_out.read_text(encoding="utf-8")
                    if happy_out.is_file()
                    else False
                ),
            },
        }
        print(json.dumps(payload, sort_keys=True))

        if failed.returncode == 0:
            return fail("failed-council exited 0")
        if failed.returncode != EC.EXIT_COUNCIL_FAILED:
            return fail(f"failed-council exit={failed.returncode} want={EC.EXIT_COUNCIL_FAILED}")
        if failed.returncode == EC.EXIT_RUN_OK:
            return fail("failed-council used the run-success code")
        if not failed_out.is_file():
            return fail("failed-council wrote no artifact to inspect for sentinel absence")
        if COUNCIL_SUCCESS_SENTINEL in failed_text:
            return fail("failed-council artifact contains SUCCESS:COUNCIL")
        if "SUCCESS:COUNCIL" in (failed.stdout or "") + (failed.stderr or ""):
            return fail("failed-council printed SUCCESS:COUNCIL")

        if nowrite.returncode == 0:
            return fail("no-write run exited 0 (spec 11312)")
        if nowrite.returncode != EC.EXIT_MISSING_ARTIFACT:
            return fail(f"no-write exit={nowrite.returncode} want={EC.EXIT_MISSING_ARTIFACT}")
        if nowrite_out.is_file() and nowrite_out.stat().st_size > 0:
            return fail("no-write run left a non-empty artifact")

        if happy.returncode != EC.EXIT_RUN_OK:
            return fail(f"happy control exit={happy.returncode} want={EC.EXIT_RUN_OK}")
        if not happy_out.is_file() or happy_out.stat().st_size <= 0:
            return fail("happy control wrote no artifact")
        if COUNCIL_SUCCESS_SENTINEL not in happy_out.read_text(encoding="utf-8"):
            return fail("happy control missing SUCCESS:COUNCIL")

        print(
            f"failed_exit={failed.returncode} sentinel_absent=True "
            f"no_write_exit={nowrite.returncode} happy_exit={happy.returncode}"
        )
        print(f"SUCCESS:{UNIT}-probe2 failed-council non-zero + 11312 missing-artifact")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
