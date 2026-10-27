"""Provenance hasher for REACH-6 (CC-0005).

Hashes `git cat-file -p <rev>:<path>` -- the stored blob CI checks out.
`git archive` is a negative control only: it applies export-time EOL
conversion and must never feed the digest. `_run_git` is list-form argv.
"""

from __future__ import annotations

import hashlib
import io
import subprocess
import tarfile
from pathlib import Path


class GitBlobError(RuntimeError):
    """git cat-file / show / archive failed; REACH-6 fails closed."""


def lf_normalize(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_git_work_tree(repo: Path | None) -> bool:
    return bool(repo) and (Path(repo) / ".git").exists()


def use_blob(*, override: bool, git_repo: Path | None) -> bool:
    """True when REACH-6 must hash the git blob (no planted override)."""
    return (not override) and is_git_work_tree(git_repo)


def _run_git(args: list[str], *, repo: Path) -> bytes:
    cmd = ["git", "-C", str(repo), *args]
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace").strip()
        raise GitBlobError(f"git {' '.join(args)} rc={proc.returncode}: {err}")
    return proc.stdout


def git_blob_bytes(rel: str, *, repo: Path, rev: str = "HEAD") -> bytes:
    """Return stored blob bytes via git cat-file -p."""
    rel = rel.replace("\\", "/")
    return _run_git(["cat-file", "-p", f"{rev}:{rel}"], repo=repo)


def git_show_bytes(rel: str, *, repo: Path, rev: str = "HEAD") -> bytes:
    rel = rel.replace("\\", "/")
    return _run_git(["show", f"{rev}:{rel}"], repo=repo)


def git_archive_bytes(rel: str, *, repo: Path, rev: str = "HEAD") -> bytes:
    """Negative control: git archive export bytes (may convert EOL)."""
    rel = rel.replace("\\", "/")
    raw = _run_git(["archive", "--format=tar", rev, "--", rel], repo=repo)
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as tf:
        names = tf.getnames()
        for candidate in (rel, "./" + rel, Path(rel).name):
            if candidate in names:
                fh = tf.extractfile(candidate)
                if fh is None:
                    raise GitBlobError(f"git archive empty member {candidate}")
                return fh.read()
        raise GitBlobError(f"{rel} not in git archive members {names}")


def register_bytes_for_hash(
    *,
    snapshot: Path,
    rel: str,
    git_repo: Path | None,
    override: bool,
) -> tuple[bytes | None, str, str | None]:
    """Pick bytes + via-label for REACH-6.

    use_blob when no override: git cat-file -p. Planted override files
    hash working-tree bytes. Non-git worktrees fall back to LF-normalised
    working-tree bytes.
    """
    rel = (rel or "").replace("\\", "/")
    if override:
        if not snapshot.is_file():
            return (
                None,
                "worktree-override",
                f"register snapshot missing at {snapshot}",
            )
        return snapshot.read_bytes(), "worktree-override", None
    if use_blob(override=False, git_repo=git_repo) and git_repo is not None:
        try:
            return git_blob_bytes(rel, repo=git_repo), "git-cat-file", None
        except GitBlobError as exc:
            return None, "git-cat-file", (
                "register snapshot blob unreadable via git cat-file -p "
                f"({exc}); digest check cannot run, so REACH-6 fails closed"
            )
    if not snapshot.is_file():
        return None, "worktree-fallback", f"register snapshot missing at {snapshot}"
    return lf_normalize(snapshot.read_bytes()), "worktree-fallback", None
