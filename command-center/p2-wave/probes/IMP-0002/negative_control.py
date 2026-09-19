#!/usr/bin/env python3
"""IMP-0002 negative control: real mtimes → digests diverge / pytest goes red path."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent


def main() -> int:
    lines = [
        "NEGATIVE CONTROL: --use-real-mtimes breaks determinism",
        "NEGATIVE-CONTROL-BEGIN:IMP-0002",
    ]
    # Focused pytest node for the negative control.
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        str(
            REPO
            / "tools/plugin/tests/test_pack_determinism.py::test_real_mtimes_breaks_determinism"
        ),
        "--tb=short",
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    lines.append(f"pytest_exit={proc.returncode}")
    lines.append("pytest_output_begin")
    lines.append(out[-4000:])
    lines.append("pytest_output_end")
    fired = (
        proc.returncode == 0
    )  # test asserts digests diverge → PASS means control fired
    # Also run the positive determinism test to show good state stays green.
    cmd2 = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        str(
            REPO
            / "tools/plugin/tests/test_pack_determinism.py::test_two_builds_identical"
        ),
        "--tb=line",
    ]
    proc2 = subprocess.run(
        cmd2,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out2 = (proc2.stdout or "") + (proc2.stderr or "")
    lines.append(f"good_state_pytest_exit={proc2.returncode}")
    lines.append(out2[-2000:])
    silent_good = proc2.returncode == 0
    ok = fired and silent_good
    meas = {
        "fired_on_bad_state": fired,
        "silent_on_good_state": silent_good,
        "bad_state_exit": proc.returncode,
        "good_state_exit": proc2.returncode,
        "control_passed": ok,
    }
    (PROBE / "negative-control-measurement.json").write_text(
        json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines.append(json.dumps(meas, indent=2, sort_keys=True))
    lines.append("NEGATIVE-CONTROL-COMPLETE:IMP-0002")
    lines.append(
        "SUCCESS:IMP-0002-negative-control"
        if ok
        else "FAILED:IMP-0002-negative-control"
    )
    raw = "\n".join(lines) + "\n"
    (PROBE / "negative-control.raw.txt").write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
