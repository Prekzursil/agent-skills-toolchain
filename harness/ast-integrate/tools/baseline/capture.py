"""Capture a pinned-SHA baseline snapshot (TST-0023).

SHA-ANCHORED facts are read from the git object database at ``pinned_sha``:
``git ls-tree -r`` gives the tracked path -> blob map and ``git cat-file
--batch-check`` gives every blob's size. Working-tree bytes are never the
oracle for them, so a recapture at the same SHA reproduces them exactly while
an untracked hook, a cache blob or an extra branch cannot move them.

Facts that cannot be recovered from the commit -- local branches, linked
worktrees, deploy artifacts, caches and worktree walks that see untracked
files -- are SAMPLED-AT-TIME and carry ``sampled_at``. ``kind`` is itself a
sample: ``BASELINE`` only when HEAD equals ``pinned_sha`` and ``git status
--porcelain`` is empty; anything else is ``SAMPLE``.

The snapshot shape is ``command-center/schema/baseline-snapshot.schema.json``
(top level is closed: no extra keys).
"""
from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable

from baseline.anchoring import SAMPLED_AT_TIME, SHA_ANCHORED

READER_TREE = "git-ls-tree-and-cat-file"
READER_WALK = "worktree-walk"
READER_REFS = "git-for-each-ref"
READER_WORKTREES = "git-worktree-list"
STATUS_MEASURED = "MEASURED"
STATUS_NOT_CHECKED = "NOT-CHECKED"
KIND_BASELINE = "BASELINE"
KIND_SAMPLE = "SAMPLE"

CACHE_DIR_NAMES: frozenset[str] = frozenset(
    {
        ".cache",
        "__pycache__",
        "node_modules",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".tox",
        ".nox",
        ".uv-cache",
    }
)
DEPLOY_DIR_NAMES: tuple[str, ...] = ("dist", "build", "deploy", ".deploy", "site")

# Tracked-path selectors for the SHA-anchored class objects (posix, repo-relative).
_TREE_CLASSES: dict[str, Callable[[str], bool]] = {
    "hooks_tree": lambda p: p.startswith("hooks/"),
    "skills_tree": lambda p: p.startswith("skills/"),
    "mcps_tree": lambda p: p.startswith("mcp/") or p == ".mcp.json",
    "plugin_settings_tree": lambda p: p.startswith("plugins/"),
    "marketplaces_tree": lambda p: p.startswith("marketplaces/"),
}
# Worktree-walk roots for the sampled twins (directories relative to root, plus files).
_LIVE_CLASSES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "hooks_live": (("hooks",), ()),
    "skills_live": (("skills",), ()),
    "mcps_live": (("mcp",), (".mcp.json",)),
    "plugin_settings_live": (("plugins",), ()),
    "marketplaces_live": (("marketplaces",), ()),
}

CLASS_INDEX: list[dict[str, Any]] = [
    {
        "class": "repo",
        "fields": ["repo", "files", "pinned_sha", "tree_sha"],
        "sha_anchored": True,
        "anchored_fields": ["repo", "files", "pinned_sha", "tree_sha"],
        "sampled_fields": [],
    },
    {
        "class": "branches",
        "fields": ["branches"],
        "sha_anchored": False,
        "anchored_fields": [],
        "sampled_fields": ["branches"],
    },
    {
        "class": "worktrees",
        "fields": ["worktrees"],
        "sha_anchored": False,
        "anchored_fields": [],
        "sampled_fields": ["worktrees"],
    },
    {
        "class": "live_deployments",
        "fields": ["live_deployments"],
        "sha_anchored": False,
        "anchored_fields": [],
        "sampled_fields": ["live_deployments"],
    },
    {
        "class": "caches",
        "fields": ["caches"],
        "sha_anchored": False,
        "anchored_fields": [],
        "sampled_fields": ["caches"],
    },
    {
        "class": "plugin_settings",
        "fields": ["plugin_settings_tree"],
        "sha_anchored": True,
        "anchored_fields": ["plugin_settings_tree"],
        "sampled_fields": ["plugin_settings_live"],
    },
    {
        "class": "marketplaces",
        "fields": ["marketplaces_tree"],
        "sha_anchored": True,
        "anchored_fields": ["marketplaces_tree"],
        "sampled_fields": ["marketplaces_live"],
    },
    {
        "class": "hooks",
        "fields": ["hooks_tree"],
        "sha_anchored": True,
        "anchored_fields": ["hooks_tree"],
        "sampled_fields": ["hooks_live"],
    },
    {
        "class": "skills",
        "fields": ["skills_tree"],
        "sha_anchored": True,
        "anchored_fields": ["skills_tree"],
        "sampled_fields": ["skills_live"],
    },
    {
        "class": "mcps",
        "fields": ["mcps_tree"],
        "sha_anchored": True,
        "anchored_fields": ["mcps_tree"],
        "sampled_fields": ["mcps_live"],
    },
]

