"""Count CRLF in the worktree file vs its INDEX blob, with the detector controlled first.

WHY THIS FILE EXISTS. `grep -c $'\\r'` reported 3 CRLF lines in a file built with `printf 'a\\nb\\nc\\n'`
-- i.e. it counted every LINE, not every CR. Git Bash did not pass `$'\\r'` through as a CR byte, so
the pattern degenerated and matched everything. Three separate measurements this session were
therefore meaningless, including one that appeared to show git storing CRLF in its blobs.

Rule: a detector that cannot distinguish a known-LF file from a known-CRLF file measures nothing.
This probe asserts both controls BEFORE reporting any real file, and exits non-zero if either fails.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools/measure-guard"))

# Reuse the existing counter rather than shipping a second one: a dup-guard flagged that
# `crlf_count` already lives in the measure-guard blob reader, which was built this session for
# precisely this question. Two copies of an EOL counter is how the two disagree later.
from blobread import crlf_count  # noqa: E402


def lone_cr(data: bytes) -> int:
    return data.count(b"\r") - data.count(b"\r\n")


def _index_blob(rel: str) -> bytes | None:
    """The bytes git ACTUALLY has staged -- via the index blob sha and `cat-file -p`.

    `git show :path` is NOT this: it applies working-tree conversion and hands back CRLF on Windows,
    exactly like `git archive`. Only the sha route gives the stored bytes.
    """
    entry = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-s", "--", rel],
        capture_output=True, text=True, check=False,
    ).stdout.split()
    if len(entry) < 2:
        return None
    return subprocess.run(
        ["git", "-C", str(REPO), "cat-file", "-p", entry[1]],
        capture_output=True, check=False,
    ).stdout


def main(argv: list[str]) -> int:
    # ---- controls, run BEFORE anything real ----
    if crlf_count(b"a\nb\nc\n") != 0:
        print("FAILED:eol-probe control 1 -- LF sample reported CRLF")
        return 1
    if crlf_count(b"a\r\nb\r\nc\r\n") != 3:
        print("FAILED:eol-probe control 2 -- CRLF sample not counted as 3")
        return 1
    print("  controls PASS (LF sample -> 0, CRLF sample -> 3)\n")

    rels = argv or [
        line
        for line in subprocess.run(
            ["git", "-C", str(REPO), "diff", "--cached", "--name-only"],
            capture_output=True, text=True, check=False,
        ).stdout.splitlines()
        if line.endswith(".py")
    ]

    print(f"  {'path':<34} {'worktree':>18}   {'index blob':>18}")
    bad = []
    for rel in rels:
        wt = (REPO / rel).read_bytes() if (REPO / rel).exists() else b""
        ib = _index_blob(rel)
        if ib is None:
            print(f"  {rel:<34} {'(not staged)':>18}")
            continue
        w = f"{crlf_count(wt)} CRLF/{lone_cr(wt)} CR"
        i = f"{crlf_count(ib)} CRLF/{lone_cr(ib)} CR"
        print(f"  {Path(rel).name:<34} {w:>18}   {i:>18}")
        if crlf_count(ib):
            bad.append(rel)

    print()
    if bad:
        print(f"FAILED:eol-probe {len(bad)} staged blob(s) contain CRLF: {bad}")
        return 1
    print(f"SUCCESS:eol-probe all {len(rels)} staged blob(s) are LF-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
