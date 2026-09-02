"""LANE DOCS round 5 -- both-states control for the prose-path-claim arm.

A silence only counts as clean if the same probe FIRES against the known-broken state.
This feeds the SHIPPED predicate (imported from the gate, not re-implemented here -- a probe
that re-implements the gate can only agree with itself) two inputs:

  BROKEN  commands/sessions.md at blob 3bfb914d3881ffe736fb3ac093e6d155f0911192 -- the real
          committed pre-fix bytes, not a synthetic string. Pinned to an immutable blob sha
          rather than a moving HEAD, so a later commit cannot silently change what "broken"
          means.
  FIXED   the current working-tree file.

Expected: BROKEN fires exactly once at the Operator Notes bullet; FIXED is silent.
Identical counts in both states would mean the arm measures nothing.
"""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "ci" / "tests"))

from test_command_doc_promises import (  # noqa: E402
    _prose_path_claims_in_text,
    _tracked_paths,
)

PRE_FIX_BLOB = "3bfb914d3881ffe736fb3ac093e6d155f0911192"
OLD_SENTENCE = "the cost metrics emitted by `scripts/hooks/cost-tracker.js`"


def main() -> int:
    tracked = _tracked_paths()

    proc = subprocess.run(
        ["git", "cat-file", "-p", PRE_FIX_BLOB],
        cwd=REPO,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        print(
            f"FAILED:docs-r5-bothstates cannot read blob {PRE_FIX_BLOB}",
            file=sys.stderr,
        )
        return 1
    broken = proc.stdout.decode("utf-8")

    # Precondition: the blob really is the broken state. Without this the control could
    # be silently comparing the fixed file against itself.
    if OLD_SENTENCE not in broken:
        print(
            "FAILED:docs-r5-bothstates the pinned blob does not contain the pre-fix "
            "sentence -- wrong blob, so the control proves nothing",
            file=sys.stderr,
        )
        return 1

    fixed_path = REPO / "commands" / "sessions.md"
    # io.open(...).read() rather than Path.read_text(newline=): the newline= kwarg on
    # Path.read_text/write_text is Python 3.13+, and CI runs 3.11 (see b0e3bf98).
    fixed = io.open(fixed_path, encoding="utf-8", newline="").read()

    broken_hits = _prose_path_claims_in_text(broken, tracked)
    fixed_hits = _prose_path_claims_in_text(fixed, tracked)

    print(f"  blob CR count   : {broken.count(chr(13))}")
    print(f"  tree CR count   : {fixed.count(chr(13))}")
    print(f"  BROKEN hits     : {broken_hits}")
    print(f"  FIXED  hits     : {fixed_hits}")

    ok = len(broken_hits) == 1 and broken_hits[0][1] == "scripts/hooks/cost-tracker.js"
    ok = ok and fixed_hits == []
    if not ok:
        print(
            f"FAILED:docs-r5-bothstates broken={len(broken_hits)} fixed={len(fixed_hits)} "
            "(expected 1 and 0)",
            file=sys.stderr,
        )
        return 1

    print(
        f"SUCCESS:docs-r5-bothstates broken_state_fires={len(broken_hits)} "
        f"fixed_state_fires={len(fixed_hits)} blob={PRE_FIX_BLOB[:8]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