__all__ = [
    "READER_TREE",
    "READER_WALK",
    "CACHE_DIR_NAMES",
    "DEPLOY_DIR_NAMES",
    "CLASS_INDEX",
    "GitError",
    "git_env",
    "git",
    "git_text",
    "resolve_sha",
    "tree_files",
    "blob_sizes",
    "capture",
]


class GitError(RuntimeError):
    """A git command exited non-zero (stderr is in the message)."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _stamp(now: Any) -> str:
    if now is None:
        return _now()
    if isinstance(now, datetime):
        return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(now)


def git_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """Environment for git subprocesses that isolates them from the host user.

    System and global config are ignored (no autocrlf, hooksPath or signing
    surprises), prompts are off, output is C-locale, a fallback identity is
    present so fixture commits work on a bare box, and any ``GIT_DIR`` /
    ``GIT_WORK_TREE`` / ``GIT_INDEX_FILE`` exported by a calling hook is dropped
    so commands act on the ``cwd`` they are given.
    """
    env = dict(os.environ if base is None else base)
    for leaked in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_PREFIX"):
        env.pop(leaked, None)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env.setdefault("LC_ALL", "C")
    env.setdefault("GIT_AUTHOR_NAME", "baseline-capture")
    env.setdefault("GIT_AUTHOR_EMAIL", "baseline-capture@local")
    env.setdefault("GIT_COMMITTER_NAME", env["GIT_AUTHOR_NAME"])
    env.setdefault("GIT_COMMITTER_EMAIL", env["GIT_AUTHOR_EMAIL"])
    return env


def git(
    root: Path | str,
    *args: str,
    check: bool = True,
    input: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Run ``git <args>`` in ``root`` with ``git_env``; raise ``GitError`` on failure."""
    proc = subprocess.run(
        ["git", *args],
        cwd=str(root),
        env=git_env(),
        input=input,
        capture_output=True,
        check=False,
    )
    if check and proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip()
        raise GitError(f"git {' '.join(args)} failed in {root} (rc={proc.returncode}): {err}")
    return proc


def git_text(root: Path | str, *args: str, check: bool = True) -> str:
    """``git`` stdout decoded as UTF-8 (undecodable bytes replaced)."""
    return git(root, *args, check=check).stdout.decode("utf-8", "replace")


def is_git_worktree(root: Path | str) -> bool:
    """True when ``root`` lies inside a git working tree."""
    proc = git(root, "rev-parse", "--is-inside-work-tree", check=False)
    return proc.returncode == 0 and proc.stdout.strip() == b"true"


def resolve_sha(root: Path | str, sha: str | None = None) -> str | None:
    """Full 40-hex commit id for ``sha`` (default HEAD), or None when unresolvable."""
    proc = git(root, "rev-parse", "--verify", "--quiet", f"{sha or 'HEAD'}^{{commit}}", check=False)
    if proc.returncode != 0:
        return None
    text = proc.stdout.decode("ascii", "replace").strip()
    return text if len(text) == 40 else None


def _prefix(root: Path | str) -> str:
    """``root``'s path inside its repository ('' at the top level), posix with trailing slash."""
    proc = git(root, "rev-parse", "--show-prefix", check=False)
    if proc.returncode != 0:
        return ""
    return proc.stdout.decode("utf-8", "replace").strip()


