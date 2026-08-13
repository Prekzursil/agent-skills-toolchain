#!/usr/bin/env python3
"""Hold THIS round's own commit to the claim it just shipped about line endings.

Round 4's headline is "every blob this lane committed -- .py, .md and .json alike -- is 0
CRLF".  The blob gate only inspects `.py`, so on its own it cannot support that sentence:
the two file types the false claim was ABOUT would go unchecked.  This walks every path in
the commit, with a positive control so a clean sweep is not just a silent reader.

Run::  python _r4_selfcheck.py [rev]   ->  exit 0 only if every blob is 0 CRLF AND the
control fires on a blob that really is CRLF.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
CTRL = "command-center/ssot/salvaged-from-scratch/_crlf_control_repo/known_crlf.md"


def blob(rev: str, path: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{rev}:{path}"], cwd=REPO, capture_output=True, check=True
    ).stdout


def main(argv: list[str]) -> int:
    rev = argv[0] if argv else "HEAD"
    paths = [
        p
        for p in subprocess.run(
            ["git", "show", "--stat", "--name-only", "--format=", rev],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
        if p.strip()
    ]
    if not paths:
        print(f"FAILED:r4-selfcheck no paths in {rev} (fail closed)")
        return 1

    print(f"== every blob in {rev}, by extension ==")
    bad = []
    for p in sorted(paths):
        b = blob(rev, p)
        crlf = b.count(b"\r\n")
        if crlf:
            bad.append(p)
        lines = b.count(b"\n")
        print(
            f"  {'BAD' if crlf else 'ok '} crlf={crlf:5}  lines={lines:5}  {p}"
        )

    # FAIL CLOSED when the control is ABSENT.  This used to leave ``fired = None`` and fall
    # through to ``fired is False`` -> False, so deleting the fixture would have turned a
    # proven sweep into an unproven one that still printed "control fired" in its marker.
    # "Control missing" and "control passed" must never be the same outcome; that identity
    # is the single most expensive failure shape in this repo's ledger.
    if not (REPO / CTRL).exists():
        print(f"FAILED:r4-selfcheck positive control missing at {CTRL} (fail closed)")
        return 1
    fired = blob("HEAD", CTRL).count(b"\r\n") > 0
    print(f"  positive control (a blob that IS CRLF) fires: {fired}")
    if bad or fired is False:
        print(f"FAILED:r4-selfcheck crlf_blobs={bad} control_fired={fired}")
        return 1
    print(f"SUCCESS:r4-selfcheck {len(paths)}/{len(paths)} blobs 0 CRLF, control fired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
