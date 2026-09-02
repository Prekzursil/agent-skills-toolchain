"""Build a fixture git object store without git add / commit / checkout.

Uses hash-object + mktree + commit-tree + update-ref only. Worktree bytes are
written directly so a CRLF working copy can sit on LF blobs (Windows autocrlf
simulation) without `git checkout`.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from lib import git_env

ATTRS = (
    "*.sh text eol=lf\n"
    "*.py text eol=lf\n"
    "*.ps1 text eol=crlf\n"
    "*.txt text eol=crlf\n"
)

# Blob bytes are stored LF. Worktree may differ.
BLOBS: dict[str, bytes] = {
    ".gitattributes": ATTRS.encode("utf-8"),
    "README.md": b"hello\nworld\n",
    "script.sh": b"#!/bin/sh\necho hi\n",
    "notes.txt": b"line1\nline2\n",
    "win.ps1": b"Write-Output ping\n",
    "src/tool.py": b"print(1)\nprint(2)\n",
    "changed.md": b"original\n",
}

WORKTREE: dict[str, bytes] = {
    ".gitattributes": ATTRS.encode("utf-8"),
    "README.md": b"hello\nworld\n",  # identical
    "script.sh": b"#!/bin/sh\necho hi\n",  # identical, pinned eol=lf
    "notes.txt": b"line1\nline2\n",  # identical blob/wt; archive converts to CRLF
    "win.ps1": b"Write-Output ping\n",
    "src/tool.py": b"print(1)\r\nprint(2)\r\n",  # EOL-only vs blob
    "changed.md": b"original\nMUTATED\n",  # content drift, not EOL
}

PLANTED = {
    "eol_only": "src/tool.py",
    "content": "changed.md",
    "identical_pinned": "script.sh",
    "archive_disagrees": "notes.txt",
    "unpinned_identical": "README.md",
}


def _run(args: list[str], *, cwd: Path, env: dict[str, str], input: bytes | None = None) -> bytes:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        input=input,
        capture_output=True,
        env=env,
    )
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace")
        raise RuntimeError(f"git {' '.join(args)} failed: {err.strip()}")
    return proc.stdout


def _hash_blob(git_dir: Path, data: bytes, env: dict[str, str]) -> str:
    out = _run(["hash-object", "-w", "--stdin"], cwd=git_dir, env=env, input=data)
    return out.decode("ascii").strip()


def _mktree(git_dir: Path, entries: list[tuple[str, str, str, str]], env: dict[str, str]) -> str:
    body = "".join(f"{mode} {typ} {sha}\t{name}\n" for mode, typ, sha, name in entries)
    out = _run(["mktree"], cwd=git_dir, env=env, input=body.encode("utf-8"))
    return out.decode("ascii").strip()


def _build_tree(git_dir: Path, files: dict[str, bytes], env: dict[str, str]) -> str:
    nested: dict[str, dict[str, bytes]] = {}
    root_files: dict[str, bytes] = {}
    for rel, data in files.items():
        posix = rel.replace("\\", "/")
        if "/" in posix:
            top, rest = posix.split("/", 1)
            if "/" in rest:
                raise NotImplementedError(f"fixture only supports one nested dir: {rel}")
            nested.setdefault(top, {})[rest] = data
        else:
            root_files[posix] = data
    entries: list[tuple[str, str, str, str]] = []
    for name, data in sorted(root_files.items()):
        entries.append(("100644", "blob", _hash_blob(git_dir, data, env), name))
    for dirname, children in sorted(nested.items()):
        child_entries = [
            ("100644", "blob", _hash_blob(git_dir, data, env), name)
            for name, data in sorted(children.items())
        ]
        tree_sha = _mktree(git_dir, child_entries, env)
        entries.append(("040000", "tree", tree_sha, dirname))
    return _mktree(git_dir, entries, env)


def write_worktree(root: Path, files: dict[str, bytes] = WORKTREE) -> None:
    for rel, data in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def build_fixture(parent: Path | None = None) -> dict[str, Any]:
    base = Path(parent) if parent is not None else Path(
        tempfile.mkdtemp(prefix="aud0019-fix-")
    )
    git_dir = base / "store.git"
    work_tree = base / "wt"
    work_tree.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.setdefault("GIT_AUTHOR_NAME", "AUD-0019")
    env.setdefault("GIT_AUTHOR_EMAIL", "aud0019@fixture.invalid")
    env.setdefault("GIT_COMMITTER_NAME", "AUD-0019")
    env.setdefault("GIT_COMMITTER_EMAIL", "aud0019@fixture.invalid")
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    _run(["init", "--bare", str(git_dir)], cwd=base, env=env)
    local_env = git_env(git_dir, work_tree)
    tree = _build_tree(git_dir, BLOBS, local_env)
    commit = _run(
        ["commit-tree", tree, "-m", "AUD-0019 fixture LF blobs"],
        cwd=git_dir,
        env=local_env,
    ).decode("ascii").strip()
    _run(["update-ref", "HEAD", commit], cwd=git_dir, env=local_env)
    write_worktree(work_tree)
    return {
        "base": str(base),
        "git_dir": str(git_dir),
        "work_tree": str(work_tree),
        "commit": commit,
        "gitattributes": ATTRS,
        "blob_paths": sorted(BLOBS),
        "planted": dict(PLANTED),
        "construction": (
            "hash-object + mktree + commit-tree + update-ref; no git add/commit/checkout"
        ),
    }
