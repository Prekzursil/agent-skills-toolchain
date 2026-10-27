"""Discover workflow-shaped artifacts in a local git repository.

Worktree rows record a bare relative path. A path that exists only on a
remote ref records `git show <ref>:<path>`. git archive is forbidden.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "ovh-monitor",
    ".tox",
}
WORKFLOW_SUFFIXES = (".js", ".mjs", ".wf.json")


class ArchiveForbidden(RuntimeError):
    """git archive is not an allowed access method."""


@dataclass(frozen=True)
class Candidate:
    path: str
    access_method: str
    content_hash: str
    location: str
    ref: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def as_dicts(rows: Iterable[Candidate]) -> list[dict]:
    return [r.as_dict() if isinstance(r, Candidate) else dict(r) for r in rows]


def _posix(rel: str) -> str:
    return rel.replace("\\", "/").lstrip("./")


def is_workflow_path(rel: str) -> bool:
    path = _posix(rel)
    if path.endswith(WORKFLOW_SUFFIXES):
        if "/workflows/" in f"/{path}" or path.startswith("workflows/"):
            return True
        if path.endswith(".wf.json"):
            return True
    return False


def find_path(rows: Iterable[Candidate], rel: str) -> list[Candidate]:
    want = _posix(rel)
    return [r for r in rows if r.path == want]


def _run_git(root: Path, args: list[str], *, text: bool) -> subprocess.CompletedProcess:
    if args and args[0] == "archive":
        raise ArchiveForbidden("git archive is forbidden")
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=text,
        check=False,
    )


def git_bytes(root: Path, *args: str) -> bytes:
    if args and args[0] == "archive":
        raise ArchiveForbidden("git archive is forbidden")
    proc = _run_git(Path(root), list(args), text=False)
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {err}")
    return proc.stdout or b""


def fetch_bytes(root: Path, access_method: str) -> bytes:
    method = str(access_method or "")
    if method.startswith("git show "):
        spec = method[len("git show ") :].strip()
        return git_bytes(root, "show", spec)
    path = Path(method)
    if path.is_absolute():
        if not path.is_file():
            raise FileNotFoundError(method)
        return path.read_bytes()
    target = Path(root) / method
    if not target.is_file():
        raise FileNotFoundError(method)
    return target.read_bytes()


def _walk_worktree(root: Path) -> list[Path]:
    out: list[Path] = []
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        base = Path(dirpath)
        for name in filenames:
            path = base / name
            try:
                rel = path.relative_to(root).as_posix()
            except ValueError:
                continue
            if is_workflow_path(rel):
                out.append(path)
    return out


def _worktree_rows(root: Path) -> list[Candidate]:
    rows: list[Candidate] = []
    for path in _walk_worktree(root):
        rel = path.relative_to(root).as_posix()
        data = path.read_bytes()
        rows.append(
            Candidate(
                path=rel,
                access_method=rel,
                content_hash=sha256_bytes(data),
                location="worktree",
                ref=None,
            )
        )
    return rows


def _remote_refs(root: Path) -> list[str]:
    proc = _run_git(root, ["for-each-ref", "--format=%(refname:short)", "refs/remotes"], text=True)
    if proc.returncode != 0:
        return []
    return [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]


def _ls_tree(root: Path, ref: str) -> list[str]:
    proc = _run_git(root, ["ls-tree", "-r", "--name-only", ref], text=True)
    if proc.returncode != 0:
        return []
    return [ln.strip().replace("\\", "/") for ln in (proc.stdout or "").splitlines() if ln.strip()]


def _ref_rows(root: Path, worktree_paths: set[str]) -> list[Candidate]:
    rows: list[Candidate] = []
    seen: set[tuple[str, str]] = set()
    for ref in _remote_refs(root):
        for rel in _ls_tree(root, ref):
            if not is_workflow_path(rel):
                continue
            if rel in worktree_paths:
                continue
            key = (ref, rel)
            if key in seen:
                continue
            seen.add(key)
            data = git_bytes(root, "show", f"{ref}:{rel}")
            rows.append(
                Candidate(
                    path=rel,
                    access_method=f"git show {ref}:{rel}",
                    content_hash=sha256_bytes(data),
                    location="ref",
                    ref=ref,
                )
            )
    return rows


def _linked_worktrees(root: Path) -> list[Path]:
    proc = _run_git(root, ["worktree", "list", "--porcelain"], text=True)
    if proc.returncode != 0:
        return []
    primary = root.resolve()
    out: list[Path] = []
    current: Path | None = None
    for line in (proc.stdout or "").splitlines():
        if line.startswith("worktree "):
            current = Path(line.split(" ", 1)[1].strip())
        elif line.strip() == "":
            if current is not None:
                try:
                    if current.resolve() != primary:
                        out.append(current)
                except OSError:
                    pass
            current = None
    if current is not None:
        try:
            if current.resolve() != primary:
                out.append(current)
        except OSError:
            pass
    return out


def _linked_rows(root: Path, linked: Path) -> list[Candidate]:
    rows: list[Candidate] = []
    if not linked.is_dir():
        return rows
    try:
        linked_root = linked.resolve()
    except OSError:
        return rows
    for path in _walk_worktree(linked_root):
        rel = path.relative_to(linked_root).as_posix()
        data = path.read_bytes()
        rows.append(
            Candidate(
                path=rel,
                access_method=str(path),
                content_hash=sha256_bytes(data),
                location="linked-worktree",
                ref=None,
            )
        )
    return rows


def discover_local(
    root: Path | str,
    include_refs: bool = False,
    include_linked_worktrees: bool = False,
) -> list[Candidate]:
    base = Path(root)
    work = _worktree_rows(base)
    rows = list(work)
    worktree_paths = {r.path for r in work}
    if include_refs:
        rows.extend(_ref_rows(base, worktree_paths))
    if include_linked_worktrees:
        for linked in _linked_worktrees(base):
            rows.extend(_linked_rows(base, linked))
    return rows
