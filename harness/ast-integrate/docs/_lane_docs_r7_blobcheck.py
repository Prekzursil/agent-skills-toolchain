"""Round 7: run the CI format gate against the STORED BLOB, not the working tree.

windows-shell rule 8b: a Windows working tree is CRLF, git stores LF, and CI on
Linux checks out the LF form -- and ruff can make different decisions on the two.
A local `ruff format --check` green is measured against the wrong bytes.

The blob is extracted with ``git cat-file -p`` in BYTE mode. PowerShell's ``>``
re-encodes and joins with the OS newline, so a redirect-based census of the same
blob cannot be trusted; ``capture_output`` without ``text=True`` cannot re-encode.

The ruff CONFIG travels with the blob (a bare temp dir has no ``ruff.toml``, so
ruff would fall back to its own defaults and return a verdict about a different
line-length than the project's), and the repo-relative path is mirrored so any
per-path config still applies.

Control: a deliberately mangled copy must FAIL in the same harness. Without it a
clean run only proves ruff was invoked.

Terminal state: SUCCESS:docs-r7-blobcheck / FAILED:docs-r7-blobcheck <reason>
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REV = sys.argv[1] if len(sys.argv) > 1 else "HEAD"

TARGETS = [
    "ci/tests/test_command_doc_promises.py",
    "ci/tests/docs_count_anchors.py",
    "docs/_lane_docs_r7_apply.py",
    "docs/_lane_docs_r7_remeasure.py",
    "docs/_lane_docs_r7_bothstates.py",
    "docs/_lane_docs_r7_shallow_control.py",
    "docs/_lane_docs_r7_blobcheck.py",
]

RUFF = ["uvx", "ruff@0.15.17", "format", "--check"]


def blob(rev: str, path: str) -> bytes | None:
    proc = subprocess.run(
        ["git", "-C", str(REPO), "cat-file", "-p", f"{rev}:{path}"],
        capture_output=True,
    )
    return proc.stdout if proc.returncode == 0 else None


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="docs-r7-blob-"))
    try:
        for cfg in ("ruff.toml", "pyproject.toml", ".ruff.toml"):
            src = REPO / cfg
            if src.exists():
                shutil.copy2(src, work / cfg)

        census: list[str] = []
        for rel in TARGETS:
            data = blob(REV, rel)
            if data is None:
                print(f"FAILED:docs-r7-blobcheck {rel} is not committed at {REV}")
                return 1
            cr = data.count(b"\r")
            census.append(f"{rel.rsplit('/', 1)[-1]}:CR={cr}")
            if cr:
                print(f"FAILED:docs-r7-blobcheck {rel} blob carries {cr} CR bytes")
                return 1
            dest = work / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)

        proc = subprocess.run(
            [*RUFF, *[str(work / r) for r in TARGETS]],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=work,
        )
        if proc.returncode != 0:
            print(
                "FAILED:docs-r7-blobcheck ruff format --check is RED on the LF blob "
                f"while the CRLF working tree is green: {(proc.stdout + proc.stderr)[-400:]}"
            )
            return 1

        # ---- control: the harness must be able to report RED ----------------
        victim = work / "control_mangled.py"
        victim.write_bytes(b"def  f( a,b ):\n      return (a,\n   b)\n")
        ctrl = subprocess.run(
            [*RUFF, str(victim)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=work,
        )
        if ctrl.returncode == 0:
            print(
                "FAILED:docs-r7-blobcheck control: mangled file passed; the check is inert"
            )
            return 1

        print(
            f"SUCCESS:docs-r7-blobcheck rev={REV} files={len(TARGETS)} "
            f"blob_format=clean control_fires=True {' '.join(census)}"
        )
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
