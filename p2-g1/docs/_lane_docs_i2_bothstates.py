#!/usr/bin/env python3
"""INTEGRATE round 2 -- end-to-end proof that the routing gate is not a no-op.

The claim under test: `ci/tests/test_command_doc_promises.py` now FAILS if the
DOCS lane's two confirmed-dead published commands stop being routed to
`docs/DEAD-COMMAND-PROMISES.md`. A gate that has never gone red is
indistinguishable from a no-op, so this runs the SHIPPED test in three states:

  FIXED    the register as committed                       -> expect rc 0
  ABSENT   the register file moved away entirely           -> expect rc 1
  HOLLOWED the file present, its table rows deleted        -> expect rc 1

ABSENT and HOLLOWED are separated deliberately. They are different failures --
"nobody wrote the register" and "somebody emptied it" -- and a gate that only
catches the first is half a gate. Both are performed on the REAL file, not on a
synthetic string, so the arms are proven against the bytes CI reads.

WHY IT INVOKES pytest RATHER THAN THE PREDICATE
-----------------------------------------------
A probe that re-implements the gate's logic can only ever agree with itself.
This one shells out to the shipped test, so what goes red is the thing wired
into `.github/workflows/quality.yml:1503`, not a copy of it.

CONTROLS
  C1  precondition: the register exists and parses to >= 2 rows before anything
      is touched. Without it the "broken" arms could be comparing an already
      empty file against itself.
  C2  the FIXED arm must be GREEN. Red in every state measures nothing.
  C3  each broken arm's output must NAME the unrouted token -- an rc of 1 from
      an unrelated failure elsewhere in the suite would otherwise read as proof.
  C4  restore is verified by sha256, not by assuming the write worked.

Terminal state per AGENTS.md 4: SUCCESS:docs-i2-bothstates / FAILED:docs-i2-bothstates
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REGISTER = REPO / "docs" / "DEAD-COMMAND-PROMISES.md"
SUITE = "ci/tests/test_command_doc_promises.py"
ARM = "test_every_dead_classification_is_routed_to_a_register_row"
EXPECT_NAMED = "scripts/claw.js"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def run_arm() -> tuple[int, str]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            f"{SUITE}::{ARM}",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


def hollow(text: str) -> str:
    """Drop every table row, keeping the prose. 'Somebody emptied it'."""
    kept = [ln for ln in text.split("\n") if not ln.lstrip().startswith("| `scripts/")]
    return "\n".join(kept)


def main() -> int:
    if not REGISTER.is_file():
        print("FAILED:docs-i2-bothstates the register does not exist to test")
        return 1

    original = REGISTER.read_bytes()
    before = sha(original)
    text = original.decode("utf-8")

    # C1 -- the shape must be there before we break it.
    rows = [ln for ln in text.split("\n") if ln.lstrip().startswith("| `scripts/")]
    if len(rows) < 2:
        print(f"FAILED:docs-i2-bothstates C1 only {len(rows)} register rows found")
        return 1

    results: dict[str, tuple[int, bool]] = {}
    try:
        fixed_rc, fixed_out = run_arm()
        results["FIXED"] = (fixed_rc, EXPECT_NAMED in fixed_out)

        REGISTER.unlink()
        absent_rc, absent_out = run_arm()
        results["ABSENT"] = (absent_rc, EXPECT_NAMED in absent_out)

        REGISTER.write_bytes(hollow(text).encode("utf-8"))
        hollow_rc, hollow_out = run_arm()
        results["HOLLOWED"] = (hollow_rc, EXPECT_NAMED in hollow_out)
    finally:
        REGISTER.write_bytes(original)

    after = sha(REGISTER.read_bytes())
    restored = after == before

    for state, (rc, named) in results.items():
        print(f"   {state:<9} rc={rc}  names_the_unrouted_token={named}")
    print(f"   restore   before={before} after={after} ok={restored}")

    problems: list[str] = []
    if results["FIXED"][0] != 0:
        problems.append("C2 the FIXED arm is not green, so red proves nothing")
    for state in ("ABSENT", "HOLLOWED"):
        rc, named = results[state]
        if rc == 0:
            problems.append(f"{state} did not fire: the gate tolerates it")
        elif not named:
            problems.append(f"C3 {state} went red without naming {EXPECT_NAMED}")
    if not restored:
        problems.append("C4 the register was NOT restored byte-for-byte")

    if problems:
        print("FAILED:docs-i2-bothstates " + " | ".join(problems))
        return 1
    print(
        "SUCCESS:docs-i2-bothstates controls=C1,C2,C3,C4-ok "
        f"fixed_rc=0 absent_rc={results['ABSENT'][0]} "
        f"hollowed_rc={results['HOLLOWED'][0]} restored=True"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
