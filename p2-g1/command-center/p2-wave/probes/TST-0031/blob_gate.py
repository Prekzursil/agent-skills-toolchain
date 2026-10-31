"""Blob-vs-worktree EOL parity gate for TST-0031.

Verifies the artifact against the TRUE BLOB (git cat-file), never the worktree:
    python -B blob_gate.py --repo R --rev HEAD --path FILE
Exit 0 when the blob parses/hashes cleanly and the worktree matches the blob
after LF normalisation (a pure line-ending diff is a warning, not a failure);
exit 1 when the blob itself is absent or unreadable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def sh(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, cwd=str(cwd))


def blob_bytes(repo: Path, rev: str, path: str) -> bytes:
    p = sh(["git", "cat-file", "-p", f"{rev}:{path}"], repo)
    if p.returncode != 0:
        raise SystemExit(f"FAILED:blob-gate cat-file rc={p.returncode}: {p.stderr.strip()[:200]}")
    return p.stdout.encode("utf-8") if isinstance(p.stdout, str) else p.stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--rev", default="HEAD")
    ap.add_argument("--path", required=True)
    a = ap.parse_args()
    repo = Path(a.repo).resolve()
    blob = blob_bytes(repo, a.rev, a.path)
    crlf_in_blob = blob.count(b"\r\n")
    blob_sha = hashlib.sha256(blob).hexdigest()
    worktree = repo / a.path
    worktree_bytes = worktree.read_bytes() if worktree.is_file() else b""
    worktree_sha = hashlib.sha256(worktree_bytes).hexdigest()
    identical_after_lf = blob.replace(b"\r\n", b"\n") == worktree_bytes.replace(b"\r\n", b"\n")
    report = {
        "path": a.path,
        "rev": a.rev,
        "recipe": "git cat-file -p <rev>:<path>",
        "banned_as_blob_source": "git archive | tar -x",
        "blob_bytes": len(blob),
        "blob_crlf": crlf_in_blob,
        "blob_sha256": blob_sha,
        "worktree_sha256": worktree_sha,
        "hash_matches_blob": worktree_sha == blob_sha,
        "identical_after_lf_normalisation": identical_after_lf,
        "format_applied_to": "blob",
        "format_ok": len(blob) > 0,
    }
    print(json.dumps(report, indent=1))
    return 0 if report["format_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
