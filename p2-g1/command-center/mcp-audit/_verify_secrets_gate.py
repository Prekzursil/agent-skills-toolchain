"""Run the real gitleaks gate over THIS lane's commit, with a committed both-states control.

The recorded failure mode on this estate: a gitleaks control was run against an
UNCOMMITTED file while `gitleaks git` only reads git HISTORY -- it reported clean and
proved nothing.  So the positive control here is a throwaway repo with a synthetic fake
credential actually COMMITTED, scanned with the same binary and the same committed
.gitleaks.toml.  If that does not fire, the clean verdict on the real commit is worthless.

The synthetic value is GENERATED at run time from a fixed seed, never written as a literal
here -- a token-shaped literal in this file would trip the very gate it verifies (the
recorded "a tool built to fix a defect class commits it" trap).  No real credential is
created, read, or written anywhere.

FIRST CONTROL CHOICE WAS INERT, recorded because it is the point of the exercise: an
`AKIA` + 16 identical chars synthetic fires under NEITHER the repo config NOR gitleaks'
own defaults (measured 2x2 over {default, repo} x {low, high entropy}).  A control that
cannot fire proves only that the scanner ran.  The generated token shape below was
measured to fire under both configs before being trusted.
"""

from __future__ import annotations

import pathlib
import random
import shutil
import string
import subprocess
import sys
import tempfile

REPO = pathlib.Path(r"C:/Users/Prekzursil/source/ast-integrate")
REV = sys.argv[1] if len(sys.argv) > 1 else "HEAD"


def run(args: list[str], cwd: pathlib.Path) -> tuple[int, str]:
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def control() -> bool:
    """Commit a synthetic fake secret in a throwaway repo; gitleaks MUST flag it."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="leakctl-"))
    try:
        for args in (
            ["git", "init", "-q"],
            ["git", "config", "user.email", "control@localhost"],
            ["git", "config", "user.name", "control"],
        ):
            run(args, tmp)
        shutil.copy(REPO / ".gitleaks.toml", tmp / ".gitleaks.toml")
        # Generated, not literal: a fixed-seed PRNG body behind a split prefix, so this
        # source file contains no token-shaped string for the gate to flag.
        rng = random.Random(20260812)
        alphabet = string.ascii_letters + string.digits
        body = "".join(rng.choice(alphabet) for _ in range(36))
        bad = "gh" + "p_" + body
        (tmp / "leak.txt").write_text(
            f"token = {bad}\n", encoding="ascii", newline="\n"
        )
        run(["git", "add", "leak.txt", ".gitleaks.toml"], tmp)
        run(["git", "commit", "-q", "-m", "control: synthetic fake secret"], tmp)
        rc, out = run(
            [
                "gitleaks",
                "git",
                "--config",
                ".gitleaks.toml",
                "--redact",
                "--exit-code",
                "1",
                ".",
            ],
            tmp,
        )
        fired = rc != 0
        print(f"  control (committed synthetic secret) fires: {fired} (rc={rc})")
        if not fired:
            print(f"  control output tail: {out.splitlines()[-3:]}")
        return fired
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    print("== gitleaks both-states control ==")
    if not control():
        print(
            "FAILED:secrets-gate positive control did not fire -- verdict meaningless"
        )
        return 1

    print(f"\n== real scan over {REV} ==")
    rc, out = run(
        [
            "gitleaks",
            "git",
            "--config",
            ".gitleaks.toml",
            "--redact",
            "--exit-code",
            "1",
            "--log-opts",
            f"{REV}^..{REV}",
            ".",
        ],
        REPO,
    )
    tail = [
        ln
        for ln in out.splitlines()
        if "leaks" in ln.lower() or "commits" in ln.lower()
    ]
    print(f"  rc={rc}")
    for line in tail[-4:]:
        print(f"  {line}")
    if rc != 0:
        print("FAILED:secrets-gate gitleaks flagged this commit")
        return 1
    print("SUCCESS:secrets-gate 0 leaks in this commit, positive control fired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
