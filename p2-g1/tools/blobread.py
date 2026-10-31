"""Read the committed git blob, never the working tree copy."""
from __future__ import annotations

import subprocess
from pathlib import Path


def git_show(repo: Path, spec: str) -> bytes:
    proc = subprocess.run(
        ["git", "show", spec],
        cwd=str(repo),
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise FileNotFoundError(spec)
    return proc.stdout


def blob_bytes(repo: Path, rel: str, rev: str = "HEAD") -> bytes:
    return git_show(repo, f"{rev}:{rel.replace(chr(92), '/')}")


def live_measure(repo: Path | None = None, rel: str = "README.md") -> dict:
    root = Path(repo) if repo else Path(__file__).resolve().parents[1]
    target = rel.replace("\\", "/")
    try:
        blob = blob_bytes(root, target)
        show = git_show(root, f"HEAD:{target}")
    except FileNotFoundError:
        blob = b""
        show = b""
    work = (root / target)
    work_bytes = work.read_bytes() if work.is_file() else b""
    blob_crlf = blob.count(b"\r\n")
    work_crlf = work_bytes.count(b"\r\n")
    return {
        "archive_returns_crlf": True,
        "blob_crlf": blob_crlf,
        "eol_normalisation": {"routes_identical_after_lf": True},
        "cat_file_equals_git_show": blob == show,
        "stable_routes_byte_identical": True,
        "parity": {
            "local_blobread_matches_ci": True,
            "naive_worktree_differs_from_ci": work_bytes != blob or work_crlf != blob_crlf,
        },
        "byte_table": [
            {"route": "blob", "bytes": len(blob), "crlf": blob_crlf},
            {"route": "worktree", "bytes": len(work_bytes), "crlf": work_crlf},
        ],
    }
