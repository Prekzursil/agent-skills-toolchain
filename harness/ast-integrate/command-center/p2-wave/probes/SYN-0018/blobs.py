"""Isolated git blob IO for SYN-0018.

Reads use `git cat-file -p <tree>:<path>` (and `git show` as the agreeing
control). Classification never uses `git archive`. Trees are built with
`hash-object -w` + `mktree` in a throwaway bare repo — no add/commit/checkout
on the worktree.

`.gitattributes` `* text eol=crlf` is planted so default `git archive` returns
CRLF while the blob stays LF (the Windows-box trap, reproducible on Linux).
"""
from __future__ import annotations

import io
import os
import subprocess
import tarfile
from pathlib import Path

RECIPE_NAME = "git cat-file -p"
FORBIDDEN_RECIPE = "git archive"


class BlobError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


def _env(git_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_DIR"] = str(git_dir)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    env.pop("GIT_INDEX_FILE", None)
    env.pop("GIT_WORK_TREE", None)
    return env


def git(git_dir: Path, args: list[str], stdin: bytes | None = None) -> bytes:
    proc = subprocess.run(
        ["git", *args],
        input=stdin,
        capture_output=True,
        env=_env(git_dir),
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace").strip()[:400]
        raise BlobError("git-failed", f"{args[0]}:{err}")
    return proc.stdout


def init_bare(git_dir: Path) -> None:
    git_dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["git", "init", "--bare", "--", str(git_dir)],
        capture_output=True,
        env=_env(git_dir),
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace").strip()[:400]
        raise BlobError("git-init", err)


def hash_object(git_dir: Path, data: bytes) -> str:
    sha = git(git_dir, ["hash-object", "-w", "--stdin"], stdin=data)
    text = sha.decode("ascii").strip()
    if len(text) != 40:
        raise BlobError("bad-blob-sha", repr(text))
    return text


def mktree(git_dir: Path, entries: list[tuple[str, str, str, str]]) -> str:
    payload = b"".join(
        f"{mode} {kind} {sha}\t{name}\n".encode("utf-8")
        for mode, kind, sha, name in entries
    )
    sha = git(git_dir, ["mktree"], stdin=payload)
    text = sha.decode("ascii").strip()
    if len(text) != 40:
        raise BlobError("bad-tree-sha", repr(text))
    return text


def write_tree(git_dir: Path, files: dict[str, bytes]) -> str:
    blobs: dict[str, str] = {}
    dirs: dict[str, dict[str, bytes]] = {}
    for path, data in files.items():
        if "/" not in path:
            blobs[path] = hash_object(git_dir, data)
            continue
        top, rest = path.split("/", 1)
        dirs.setdefault(top, {})[rest] = data
    entries: list[tuple[str, str, str, str]] = []
    for name, sha in sorted(blobs.items()):
        entries.append(("100644", "blob", sha, name))
    for name, sub in sorted(dirs.items()):
        entries.append(("040000", "tree", write_tree(git_dir, sub), name))
    return mktree(git_dir, entries)


def cat_file(git_dir: Path, tree: str, path: str) -> bytes | None:
    spec = f"{tree}:{path}"
    proc = subprocess.run(
        ["git", "cat-file", "-p", spec],
        capture_output=True,
        env=_env(git_dir),
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def git_show(git_dir: Path, tree: str, path: str) -> bytes | None:
    spec = f"{tree}:{path}"
    proc = subprocess.run(
        ["git", "show", spec],
        capture_output=True,
        env=_env(git_dir),
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def archive_bytes(git_dir: Path, tree: str, path: str) -> bytes:
    """Export via git archive (recipe-control only; never for classification)."""
    proc = subprocess.run(
        ["git", "archive", tree, "--", path],
        capture_output=True,
        env=_env(git_dir),
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace").strip()[:400]
        raise BlobError("archive-failed", err)
    tf = tarfile.open(fileobj=io.BytesIO(proc.stdout), mode="r:")
    found: bytes | None = None
    for member in tf.getmembers():
        if not member.isfile():
            continue
        extracted = tf.extractfile(member)
        if extracted is None:
            continue
        if member.name == path or member.name.endswith("/" + path.split("/")[-1]):
            found = extracted.read()
            break
    if found is None:
        raise BlobError("archive-member-missing", path)
    return found