def tree_files(root: Path | str, sha: str) -> dict[str, str]:
    """Tracked posix path -> blob id under ``root`` at ``sha`` (``git ls-tree -r -z``).

    Paths are relative to ``root``; without ``--full-tree`` git limits the
    listing to the current directory's subtree. Only blobs are returned
    (submodule commits are not files of this tree).
    """
    out = git(root, "ls-tree", "-r", "-z", sha).stdout
    files: dict[str, str] = {}
    for entry in out.split(b"\0"):
        if not entry:
            continue
        meta, _, path = entry.partition(b"\t")
        parts = meta.split()
        if len(parts) != 3 or parts[1] != b"blob":
            continue
        files[path.decode("utf-8", "surrogateescape")] = parts[2].decode("ascii")
    return dict(sorted(files.items()))


def blob_sizes(root: Path | str, shas: Iterable[str]) -> dict[str, int | None]:
    """Blob id -> size in bytes via one ``git cat-file --batch-check`` (None when missing)."""
    wanted = sorted(set(shas))
    if not wanted:
        return {}
    out = git(root, "cat-file", "--batch-check", input=("\n".join(wanted) + "\n").encode("ascii")).stdout
    sizes: dict[str, int | None] = {}
    for line in out.decode("ascii", "replace").splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[1] == "blob":
            sizes[parts[0]] = int(parts[2])
        elif parts:
            sizes[parts[0]] = None
    return sizes


def _anchored(
    cls: str,
    pinned_sha: str | None,
    tree_sha: str | None,
    files: dict[str, str],
    sizes: dict[str, int | None],
    selector: Callable[[str], bool] | None,
    *,
    with_paths: bool,
    not_checked_reason: str | None = None,
) -> dict[str, Any]:
    if pinned_sha is None:
        return {
            "class": cls,
            "anchoring_kind": SHA_ANCHORED,
            "reader": READER_TREE,
            "pinned_sha": None,
            "tree_sha": None,
            "count": None,
            "status": STATUS_NOT_CHECKED,
            "not_checked_reason": not_checked_reason or "no git database",
        }
    chosen = {p: s for p, s in files.items() if selector is None or selector(p)}
    total = 0
    missing: list[str] = []
    for path, blob in chosen.items():
        size = sizes.get(blob)
        if size is None:
            missing.append(path)
        else:
            total += size
    out: dict[str, Any] = {
        "class": cls,
        "anchoring_kind": SHA_ANCHORED,
        "reader": READER_TREE,
        "pinned_sha": pinned_sha,
        "tree_sha": tree_sha,
        "count": len(chosen),
        "bytes": total,
        "status": STATUS_MEASURED,
    }
    if with_paths:
        out["paths"] = sorted(chosen)
        out["blobs"] = dict(sorted(chosen.items()))
    if missing:
        out["missing_blobs"] = sorted(missing)
    return out


def _walk_files(base: Path, rel_root: Path) -> list[str]:
    """Posix paths (relative to ``rel_root``) of every file under ``base``, skipping ``.git``."""
    if not base.is_dir():
        return []
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d != ".git")
        for name in filenames:
            path = Path(dirpath) / name
            found.append(PurePosixPath(path.relative_to(rel_root)).as_posix())
    return sorted(found)


def _sampled(cls: str, reader: str, paths: list[str], sampled_at: str) -> dict[str, Any]:
    return {
        "class": cls,
        "anchoring_kind": SAMPLED_AT_TIME,
        "reader": reader,
        "count": len(paths),
        "sampled_at": sampled_at,
        "paths": paths,
    }


def _live_walk(root: Path, dirs: tuple[str, ...], files: tuple[str, ...]) -> list[str]:
    paths: list[str] = []
    for d in dirs:
        paths.extend(_walk_files(root / d, root))
    for f in files:
        if (root / f).is_file():
            paths.append(f)
    return sorted(set(paths))


