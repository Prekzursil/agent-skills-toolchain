"""Round 7: is the pinned-count probe really unrunnable in CI, or just unwired?

Round 6 concluded "NO -- structurally unrunnable there" and declined to wire the
probe, on the ground that the hosting job's checkout is shallow. That premise is
correct; the conclusion drawn from it is not. This is the two-arm control that
separates them, on ONE clone, changing ONE variable:

    arm 1  depth-1 clone (what actions/checkout gives that job today) -> must FAIL
    arm 2  the SAME clone after `fetch --unshallow` (== fetch-depth: 0) -> must PASS

A control that passed in both arms would prove only that the probe runs; a
control that failed in both would prove no remedy exists. The two arms must
DIFFER, and the script fails if they do not.

ON-DEMAND ONLY -- it clones the repo (~11k files) and takes minutes. It is not,
and must not become, a CI gate: see docs/_LANE-DOCS-BUILD-R7.md.

Terminal state: SUCCESS:docs-r7-shallow / FAILED:docs-r7-shallow <reason>
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROBE = "docs/_lane_docs_r6_pinned_counts.py"
PINNED = ("67137879", "5d573583")


def run(args: list[str], cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="do not delete the clone")
    ns = ap.parse_args()

    work = Path(tempfile.mkdtemp(prefix="docs-r7-shallow-"))
    clone = work / "shallow"
    try:
        rc, out = run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--no-single-branch",
                f"file:///{REPO.as_posix()}",
                str(clone),
            ],
            cwd=work,
        )
        if rc != 0:
            print(f"FAILED:docs-r7-shallow clone rc={rc} {out[-300:]}")
            return 1

        # --- precondition: the arm really IS shallow -------------------------
        # Without this, arm 1 failing proves nothing -- it could fail for any
        # unrelated reason and we would credit it to the checkout depth.
        if not (clone / ".git" / "shallow").exists():
            print("FAILED:docs-r7-shallow arm 1 is not actually a shallow clone")
            return 1
        rc, depth = run(["git", "rev-list", "--count", "HEAD"], cwd=clone)
        if depth.strip() != "1":
            print(f"FAILED:docs-r7-shallow arm 1 depth is {depth!r}, want 1")
            return 1
        for sha in PINNED:
            rc, _ = run(["git", "cat-file", "-t", sha], cwd=clone)
            if rc == 0:
                print(f"FAILED:docs-r7-shallow {sha} is present in a depth-1 clone")
                return 1

        # --- arm 1: shallow ---------------------------------------------------
        rc_shallow, out_shallow = run([sys.executable, PROBE], cwd=clone)

        # --- arm 2: the remedy 6 workflows in this repo already use ------------
        rc, out = run(["git", "fetch", "--unshallow"], cwd=clone)
        if rc != 0:
            print(f"FAILED:docs-r7-shallow unshallow rc={rc} {out[-300:]}")
            return 1
        if (clone / ".git" / "shallow").exists():
            print("FAILED:docs-r7-shallow still shallow after --unshallow")
            return 1
        rc_full, out_full = run([sys.executable, PROBE], cwd=clone)

        # --- the arms must differ --------------------------------------------
        if rc_shallow == 0:
            print(
                f"FAILED:docs-r7-shallow arm 1 PASSED; the premise is wrong: {out_shallow[-200:]}"
            )
            return 1
        if rc_full != 0:
            print(
                f"FAILED:docs-r7-shallow arm 2 failed; no remedy shown: {out_full[-300:]}"
            )
            return 1
        if "pre_fix=20/16 post_fix=19/15" not in out_full:
            print(
                f"FAILED:docs-r7-shallow arm 2 passed with unexpected counts: {out_full[-200:]}"
            )
            return 1

        print(
            "SUCCESS:docs-r7-shallow "
            f"arm1_shallow=rc{rc_shallow} arm2_unshallowed=rc{rc_full} arms_differ=True "
            "verdict=NOT-structurally-unrunnable-remedy-is-fetch-depth-0"
        )
        return 0
    finally:
        if not ns.keep:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
