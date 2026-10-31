"""ruff over the COMMITTED BLOBS of a given commit -- file list DERIVED, never hardcoded.

WHY THIS EXISTS RATHER THAN REUSING `_r2_blobcheck.py`. That script carries a HARDCODED FILES
list (its lines 29-39) naming the round-2 lane's ten scripts. Run after a later commit it still
reports "extracted 10 blobs ... All checks passed" -- a green about files nobody just changed.
It reported exactly that for this round's commit, whose ten files it shares NONE of. The "10
blobs" it printed happened to equal the "10 files changed" of the new commit, which is the
suspiciously-equal-number tell: a control that passes while measuring the wrong collection.

So the file list here is DERIVED FROM THE COMMIT (`git diff-tree`), which cannot go stale, and
the run FAILS CLOSED at zero files rather than reporting a clean tree it never read.

windows-shell.md Sec.8b: the working tree is CRLF, git stores LF, CI checks out LF, and ruff can
decide differently on the two. `git cat-file -p` returns the stored blob (NOT `git archive`,
which applies EOL conversion and hands back CRLF on Windows).
The repo's ruff.toml is carried into the temp tree and relative paths are mirrored, or ruff falls
back to line-length 88 against this repo's 120 and manufactures a false CI-red on clean files.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUFF = ["uvx", "ruff@0.15.17"]
CONFIG = "ruff.toml"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), *args], capture_output=True, text=True, check=True
    ).stdout


def main(argv: list[str] | None = None) -> int:
    rev = (argv or sys.argv[1:] or ["HEAD"])[0]
    changed = [
        line.strip()
        for line in git(
            "diff-tree", "--no-commit-id", "--name-only", "-r", rev
        ).splitlines()
        if line.strip().endswith(".py")
    ]
    print(f"  rev={rev}  python files changed by THIS commit: {len(changed)}")
    for rel in changed:
        print(f"    {rel}")
    if not changed:
        print("FAILED:c4-blobcheck no python files in this commit -- failing closed")
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="c4blob_"))
    try:
        crlf = 0
        for rel in changed:
            raw = subprocess.run(
                ["git", "-C", str(REPO), "cat-file", "-p", f"{rev}:{rel}"],
                capture_output=True,
                check=True,
            ).stdout
            crlf += raw.count(b"\r\n")
            dest = tmp / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)
        shutil.copy2(REPO / CONFIG, tmp / CONFIG)
        print(f"  carried config: {CONFIG}")
        print(
            f"  extracted {len(changed)} blobs; CRLF sequences across all of them: {crlf}"
        )

        rc = 0
        for label, cmd in (
            ("format --check", [*RUFF, "format", "--check", "."]),
            ("check", [*RUFF, "check", "."]),
        ):
            out = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True)
            tail = [ln for ln in (out.stdout + out.stderr).splitlines() if ln.strip()][
                -1:
            ]
            print(f"  BLOB ruff {label:<15} rc={out.returncode} :: {tail}")
            rc |= out.returncode

        # CONTROL: the detector must FIRE on a known-broken blob, or its silence means nothing.
        victim = tmp / changed[0]
        victim.write_text(
            "import os,sys\nx  =  1\ndef  f( a ):\n  return  a\n", encoding="utf-8"
        )
        ctl = subprocess.run(
            [*RUFF, "format", "--check", "."], cwd=tmp, capture_output=True, text=True
        )
        print(
            f"  CONTROL mangled blob -> rc={ctl.returncode} fires={ctl.returncode != 0}"
        )
        if ctl.returncode == 0:
            print("FAILED:c4-blobcheck control did not fire -- verdict not trustworthy")
            return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if rc:
        print("FAILED:c4-blobcheck ruff red on the committed blobs")
        return 1
    print("SUCCESS:c4-blobcheck committed blobs are ruff-clean in their LF form")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