def _cache_paths(root: Path) -> list[str]:
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d != ".git")
        rel_parts = Path(dirpath).relative_to(root).parts
        if any(part in CACHE_DIR_NAMES for part in rel_parts):
            for name in filenames:
                found.append(PurePosixPath(Path(dirpath, name).relative_to(root)).as_posix())
    return sorted(found)


def _branches(root: Path) -> list[str]:
    proc = git(root, "for-each-ref", "--format=%(refname:short)", "refs/heads", check=False)
    if proc.returncode != 0:
        return []
    return sorted(line for line in proc.stdout.decode("utf-8", "replace").splitlines() if line)


def _worktrees(root: Path) -> list[str]:
    proc = git(root, "worktree", "list", "--porcelain", check=False)
    if proc.returncode != 0:
        return []
    return sorted(
        line[len("worktree ") :]
        for line in proc.stdout.decode("utf-8", "replace").splitlines()
        if line.startswith("worktree ")
    )


def _kind(root: Path, pinned_sha: str | None) -> str:
    """BASELINE only when HEAD == pinned_sha and the worktree (under root) is porcelain-clean."""
    if pinned_sha is None:
        return KIND_SAMPLE
    head = resolve_sha(root, "HEAD")
    if head != pinned_sha:
        return KIND_SAMPLE
    status = git(root, "status", "--porcelain", "--untracked-files=all", "--", ".", check=False)
    if status.returncode != 0 or status.stdout.strip():
        return KIND_SAMPLE
    return KIND_BASELINE


def capture(root: Path | str, sha: str | None = None, now: Any = None) -> dict[str, Any]:
    """Snapshot ``root`` with SHA-anchored facts read at ``sha`` (default HEAD).

    ``now`` pins ``captured_at`` / ``sampled_at`` (a string or datetime) so two
    captures can be compared without clock noise; the anchored projection is
    identical for equal ``sha`` regardless. A root without a git database yields
    ``pinned_sha`` None and NOT-CHECKED anchored objects rather than zeros.
    """
    root = Path(root)
    stamp = _stamp(now)
    pinned = resolve_sha(root, sha) if is_git_worktree(root) else None
    reason = None if pinned is not None else (
        "no git database under root" if not is_git_worktree(root) else f"unresolvable sha {sha!r}"
    )

    files: dict[str, str] = {}
    tree_sha: str | None = None
    sizes: dict[str, int | None] = {}
    if pinned is not None:
        files = tree_files(root, pinned)
        prefix = _prefix(root).rstrip("/")
        tree_spec = f"{pinned}:{prefix}" if prefix else f"{pinned}^{{tree}}"
        proc = git(root, "rev-parse", "--verify", "--quiet", tree_spec, check=False)
        if proc.returncode == 0:
            tree_sha = proc.stdout.decode("ascii", "replace").strip() or None
        sizes = blob_sizes(root, files.values())

    snap: dict[str, Any] = {
        "kind": _kind(root, pinned),
        "captured_at": stamp,
        "pinned_sha": pinned,
        "tree_sha": tree_sha,
        "files": files,
        "repo": _anchored(
            "repo", pinned, tree_sha, files, sizes, None, with_paths=False, not_checked_reason=reason
        ),
    }
    for cls, selector in _TREE_CLASSES.items():
        snap[cls] = _anchored(
            cls, pinned, tree_sha, files, sizes, selector, with_paths=True, not_checked_reason=reason
        )

    snap["branches"] = _sampled("branches", READER_REFS, _branches(root), stamp)
    snap["worktrees"] = _sampled("worktrees", READER_WORKTREES, _worktrees(root), stamp)
    snap["live_deployments"] = _sampled(
        "live_deployments", READER_WALK, _live_walk(root, DEPLOY_DIR_NAMES, ()), stamp
    )
    snap["caches"] = _sampled("caches", READER_WALK, _cache_paths(root), stamp)
    for cls, (dirs, extra_files) in _LIVE_CLASSES.items():
        snap[cls] = _sampled(cls, READER_WALK, _live_walk(root, dirs, extra_files), stamp)
    return snap
