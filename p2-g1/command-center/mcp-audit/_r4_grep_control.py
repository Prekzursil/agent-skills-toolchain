#!/usr/bin/env python3
"""What did round 2's CRLF detector actually measure?  Settle it with a control.

The verifier left this UNVERIFIED (20-55%): *"whether round 2's numbers came from
counting the worktree or from counting lines"*.  Neither, it turns out.

While re-measuring, my OWN shell one-liner reproduced the defect live::

    git show <rev>:<path> | grep -c $'\\r'

reported a count exactly equal to the LINE count for five different revisions of the same
file -- 242, 242, 248, 276, 291 -- while a byte-exact Python counter read 0 CRLF for every
one of them.  Two instruments, same bytes, opposite answers: a detector failure, not a
finding.  `248` is round 2's shipped number for that very file, and it is the line count at
`959f783f`.

This script runs the suspect shell detector and a byte-exact counter over the SAME two
blobs -- one known-CRLF, one known-LF -- so the answer cannot be a matter of opinion.

SCOPE, ADDED AFTER THE FACT AND LOAD-BEARING: ``bash`` spawned from Python on this box is
**WSL bash**, not Git Bash -- measured, the child reports its cwd as ``/mnt/c/Users/...``.
So everything below characterises *WSL* grep.  It says nothing about MSYS grep, which was
separately measured to behave differently (it strips CR in text mode and misses a real
CRLF without ``-U``).  The temp-repo readings here are valid because a freshly ``git
init``-ed directory has a real ``.git`` DIRECTORY; the in-repo control at the bottom reads
NO-INPUT under WSL because this checkout is a linked worktree whose ``.git`` file holds a
Windows absolute path that WSL git cannot resolve.  A ``0`` from it is not a measurement.

Run::  python _r4_grep_control.py   ->  exit 0 if both controls behave; the verdict line
says whether the WSL shell detector can tell CRLF from LF at all.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[2]
# A committed, deliberately-CRLF blob (3 CRLF lines), authored by a sibling lane.  Used
# read-only; if it is ever retired the throwaway repo below still carries the control.
IN_REPO_CRLF = (
    "command-center/ssot/salvaged-from-scratch/_crlf_control_repo/known_crlf.md"
)


def sh(script: str, cwd: pathlib.Path) -> str:
    """Run a shell snippet through bash exactly as a terminal would."""
    out = subprocess.run(
        ["bash", "-lc", script], cwd=cwd, capture_output=True, text=True
    )
    return (out.stdout or out.stderr).strip()


def main() -> int:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="r4grep_"))
    try:
        env = ["git", "-c", "core.autocrlf=false", "-c", "user.email=t@t"]
        env += ["-c", "user.name=t"]
        subprocess.run(["git", "init", "-q", str(tmp)], check=True, capture_output=True)
        (tmp / ".gitattributes").write_bytes(b"* -text\n")
        (tmp / "crlf.md").write_bytes(b"a\r\nb\r\nc\r\nd\r\ne\r\n")  # 5 CRLF, 5 lines
        (tmp / "lf.md").write_bytes(b"a\nb\nc\nd\ne\n")  # 0 CRLF, 5 lines
        subprocess.run([*env, "add", "."], cwd=tmp, check=True, capture_output=True)
        subprocess.run(
            [*env, "commit", "-q", "-m", "c"], cwd=tmp, check=True, capture_output=True
        )

        print("== the two hypotheses, stated BEFORE the measurement ==")
        print(
            "  H-broken : the shell detector reports the LINE count regardless of EOL"
        )
        print("  H-works  : it reports 5 on the CRLF blob and 0 on the LF blob")
        print("  (both files have 5 lines, so only the LF blob can tell them apart --")
        print(
            "   a control run only on the CRLF file would PASS under both hypotheses)"
        )

        suspect = "git show HEAD:{p} | grep -c $'\\r'"
        correct = "git show HEAD:{p} | grep -cU $'\\r$'"
        rows = []
        for label, path in (("CRLF blob", "crlf.md"), ("LF blob", "lf.md")):
            s = sh(suspect.format(p=path), tmp)
            c = sh(correct.format(p=path), tmp)
            raw = subprocess.run(
                ["git", "show", f"HEAD:{path}"], cwd=tmp, capture_output=True
            ).stdout
            print(
                f"  {label:10} suspect `grep -c $'\\r'`={s:>3}  "
                f"corrected `grep -cU $'\\r$'`={c:>3}  python bytes={raw.count(chr(13).encode())}"
            )
            rows.append((label, s, c, raw.count(b"\r")))

        lf_row = [r for r in rows if r[0] == "LF blob"][0]
        broken = lf_row[1] == "5"
        works = lf_row[1] == "0"
        print(
            f"\n  VERDICT (WSL grep only -- NOT transferable to MSYS grep): "
            f"{'BROKEN, reports the line count on an LF blob' if broken else ''}"
            f"{'sound HERE' if works else ''}"
            f"{'inconclusive' if not broken and not works else ''}"
        )
        print(
            "  Measured separately in Git Bash, the SAME one-liner missed a real CRLF\n"
            "  (0 where od proves 2) and returned 276 on a CR-free blob.  One shell's\n"
            "  verdict about a detector does not carry to another shell."
        )

        # Second state: the corrected detector must still SEE a real CRLF blob, or the
        # 'corrected' form is just a differently-blind instrument.
        ok_pos = rows[0][2] == "5" and rows[0][3] == 5
        ok_neg = lf_row[2] == "0" and lf_row[3] == 0
        print(f"  corrected form fires on CRLF: {ok_pos}   silent on LF: {ok_neg}")

        if pathlib.Path(REPO / IN_REPO_CRLF).exists():
            size = sh(f"git show HEAD:{IN_REPO_CRLF} | wc -c", REPO)
            got = sh(f"git show HEAD:{IN_REPO_CRLF} | grep -cU $'\\r$'", REPO)
            # Distinguish "0 matches" from "0 bytes of input".  Without this clause the
            # WSL-cannot-resolve-a-linked-worktree failure reads as a clean, meaningless
            # zero -- which is exactly how it first presented.
            blind = size in ("0", "")
            verdict = (
                "NO-INPUT: WSL git cannot resolve this linked worktree, so this line is "
                "not a measurement"
                if blind
                else f"{got} (want > 0)"
            )
            print(f"  in-repo real CRLF blob, corrected form -> {verdict}")

        if not (ok_pos and ok_neg):
            print(
                "FAILED:r4-grep the corrected detector failed its own both-states test"
            )
            return 1
        print(
            "SUCCESS:r4-grep suspect detector characterised, corrected form controlled"
        )
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
