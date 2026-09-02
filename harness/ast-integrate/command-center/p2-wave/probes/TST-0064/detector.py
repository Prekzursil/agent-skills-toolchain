"""Case-fold path collision detector and gate for TST-0064.

A pair of tracked (or worktree) paths collides when they are distinct strings
but equal after Unicode casefold. That pair checks out as one file on
Windows/macOS default filesystems. The git index is case-sensitive, so the
detector prefers `git ls-files` when a git worktree is present and otherwise
walks regular files.

A string-comparing control that only looks at exact-path uniqueness is
SILENT on a planted Foo.md/foo.md pair — that is the hole this detector
exists to close.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Iterable

SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "__pycache__",
        ".pytest_cache",
        "node_modules",
        ".venv",
        "venv",
        ".mypy_cache",
        ".tox",
        ".eggs",
        ".cursor",
    }
)

PLANTED_UPPER = "Foo.md"
PLANTED_LOWER = "foo.md"
CLEAN_A = "README.md"
CLEAN_B = "docs/readme.md"
# Outputs this unit writes during emit/measure. Including them in the live
# listing makes path_count drift between emit and the re-run probes.
SELF_OUTPUT_PATHS = frozenset(
    {
        "command-center/receipts/TST-0064.json",
        "command-center/p2-wave/probes/TST-0064/SUBAGENT-RETURN.json",
        "command-center/p2-wave/probes/TST-0064/UNIT-ARTIFACT-MANIFEST.json",
    }
)


def posix(rel: str) -> str:
    return rel.replace("\\", "/").lstrip("./")


def fold(rel: str) -> str:
    return posix(rel).casefold()


def git_ls_files(root: Path) -> list[str] | None:
    """Return tracked paths, or None if root is not a git worktree."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return [posix(p) for p in proc.stdout.split("\0") if p]


def walk_files(root: Path) -> list[str]:
    """Worktree walk used when no git index exists."""
    root = Path(root)
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(
            d
            for d in dirnames
            if d not in SKIP_DIR_NAMES and not d.endswith(".egg-info")
        )
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if path.is_symlink() or not path.is_file():
                continue
            out.append(posix(path.relative_to(root).as_posix()))
    return out


def listed_paths(root: Path) -> tuple[list[str], str]:
    tracked = git_ls_files(root)
    if tracked is not None:
        paths, source = tracked, "git-ls-files"
    else:
        paths, source = walk_files(root), "worktree-walk"
    filtered = [p for p in paths if posix(p) not in SELF_OUTPUT_PATHS]
    return filtered, source


def collision_groups(paths: Iterable[str]) -> list[dict]:
    buckets: dict[str, list[str]] = defaultdict(list)
    for raw in paths:
        p = posix(raw)
        buckets[fold(p)].append(p)
    groups: list[dict] = []
    for key, members in buckets.items():
        uniq = sorted(set(members))
        if len(uniq) >= 2:
            groups.append({"casefold": key, "paths": uniq, "count": len(uniq)})
    groups.sort(key=lambda g: g["casefold"])
    return groups


def exact_duplicate_groups(paths: Iterable[str]) -> list[dict]:
    """String-comparing control: only identical path strings, not casefold."""
    buckets: dict[str, int] = defaultdict(int)
    for raw in paths:
        buckets[posix(raw)] += 1
    return [
        {"path": p, "count": n}
        for p, n in sorted(buckets.items())
        if n >= 2
    ]


def census(root: Path) -> dict:
    root = Path(root)
    paths, source = listed_paths(root)
    groups = collision_groups(paths)
    exact = exact_duplicate_groups(paths)
    return {
        "root": str(root),
        "source": source,
        "git_index_present": source == "git-ls-files",
        "path_count": len(paths),
        "unique_path_count": len(set(map(posix, paths))),
        "collision_group_count": len(groups),
        "colliding_path_count": sum(int(g["count"]) for g in groups),
        "collisions": groups,
        "exact_duplicate_group_count": len(exact),
        "exact_duplicates": exact,
    }


def gate(census_doc: dict) -> dict:
    fired = int(census_doc.get("collision_group_count") or 0) > 0
    return {
        "name": "casefold-path-collision-gate",
        "mechanism": "group listed paths by str.casefold; fire when any group has >=2 distinct strings",
        "fired": fired,
        "silent": not fired,
        "collision_group_count": int(census_doc.get("collision_group_count") or 0),
        "path_count": int(census_doc.get("path_count") or 0),
    }


