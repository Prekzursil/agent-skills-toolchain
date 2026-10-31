r"""FRESH-CLONE verification of the CASUALTY integration.

Working-tree green != clone green. Measured on this program: a tree reporting 3,910 passed
produced 31 collection errors from a fresh clone of the same commit. This lane's own round 2
found the sharper version -- a Windows checkout converted two LF blobs to CRLF and broke both
published digests, while the worktree looked fine.

So: clone HEAD into a throwaway directory and run the integration there. The clone is the
bytes a reviewer (and CI) actually gets.

  1. the lane's pytest suite
  2. casualty_guard.py in STRICT mode (its P1 blob signal must resolve in the clone too)
  3. suitefloor --suite casualty

`_`-prefixed on purpose: it is a one-off verification probe, not a shipped instrument, so the
guard's inventory (which walks non-underscore *.py) correctly ignores it.

Terminal: SUCCESS:int-freshclone / FAILED:int-freshclone <failing step>
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def run(argv: list[str], cwd: Path, timeout: int = 900) -> tuple[int, str]:
    proc = subprocess.run(
        argv, cwd=str(cwd), capture_output=True, text=True, check=False, timeout=timeout
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def main() -> int:
    head = run(["git", "rev-parse", "HEAD"], REPO)[1]
    tmp = Path(tempfile.mkdtemp(prefix="casualty_freshclone_"))
    clone = tmp / "clone"
    failures: list[str] = []
    try:
        rc, out = run(
            ["git", "clone", "--no-hardlinks", "--quiet", str(REPO), str(clone)], REPO
        )
        if rc != 0:
            print(f"FAILED:int-freshclone clone did not complete: {out[-400:]}")
            return 1
        rc, at = run(["git", "rev-parse", "HEAD"], clone)
        print(f"  clone HEAD : {at}")
        print(f"  repo  HEAD : {head}   SAME={at == head}")
        if at != head:
            print("FAILED:int-freshclone the clone is not at the commit under test")
            return 1

        steps = [
            (
                "pytest",
                [sys.executable, "-m", "pytest", "command-center/casualty/tests", "-q"],
                0,
            ),
            (
                "guard-strict",
                [sys.executable, "command-center/casualty/casualty_guard.py"],
                0,
            ),
            (
                "suitefloor",
                [
                    sys.executable,
                    "tools/measure-guard/suitefloor.py",
                    "--suite",
                    "casualty",
                ],
                0,
            ),
        ]
        for name, argv, want in steps:
            rc, out = run(argv, clone)
            tail = out.strip().splitlines()[-1] if out.strip() else "(no output)"
            ok = rc == want
            print(f"  {'PASS' if ok else 'FAIL'} {name:13s} rc={rc}  {tail}")
            if not ok:
                failures.append(name)
                print("    ---- output ----")
                for line in out.strip().splitlines()[-25:]:
                    print(f"    {line}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        print(f"FAILED:int-freshclone {','.join(failures)}")
        return 1
    print(
        "SUCCESS:int-freshclone the integration holds from a clone, not just this worktree"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
