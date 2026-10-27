#!/usr/bin/env python3
"""IMP-0055 probe2 (verifier): the SAME commands observed through bash ($?) and
pwsh7 ($LASTEXITCODE) yield the same integers — codes survive the shell
boundary. NEGATIVE CONTROL: a failing command never exits 0 in either shell."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.exit_codes import BLOCKED_NEEDS_OWNER, VALIDATION_FAILED, cli_argv  # noqa: E402


def via_bash(argv):
    bash = shutil.which("bash")
    Q = chr(39)
    quoted = " ".join(Q + a.replace(Q, Q + chr(92) + Q + Q) + Q for a in argv)
    p = subprocess.run([bash, "-c", quoted + "; exit $?"], capture_output=True, text=True, timeout=60, env=os.environ.copy())
    return p.returncode


def via_pwsh(argv):
    pwsh = shutil.which("pwsh") or shutil.which("pwsh.exe")
    Q = chr(39)
    quoted = "& " + " ".join(Q + a.replace(Q, Q + Q) + Q for a in argv)
    p = subprocess.run([pwsh, "-NoProfile", "-Command", quoted + "; exit $LASTEXITCODE"], capture_output=True, text=True, timeout=60, env=os.environ.copy())
    return p.returncode


def main() -> int:
    import tempfile
    cases = []
    with tempfile.TemporaryDirectory() as td:
        missing = str(Path(td) / "missing.json")
        cases = [
            (cli_argv("not-a-verb"), 2),
            (cli_argv("preflight", "--require-file", missing), 10),
            (cli_argv("check", "--file", missing), VALIDATION_FAILED),
            (cli_argv("owner-gate", "--candidate", "not-installed-pkg"), BLOCKED_NEEDS_OWNER),
        ]
        rows = []
        checks = {"all_shell_pairs_agree": True, "no_failure_exits_zero": True}
        for argv, expected in cases:
            b = via_bash(argv)
            w = via_pwsh(argv)
            rows.append({"expected": expected, "bash": b, "pwsh": w})
            if not (b == w == expected):
                checks["all_shell_pairs_agree"] = False
            if expected != 0 and (b == 0 or w == 0):
                checks["no_failure_exits_zero"] = False
        print(json.dumps({"rows": rows, "checks": checks}))
        if not all(checks.values()):
            print("FAILED:IMP-0055-probe2 cross-shell disagreement")
            return 1
        print("SUCCESS:IMP-0055-probe2 bash and pwsh observe identical exit codes for every class")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