def naive_exact_gate(census_doc: dict) -> dict:
    fired = int(census_doc.get("exact_duplicate_group_count") or 0) > 0
    return {
        "name": "exact-path-string-gate",
        "mechanism": "group listed paths by exact string equality only",
        "fired": fired,
        "silent": not fired,
        "exact_duplicate_group_count": int(
            census_doc.get("exact_duplicate_group_count") or 0
        ),
    }


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.setdefault("GIT_AUTHOR_NAME", "TST-0064")
    env.setdefault("GIT_AUTHOR_EMAIL", "tst-0064@invalid")
    env.setdefault("GIT_COMMITTER_NAME", "TST-0064")
    env.setdefault("GIT_COMMITTER_EMAIL", "tst-0064@invalid")
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=check,
        env=env,
        timeout=60,
    )


def _init_scratch(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "core.ignorecase", "false")
    _git(repo, "config", "user.email", "tst-0064@invalid")
    _git(repo, "config", "user.name", "TST-0064")


def plant_colliding_scratch(parent: Path | None = None) -> Path:
    """Scratch git repo carrying Foo.md and foo.md (Linux can store both)."""
    parent = Path(parent) if parent is not None else Path(tempfile.mkdtemp(prefix="tst0064-hit-"))
    repo = parent / "colliding"
    _init_scratch(repo)
    (repo / PLANTED_UPPER).write_text("UPPER-CASE-NAME\n", encoding="utf-8")
    (repo / PLANTED_LOWER).write_text("lower-case-name\n", encoding="utf-8")
    (repo / "unique.txt").write_text("unique\n", encoding="utf-8")
    _git(repo, "add", "-f", PLANTED_UPPER, PLANTED_LOWER, "unique.txt")
    _git(repo, "commit", "-m", "plant case-colliding pair")
    return repo


def plant_clean_scratch(parent: Path | None = None) -> Path:
    """Scratch git repo with case-distinct paths that do not collide."""
    parent = Path(parent) if parent is not None else Path(tempfile.mkdtemp(prefix="tst0064-clean-"))
    repo = parent / "clean"
    _init_scratch(repo)
    (repo / CLEAN_A).write_text("readme\n", encoding="utf-8")
    docs = repo / "docs"
    docs.mkdir()
    (repo / CLEAN_B).write_text("docs-readme\n", encoding="utf-8")
    _git(repo, "add", "-f", CLEAN_A, CLEAN_B)
    _git(repo, "commit", "-m", "non-colliding case-distinct pair")
    return repo


def both_states_control(parent: Path | None = None) -> dict:
    """Plant a colliding pair and a clean pair; require fire XOR silent."""
    base = Path(parent) if parent is not None else Path(
        tempfile.mkdtemp(prefix="tst0064-both-")
    )
    hit = plant_colliding_scratch(base)
    clean = plant_clean_scratch(base)
    hit_c = census(hit)
    clean_c = census(clean)
    hit_g = gate(hit_c)
    clean_g = gate(clean_c)
    naive = naive_exact_gate(hit_c)
    tracked = set(git_ls_files(hit) or [])
    planted_found = {PLANTED_UPPER, PLANTED_LOWER}.issubset(tracked)
    xor = bool(hit_g["fired"]) and bool(clean_g["silent"])
    return {
        "colliding_root": str(hit),
        "clean_root": str(clean),
        "colliding": hit_c,
        "clean": clean_c,
        "gate_on_plant": hit_g,
        "gate_on_clean": clean_g,
        "naive_exact_on_plant": naive,
        "git_ls_files_contains_planted_pair": planted_found,
        "tracked_on_plant": sorted(tracked),
        "fired_in_exactly_one_condition": xor,
        "planted_pair": [PLANTED_UPPER, PLANTED_LOWER],
        "clean_pair": [CLEAN_A, CLEAN_B],
    }


def assumed_zero(_root: Path) -> dict:
    """Known-broken census: skip the walk and report zero. Detector control."""
    return {
        "source": "assumed-zero",
        "git_index_present": False,
        "path_count": 0,
        "unique_path_count": 0,
        "collision_group_count": 0,
        "colliding_path_count": 0,
        "collisions": [],
        "exact_duplicate_group_count": 0,
        "exact_duplicates": [],
    }
