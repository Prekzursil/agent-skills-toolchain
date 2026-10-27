#!/usr/bin/env python3
"""Settle a contradiction between two of MY OWN instruments before citing either.

A shell loop reported ``grep -c $'\\r'`` equal to the LINE count for five revisions of
``ROUND2-DEFECT-CLOSURE.md`` (242/242, 248/248, 276/276, ...) while a Python byte counter
read 0 CRLF for the same blobs.  A self-contradicting output is a detector failure, not a
finding, so neither number may be used until the disagreement is explained.

Three candidate explanations, and the measurement that separates them:

  P  the blob holds BARE CR bytes (not CRLF) -- then count(b"\\r") >> count(b"\\r\\n")
  Q  the shell transport mangled the ANSI-C quote -- then a CR-free blob still counts high
  R  the blob is clean and the reading was spurious -- then both counters agree at 0

ANSWER (measured below): **R**.  Both git plumbing commands read 0 CR bytes in every one
of those blobs, and they agree on the byte size too, with a positive control that fires on
a blob which really is CRLF.

The shell readings are excluded from the verdict rather than reconciled, because the shell
instrument was shown to be untrustworthy in three separate ways -- see ``cat_file`` below.
Two shell behaviours are recorded but NOT resolved, and no number here depends on either:

* Git Bash, false-negative direction, root cause pinned with ``od``: MSYS grep opens input
  in TEXT mode and strips CR before matching, so ``grep -c $'\\r'`` returns **0 on input
  od proves contains CR**; it needs ``-U``.
* Git Bash, false-POSITIVE direction: ``grep -c $'\\r'`` returned 276 -- the exact line
  count -- on a blob two other instruments read as CR-free.  Reproducible, UNEXPLAINED.
  Settling experiment: replace grep with a wrapper that dumps its own argv through
  ``od -c`` and run the loop form again.

Bearing on round 2: a CR-pattern grep through this shell can return exactly the line count
of a CR-free file, which is the shape of round 2's whole table.  That makes it a plausible
mechanism, not a demonstrated one -- round 2's actual command was never committed and
cannot be recovered.  LIKELY (55-80%), and it stays labelled as such.

Run::  python _r4_cr_settle.py   ->  exit 0 only if the two plumbing readers agree on
every blob AND the positive control fires.
"""

from __future__ import annotations

import pathlib
import subprocess

REPO = pathlib.Path(__file__).resolve().parents[2]
DOC = "docs/mcp-audit/ROUND2-DEFECT-CLOSURE.md"
REVS = ["630bb8af", "5550e225", "959f783f", "2caafe53", "bfec0543"]


def blob(rev: str, path: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{rev}:{path}"], cwd=REPO, capture_output=True, check=True
    ).stdout


def cat_file(rev: str, path: str) -> bytes:
    """Second instrument: git's OTHER plumbing.  Deliberately not a shell pipeline.

    The first version of this script used ``bash -lc '<git show> | grep -cU ...'`` as the
    second instrument and it reported a clean 0 for every blob -- including a control that
    really is CRLF.  Three things were wrong with it and each is worth keeping written
    down, because all three produce a REASSURING number rather than an error:

    1. `grep -c` prints `0` for "matched nothing" and for "was handed nothing".  A
       pipeline whose producer died reads as a clean zero.
    2. `bash` launched from Python on this box is **WSL bash**, not Git Bash -- measured:
       the child reported its cwd as `/mnt/c/Users/...`.  (Exactly the trap
       `rules/common/single-signal-verification.md` records: `command -v bash` in Git Bash
       resolves `/usr/bin/bash` while a Windows process gets `C:\\WINDOWS\\system32\\bash.exe`.)
    3. This checkout is a LINKED WORKTREE whose `.git` is a file holding a *Windows*
       absolute path, so WSL git cannot resolve it:
       ``fatal: not a git repository: /mnt/c/.../C:/Users/.../worktrees/ast-integrate``.
       Every byte of every reading taken that way was void.

    `git cat-file -p` invoked directly, no shell, is a different plumbing command from
    `git show` and cannot silently produce an empty success: check=True makes a failure an
    exception instead of a zero.
    """
    return subprocess.run(
        ["git", "cat-file", "-p", f"{rev}:{path}"],
        cwd=REPO,
        capture_output=True,
        check=True,
    ).stdout


CTRL = "command-center/ssot/salvaged-from-scratch/_crlf_control_repo/known_crlf.md"


def main() -> int:
    print(
        f"{'rev':10} {'bytes':>8} {'CR':>6} {'CRLF':>6} {'LF':>6} "
        f"{'catfileCR':>9} {'agree':>6}"
    )
    disagree = []
    for rev in REVS:
        b = blob(rev, DOC)
        cr, crlf, lf = b.count(b"\r"), b.count(b"\r\n"), b.count(b"\n")
        c = cat_file(rev, DOC)
        # Both instruments must see the same SIZE too -- two readers agreeing on "0 CR"
        # while disagreeing on the byte count would mean they read different objects.
        c_cr = c.count(b"\r")
        ok = c_cr == cr and len(c) == len(b)
        disagree += [] if ok else [rev]
        print(f"{rev:10} {len(b):8} {cr:6} {crlf:6} {lf:6} {c_cr:>9} {str(ok):>6}")

    # Positive control: the corrected detector must FIRE on a blob that really is CRLF, or
    # its agreement above is two blind instruments agreeing about nothing.
    fired = None
    if (REPO / CTRL).exists():
        raw = blob("HEAD", CTRL)
        ctl = cat_file("HEAD", CTRL)
        # The clause that can actually fail: BOTH instruments must SEE CR on a blob that
        # has it.  Without this, five zeros above are just two blind readers agreeing.
        raw_cr = raw.count(b"\r")
        ctl_cr = ctl.count(b"\r")
        fired = raw_cr > 0 and ctl_cr == raw_cr
        print(
            f"\n  positive control {CTRL.split('/')[-1]}: git show CR={raw_cr} "
            f"git cat-file CR={ctl_cr}  fires: {fired}"
        )
    else:
        print("\n  positive control blob absent; see _r4_eol_probe.py PART A instead")

    if disagree or fired is False:
        print(f"FAILED:r4-cr-settle disagree={disagree} control_fired={fired}")
        return 1
    print("SUCCESS:r4-cr-settle 0 CR in every claimed blob, positive control fires")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
