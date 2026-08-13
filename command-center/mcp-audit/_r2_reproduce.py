#!/usr/bin/env python3
"""Both-states reproduction of the two defects the round-1 verifier CONFIRMED.

A fix with no reproduction is a guess -- and a reproduction that reads the WORKING TREE
stops reproducing the moment the fix lands, which makes it a one-shot note rather than
evidence.  So each defect is measured twice, against two states that cannot drift:

  BEFORE  the round-1 COMMITTED BLOB (``git show b9dce830:<path>``).  Frozen; the defect
          must still be visible there forever.  If it is not, this detector is broken.
  AFTER   the current working tree.  The defect must be absent.

Requiring BOTH directions is what makes this a control rather than a claim: a script that
only checked AFTER would print a clean bill of health if it were pointed at the wrong
field, the wrong file, or nothing at all.

  D1  ``disposition.json`` documented ``call_verified`` as "real initialize+tools/list, OR
      a real in-session tool call" while computing it from the handshake alone, so rows
      existed with ``call_verified: false`` beside a non-null ``s4_executed``.
  D2  the producer was claimed to emit "exactly the four fields ``mcpctl.matrix.Row``
      leaves null".  mcpctl's fourth is ``rss_bytes``; the producer emitted
      ``working_set_bytes``.  Three of four by name.

  D3 (the ruff-count disclosure) is not reproducible by construction -- the number moves
     as sibling lanes commit, which IS the defect.  It is measured by _r2_ruff_census.py.

Run::  python _r2_reproduce.py   ->  exit 0 only when BEFORE shows both defects and AFTER
shows neither.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
ROUND1 = "b9dce830"  # the commit that shipped the round-1 artifacts
sys.path.insert(0, str(REPO / "tools" / "mcpctl"))

from mcpctl.matrix import Liveness  # noqa: E402

LIVENESS_FIELDS = {f.name for f in dataclasses.fields(Liveness)}


def blob(rev: str, path: str) -> dict:
    """Read a committed blob.  ``git show`` returns the stored bytes (0 CRLF)."""
    out = subprocess.run(
        ["git", "show", f"{rev}:{path}"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)


def d1_contradictions(disp: dict) -> list[str]:
    """Rows asserting no real call while carrying in-session evidence of one."""
    return [
        r["name"] for r in disp["rows"] if not r["call_verified"] and r["s4_executed"]
    ]


def d2_missing(matrix: dict) -> list[str]:
    """Liveness field names the producer does not emit."""
    emitted = set(matrix["rows"][0].keys())
    return sorted(LIVENESS_FIELDS - emitted)


def main() -> int:
    failures: list[str] = []

    print("== D1 call_verified self-contradiction ==")
    before = blob(ROUND1, "command-center/mcp-audit/disposition.json")
    after = json.loads((HERE / "disposition.json").read_text(encoding="utf-8"))
    b_rows, a_rows = d1_contradictions(before), d1_contradictions(after)
    print(f"  BEFORE {ROUND1}: legend={before['signals']['call_verified'][:52]!r}...")
    print(f"  BEFORE contradictory rows ({len(b_rows)}): {b_rows}")
    print(
        f"  BEFORE call_verified={sum(1 for r in before['rows'] if r['call_verified'])}"
        f" of {len(before['rows'])}, while the prose claimed 21"
    )
    print(f"  AFTER  contradictory rows ({len(a_rows)}): {a_rows}")
    print(
        f"  AFTER  call_verified={sum(1 for r in after['rows'] if r['call_verified'])}"
        f" of {len(after['rows'])}"
    )
    if not b_rows:
        failures.append("D1-before-shows-no-defect (detector broken)")
    if a_rows:
        failures.append("D1-after-still-defective")

    print("\n== D2 'exactly the four fields' overclaim ==")
    b_matrix = blob(ROUND1, "command-center/mcp-audit/capability-matrix.json")
    a_matrix = json.loads(
        (HERE / "capability-matrix-r2.json").read_text(encoding="utf-8")
    )
    b_missing, a_missing = d2_missing(b_matrix), d2_missing(a_matrix)
    print(f"  mcpctl Liveness fields : {sorted(LIVENESS_FIELDS)}")
    print(f"  BEFORE missing by name : {b_missing}")
    print(f"  AFTER  missing by name : {a_missing}")
    if b_missing != ["rss_bytes"]:
        failures.append(f"D2-before-unexpected {b_missing} (detector broken)")
    if a_missing:
        failures.append(f"D2-after-still-missing {a_missing}")

    if failures:
        print(f"\nFAILED:r2-reproduce {failures}")
        return 1
    print("\nSUCCESS:r2-reproduce both defects present in the round-1 blob, absent now")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
