"""BUILD-R1 probe: the two portability questions _i1_ci_portability.py did NOT answer.

WHY THIS EXISTS ALONGSIDE _i1_ci_portability.py (read that first -- it is the primary
instrument and this does not replace it).  _i1 measures 27 scripts x {real HOME, empty HOME}
on ONE platform, and it runs ``rule_audit.py`` and ``r2_pathrefs.py`` with ``--self-test``.
Two gaps remain, and both are load-bearing for the CI plan:

  GAP 1  BARE argv.  ``--self-test`` runs the detector controls, which are tree-independent
         by construction.  The CI plan has to decide whether the REAL sweep can also run,
         and that is a different invocation with a different exit code (bare r2_pathrefs is
         rc=2 on this box, not rc=0).  Specifically it tests the FAIL-OPEN hypothesis:
         rule_audit.main() fails closed only on an empty *repo* tree, so with no ~/.claude
         the ``live`` tree is empty and it may still exit 0 while measuring nothing about
         live -- the exact shape _i1's own docstring warns about.

  GAP 2  POSIX.  _i1 runs on whichever interpreter invokes it; it has only ever been run on
         Windows.  GitHub Actions is ubuntu-latest.  The sibling mcp-audit lane found 4 real
         Windows-only failures this way, so POSIX is measured, not assumed.

Run BOTH, same script, two interpreters::

    python  docs/rule-audit/_b3_portability.py --tag win-bare-nohome
    python3 docs/rule-audit/_b3_portability.py --tag linux-bare-nohome   (under WSL Ubuntu)

HOME is redirected to a fresh empty temp dir, so ~/.claude is absent exactly as on a runner.
Nothing in the real HOME is read or written; the repo is not modified.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

# The invocations the CI plan is actually considering -- bare where _i1 used --self-test.
PLAN: list[tuple[str, list[str]]] = [
    ("rule_audit.py", []),
    ("rule_audit.py", ["--self-test"]),
    ("lazy_predict.py", []),
    ("r2_control_count_gate.py", []),
    ("r2_failclosed_mutation.py", []),
    ("r2_pathrefs.py", []),
    ("r2_pathrefs.py", ["--self-test"]),
    ("r3_corpus_parity_gate.py", []),
    ("r4_credential_rule_gate.py", []),
    ("r4_receipt_argv_gate.py", []),
]

TIMEOUT_SEC = 900


def marker_of(stdout: str) -> str:
    lines = [ln for ln in stdout.splitlines() if ln.strip()]
    for line in reversed(lines):
        if line.startswith(("SUCCESS:", "FAILED:")):
            return line.strip()[:160]
    return lines[-1].strip()[:160] if lines else "<no stdout>"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    args = ap.parse_args()

    results = []
    with tempfile.TemporaryDirectory(prefix="rule-audit-nohome-") as fake_home:
        env = dict(os.environ)
        env["HOME"] = fake_home
        env["USERPROFILE"] = fake_home
        env["PYTHONIOENCODING"] = "utf-8"
        # Path.home() prefers USERPROFILE on Windows and HOME on POSIX; HOMEDRIVE/HOMEPATH
        # would override USERPROFILE on Windows, so they must not survive.
        for stale in ("HOMEDRIVE", "HOMEPATH"):
            env.pop(stale, None)

        for name, argv in PLAN:
            started = time.monotonic()
            label = f"{name} {' '.join(argv)}".strip()
            rec: dict[str, object] = {"gate": name, "argv": argv, "label": label}
            try:
                proc = subprocess.run(
                    [sys.executable, str(HERE / name), *argv],
                    cwd=str(REPO),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=TIMEOUT_SEC,
                    env=env,
                )
                rec["returncode"] = proc.returncode
                rec["marker"] = marker_of(proc.stdout)
                rec["crashed"] = "Traceback" in proc.stderr
                rec["stderr_tail"] = proc.stderr[-400:]
            except subprocess.TimeoutExpired:
                rec["returncode"] = None
                rec["crashed"] = False
                rec["marker"] = f"<timeout {TIMEOUT_SEC}s>"
            rec["wall_sec"] = round(time.monotonic() - started, 1)
            print(
                f"{label:38} rc={rec.get('returncode')} "
                f"{rec['wall_sec']:>7}s  {rec['marker'][:90]}",
                flush=True,
            )
            results.append(rec)

    out = {
        "tag": args.tag,
        "platform": platform.system(),
        "python": sys.version.split()[0],
        "home": "fresh empty temp dir (no .claude) -- stands in for a CI runner",
        "results": results,
    }
    (HERE / f"_b3_portability.{args.tag}.json").write_text(
        json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"\nSUCCESS:b3-portability {len(results)} invocations on {out['platform']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
