"""LANE DOCS round 6 -- verify the COMMITTED BLOBS, not the working tree.

A Windows-local green proves nothing about CI: the working tree can be CRLF while the stored
blob is LF, and CI checks out the blob. ``git cat-file -p`` returns the stored bytes with no
EOL conversion (``git archive`` is the one that re-inserts CRLF on Windows, measured), so it
is the right reader here.

Checks, per file committed by round 6:
  1. the blob exists at the pinned commit;
  2. the blob has ZERO CRLF -- i.e. what ubuntu CI will read;
  3. the blob is byte-identical to the working tree after LF-normalisation, which is what
     makes the local pytest run evidence about the blob rather than only about this box.

CONTROL (distinguishes "my reader sees CRLF" from "my reader is blind to CRLF"): a synthetic
CRLF buffer must be counted as CRLF. Without it, a CRLF=0 reading could mean the counter is
broken rather than the bytes being clean.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

COMMIT = "65af5451"

FILES = [
    "docs/_LANE-DOCS-BUILD-R5.md",
    "docs/_LANE-DOCS-BUILD-R6.md",
    "docs/_lane_docs_r6_pinned_counts.py",
    "docs/_lane_docs_r6_eol.py",
    "ci/tests/test_command_doc_promises.py",
]


def blob_bytes(rev: str, path: str) -> bytes:
    proc = subprocess.run(
        ["git", "cat-file", "-p", f"{rev}:{path}"],
        cwd=REPO,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"FAILED:docs-r6-blobcheck cat-file {path} rc={proc.returncode} "
            f"{proc.stderr.decode('utf-8', 'replace').strip()[:160]}"
        )
    return proc.stdout


def main() -> int:
    # CONTROL: the counter must SEE CRLF when CRLF is present.
    synthetic = b"a\r\nb\r\n"
    control_ok = synthetic.count(b"\r\n") == 2
    print(f"CONTROL crlf_counter_sees_crlf={control_ok} (must be True)")
    if not control_ok:  # pragma: no cover - defensive
        print("FAILED:docs-r6-blobcheck control could not see CRLF")
        return 1

    bad: list[str] = []
    for rel in FILES:
        blob = blob_bytes(COMMIT, rel)
        crlf = blob.count(b"\r\n")
        tree = (REPO / rel).read_bytes()
        same = blob.replace(b"\r\n", b"\n") == tree.replace(b"\r\n", b"\n")
        exact = blob == tree
        print(
            f"{rel:42s} blob_bytes={len(blob):6d} blob_CRLF={crlf:4d} "
            f"tree_CRLF={tree.count(chr(13).encode() + chr(10).encode()):4d} "
            f"norm_equal={same} byte_equal={exact}"
        )
        if crlf:
            bad.append(f"{rel}:blob-has-crlf")
        if not same:
            bad.append(f"{rel}:blob-differs-from-tree")

    if bad:
        print(f"FAILED:docs-r6-blobcheck {' '.join(bad)}")
        return 1
    print(
        f"SUCCESS:docs-r6-blobcheck commit={COMMIT} files={len(FILES)} crlf=0 tree==blob"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
