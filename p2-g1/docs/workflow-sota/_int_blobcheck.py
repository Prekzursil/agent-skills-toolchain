#!/usr/bin/env python3
"""Blob-level lint/format check -- a Windows working-tree green does NOT imply CI green.

``rules/common/windows-shell.md`` 8b: the working tree here is CRLF, git stores LF, and
CI checks out the LF form.  ruff can make different decisions on the two.  So verify the
STORED BLOB.

Two traps this script exists to avoid, both previously measured:
  * ``git archive`` re-applies EOL conversion on Windows and hands back CRLF -- the exact
    opposite of what is wanted.  ``git cat-file -p :<path>`` (index blob) is used instead.
  * a bare temp dir has no ``ruff.toml``, so ruff falls back to its own defaults and can
    manufacture a FALSE red.  The repo config is copied in and the relative paths mirrored.

A deliberately mangled control file is added and MUST appear in ruff's reformat list.  If it
does not, the checker is not checking and the green means nothing.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUFF = ["uvx", "ruff@0.15.17"]
CONTROL = "_control_mangled.py"
CONTROL_BODY = "def  f( a,b ):\n  return   {  'x' :a,'y':b }\n"


def staged_python_paths() -> list[str]:
    out = subprocess.check_output(
        ["git", "-C", str(ROOT), "diff", "--cached", "--name-only"], text=True
    )
    return [p for p in out.split("\n") if p.endswith(".py")]


def blob(rel: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(ROOT), "cat-file", "-p", f":{rel}"],
        capture_output=True,
        check=True,
    ).stdout


def main() -> int:
    paths = staged_python_paths()
    if not paths:
        print("FAILED:blobcheck no staged .py files (empty walk)")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp)
        shutil.copy2(ROOT / "ruff.toml", dest / "ruff.toml")
        crlf = 0
        for rel in paths:
            data = blob(rel)
            crlf += data.count(b"\r\n")
            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
        (dest / CONTROL).write_text(CONTROL_BODY, encoding="utf-8", newline="\n")

        check = subprocess.run(
            [*RUFF, "check", "."], cwd=dest, capture_output=True, text=True
        )
        fmt = subprocess.run(
            [*RUFF, "format", "--check", "."], cwd=dest, capture_output=True, text=True
        )

    fired = CONTROL in fmt.stdout
    flagged = [
        ln.split("Would reformat:", 1)[1].strip()
        for ln in fmt.stdout.splitlines()
        if "Would reformat:" in ln
    ]
    real = [f for f in flagged if Path(f).name != CONTROL]

    print(f"blobs extracted (git cat-file -p, NOT git archive): {len(paths)}")
    print(f"CRLF byte pairs inside those blobs: {crlf}")
    print(
        f"ruff check   rc={check.returncode}: {check.stdout.strip().splitlines()[-1:]}"
    )
    print(f"ruff format  rc={fmt.returncode}: {fmt.stdout.strip().splitlines()[-1:]}")
    print(f"CONTROL FIRED: {fired}   REAL BLOBS FLAGGED: {real}")

    ok = fired and not real and check.returncode == 0 and crlf == 0
    print(
        "SUCCESS:blobcheck stored blobs are LF and CI-clean; control fired"
        if ok
        else "FAILED:blobcheck see above"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
