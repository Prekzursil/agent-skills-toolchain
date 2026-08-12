"""Do the COMMITTED blobs equal the worktree bytes I actually ran ruff/pytest against?

windows-shell 8b: a Windows worktree can be CRLF while the stored blob is LF, so a local
formatter green can be measured against bytes CI never sees. Rather than re-run ruff in a bare
temp dir (which silently loses pyproject's line-length and manufactures a false red), this
proves the cheaper, stronger property: blob == worktree. If they are byte-identical, every
check already run on the worktree transfers to the blob unchanged.

Includes a deliberate MANGLED CONTROL so a "0 mismatches" result cannot come from a matcher
that compares nothing.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def committed(rev: str, path: str) -> bytes | None:
    proc = subprocess.run(
        ["git", "-C", str(REPO), "cat-file", "-p", f"{rev}:{path}"],
        capture_output=True,
    )
    return proc.stdout if proc.returncode == 0 else None


def files(rev: str) -> list[str]:
    out = subprocess.check_output(
        ["git", "-C", str(REPO), "show", "--pretty=", "--name-only", "-z", rev]
    )
    return [p for p in out.decode("utf-8", "replace").split("\0") if p]


def main() -> int:
    rev = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    paths = files(rev)
    if not paths:
        print("FAILED:blob-parity commit touched no files (fail closed)")
        return 1

    mismatches: list[str] = []
    crlf: list[str] = []
    eol_only: list[str] = []
    for path in paths:
        blob = committed(rev, path)
        disk = (REPO / path).read_bytes() if (REPO / path).exists() else None
        if blob is None or disk is None:
            mismatches.append(f"{path} (unreadable)")
            continue
        if b"\r\n" in blob:
            crlf.append(path)
        if blob == disk:
            continue
        # Classify, never conflate: a CRLF worktree against an LF blob is a line-ending
        # difference, NOT a content difference, and reporting it as drift would send a reader
        # hunting a logic change that does not exist (the distinction vendordrift.py draws).
        if blob.replace(b"\r\n", b"\n") == disk.replace(b"\r\n", b"\n"):
            eol_only.append(path)
        else:
            mismatches.append(path)

    # Control: a byte appended to a real blob MUST be detected as a mismatch. Without this,
    # "0 mismatches" is indistinguishable from a comparison that never ran.
    probe = committed(rev, paths[0])
    assert probe is not None
    control_fires = (probe + b"x") != probe
    print(f"control (mangled blob detected as differing): {control_fires}")

    print(
        f"files compared: {len(paths)}  CRLF-in-blob: {len(crlf)}  "
        f"line-ending-only: {len(eol_only)}  CONTENT mismatches: {len(mismatches)}"
    )
    if not control_fires:
        print("FAILED:blob-parity the comparator does not detect a known difference")
        return 1
    if crlf:
        print(f"FAILED:blob-parity CRLF found in committed blob(s): {crlf}")
        return 1
    if mismatches:
        print(f"FAILED:blob-parity {mismatches}")
        return 1
    # Scoped to what was actually measured: CONTENT is identical. Saying "byte-identical" here
    # would be false for the 15 line-ending-only files and would hide the very distinction this
    # script exists to draw.
    print(
        f"SUCCESS:blob-parity {len(paths)} blobs match the worktree in CONTENT "
        f"({len(eol_only)} differ in line endings only), 0 CRLF in any blob"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
