#!/usr/bin/env python3
"""INTEGRATE round 2 -- the register survives a clone, and still gates there.

The finding this round acts on is that *a register only the author can read
routes nothing*. That makes it the one claim this lane may not assert about its
own artifact without proving it. So: clone the commit shallow, and check the
register from OUTSIDE the working tree that produced it.

  arm 1  depth-1 clone at the commit -> the register file is present, the new
         arm is COLLECTED (not silently deselected), and the suite is GREEN
  arm 2  the SAME clone with the register deleted -> the arm goes RED

Arm 2 is what makes arm 1 worth anything. A clone that merely runs the suite
green would be consistent with the gate being absent from the clone entirely;
only the asymmetry shows the gate is live there. Same reasoning as the
three-state probe, applied to a different machine's view of the repo.

depth 1 is deliberate: the hosting job's `actions/checkout` in
`.github/workflows/quality.yml` has no `with:` block, so its `fetch-depth`
defaults to 1. An arm that needed history would fail closed on every CI run.

ON-DEMAND ONLY -- it clones ~11k files. Not a CI gate.

Terminal state per AGENTS.md 4: SUCCESS:docs-i2-clone / FAILED:docs-i2-clone
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REV = sys.argv[1] if len(sys.argv) > 1 else "HEAD"

SUITE = "ci/tests/test_command_doc_promises.py"
ARM = "test_every_dead_classification_is_routed_to_a_register_row"
REGISTER = "docs/DEAD-COMMAND-PROMISES.md"


def git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
    )


def pytest_in(clone: Path, *extra: str) -> tuple[int, str]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            f"{SUITE}::{ARM}",
            "-p",
            "no:cacheprovider",
            *extra,
        ],
        cwd=clone,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    want = git("rev-parse", REV, cwd=REPO).stdout.strip()
    tmp = Path(tempfile.mkdtemp(prefix="docs-i2-clone-"))
    clone = tmp / "repo"
    problems: list[str] = []
    facts: dict[str, object] = {}
    try:
        made = git(
            "clone",
            "--depth",
            "1",
            "--no-local",
            "--branch",
            "main",
            REPO.as_uri(),
            str(clone),
            cwd=tmp,
        )
        if made.returncode != 0:
            print(
                f"FAILED:docs-i2-clone clone rc={made.returncode} {made.stderr[-300:]}"
            )
            return 1

        head = git("rev-parse", "HEAD", cwd=clone).stdout.strip()
        depth = git("rev-list", "--count", "HEAD", cwd=clone).stdout.strip()
        shallow = (clone / ".git" / "shallow").exists()
        facts |= {
            "clone_head": head[:8],
            "want": want[:8],
            "shallow": shallow,
            "depth": depth,
        }

        # Preconditions: without these the arms below measure the wrong tree.
        if head != want:
            problems.append(f"clone HEAD {head[:8]} != {want[:8]}")
        if not shallow or depth != "1":
            problems.append(f"clone is not shallow (shallow={shallow} depth={depth})")

        present = (clone / REGISTER).is_file()
        facts["register_in_clone"] = present
        if not present:
            problems.append(
                f"{REGISTER} is ABSENT from the clone -- it routes nothing for anyone"
            )

        collected = pytest_in(clone, "--collect-only", "-q")
        facts["arm_collected"] = ARM in collected[1]
        if not facts["arm_collected"]:
            problems.append("the new arm is not collected in the clone")

        green_rc, _ = pytest_in(clone, "-q")
        facts["arm_rc_present"] = green_rc

        (clone / REGISTER).unlink()
        red_rc, red_out = pytest_in(clone, "-q")
        facts["arm_rc_deleted"] = red_rc
        facts["red_names_token"] = "scripts/claw.js" in red_out

        if green_rc != 0:
            problems.append(f"arm 1: the suite is RED in a clean clone (rc={green_rc})")
        if red_rc == 0:
            problems.append("arm 2: deleting the register did NOT turn the clone red")
        elif not facts["red_names_token"]:
            problems.append("arm 2 went red without naming the unrouted token")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    for key, value in facts.items():
        print(f"   {key} = {value}")
    if problems:
        print("FAILED:docs-i2-clone " + " | ".join(problems))
        return 1
    print(
        f"SUCCESS:docs-i2-clone rev={want[:8]} shallow=True register_in_clone=True "
        f"arm_collected=True present_rc=0 deleted_rc={facts['arm_rc_deleted']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
