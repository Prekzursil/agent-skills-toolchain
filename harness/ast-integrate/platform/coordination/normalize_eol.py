"""Normalise this package's text files to LF, and prove the working tree matches the git BLOB.

WHY THIS EXISTS AS A TRACKED TOOL RATHER THAN A ONE-OFF

``rules/common/windows-shell.md`` section 8b: a working-tree file can be CRLF while git stores LF,
and **formatters make different decisions on the two forms**. Measured on this estate:
``ruff format --check`` reported "1 file already formatted" locally while CI reported "Would
reformat" for the SAME commit. A local green measured against the wrong bytes verifies nothing.

Two things bit during this build and are why the check is mechanical:

1. Python's default text-mode write on Windows translates ``\\n`` to ``\\r\\n``. Six files rewritten
   by an in-line edit script silently became CRLF while the rest of the package stayed LF.
2. ``git config core.autocrlf`` is ``true`` here, so ``git add`` normalises CRLF to LF in the blob
   anyway - which means the DIVERGENCE IS INVISIBLE in a diff and only shows up as a formatter
   disagreement between this box and CI.

The blob comparison uses ``git hash-object --path`` (which applies the same attributes and filters
``git add`` would) followed by ``git cat-file -p``. It deliberately does NOT use ``git archive``:
that applies export-time EOL conversion and returns CRLF on this box, i.e. the opposite of the
bytes CI checks out.

Run: ``python platform/coordination/normalize_eol.py [--check]``
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SUFFIXES = (".py", ".md", ".json")


def targets() -> list[Path]:
    return [
        p
        for p in sorted(HERE.rglob("*"))
        if p.is_file() and p.suffix in SUFFIXES and "__pycache__" not in p.parts
    ]


def to_lf(path: Path) -> bool:
    """Rewrite ``path`` with LF endings. Returns True when bytes changed."""
    raw = path.read_bytes()
    fixed = raw.replace(b"\r\n", b"\n")
    if fixed == raw:
        return False
    with open(path, "wb") as fh:
        fh.write(fixed)
    return True


def blob_bytes(path: Path) -> bytes:
    """What git WOULD store for ``path`` - attributes and autocrlf applied, no export filter."""
    rel = path.relative_to(REPO).as_posix()
    digest = subprocess.run(  # noqa: S603 - fixed argv
        ["git", "hash-object", "-w", "--path", rel, str(path)],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return subprocess.run(  # noqa: S603 - fixed argv
        ["git", "cat-file", "-p", digest], cwd=REPO, capture_output=True, check=True
    ).stdout


def main(argv: list[str]) -> int:
    check_only = "--check" in argv
    files = targets()
    if not files:
        print(
            "FAILED:normalize-eol no candidate files found - empty walk is never a pass"
        )
        return 1

    crlf = [p for p in files if b"\r\n" in p.read_bytes()]
    if check_only:
        if crlf:
            for p in crlf:
                print(f"FAILED:normalize-eol CRLF in {p.relative_to(REPO).as_posix()}")
            return 1
    else:
        for p in crlf:
            to_lf(p)
            print(f"normalised {p.relative_to(REPO).as_posix()}")

    mismatched: list[str] = []
    for p in files:
        if p.read_bytes() != blob_bytes(p):
            mismatched.append(p.relative_to(REPO).as_posix())
    for rel in mismatched:
        print(f"FAILED:normalize-eol working tree differs from the git blob: {rel}")

    if mismatched:
        return 1
    print(
        f"SUCCESS:normalize-eol files={len(files)} crlf_fixed={0 if check_only else len(crlf)} "
        "worktree==blob for every file"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
