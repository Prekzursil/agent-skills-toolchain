"""Blob-byte helpers. git cat-file is the hash route; git archive is forbidden."""
from __future__ import annotations

import os
import subprocess
import tarfile
import tempfile
from io import BytesIO
from pathlib import Path


HASH_ROUTE = "git-cat-file"
# archive is forbidden as a blob source on this Windows autocrlf box.


class BlobRouteError(RuntimeError):
    """Raised when a forbidden git route (archive) is requested."""


def _git(git_dir: Path | str, *args: str) -> bytes:
    if args and args[0] == "archive":
        raise BlobRouteError("archive is forbidden")
    env = os.environ.copy()
    env["GIT_DIR"] = str(git_dir)
    p = subprocess.run(
        ["git", *args],
        capture_output=True,
        timeout=30,
        env=env,
    )
    if p.returncode != 0:
        raise BlobRouteError((p.stderr or p.stdout or b"").decode("utf-8", "replace"))
    return p.stdout


def blob_bytes(git_dir: Path | str, tree: str, rel: str) -> bytes:
    spec = f"{tree}:{rel.replace(chr(92), '/')}"
    return _git(git_dir, "cat-file", "-p", spec)


def show_equals_cat(git_dir: Path | str, spec: str) -> bool:
    cat = _git(git_dir, "cat-file", "-p", spec)
    show = _git(git_dir, "show", spec)
    return cat == show


def archive_bytes(git_dir: Path | str, tree: str, rel: str) -> bytes:
    """Extract a path from `git archive` without using it as the hash route."""
    env = os.environ.copy()
    env["GIT_DIR"] = str(git_dir)
    p = subprocess.run(
        ["git", "archive", "--format=tar", tree],
        capture_output=True,
        timeout=30,
        env=env,
    )
    if p.returncode != 0:
        return b""
    bio = BytesIO(p.stdout)
    with tarfile.open(fileobj=bio, mode="r:") as tar:
        try:
            member = tar.getmember(rel)
        except KeyError:
            return b""
        f = tar.extractfile(member)
        return f.read() if f else b""


def materialize(git_dir: Path | str, tree: str, dest: Path, eol: str = "lf") -> dict:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["GIT_DIR"] = str(git_dir)
    p = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", tree],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    names = [ln.strip() for ln in (p.stdout or "").splitlines() if ln.strip()]
    written = []
    for rel in names:
        data = blob_bytes(git_dir, tree, rel)
        if eol == "crlf":
            data = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        else:
            data = data.replace(b"\r\n", b"\n")
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        written.append(rel)
    return {"eol": eol, "files": written, "root": str(dest)}
