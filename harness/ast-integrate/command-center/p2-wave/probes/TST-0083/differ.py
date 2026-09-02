#!/usr/bin/env python3
"""Deterministic repo-vs-live skill reconciler for TST-0083.

A skill is a directory that contains SKILL.md. Identity is the posix path
of that directory relative to the skills root. Content identity is the
ordered map of skill-relative file paths to SHA-256 of LF-normalized
bytes. Nested skills are split: files under a child SKILL.md belong to
the child, not the parent.

This is an availability instrument, not a sync tool. It reports
repo-only / live-only / content-divergent sets and which catalogued
skills a live router cannot load. It never copies or deletes files.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

SKIP_DIRS = frozenset({".git", "__pycache__", ".mypy_cache", "node_modules", ".pytest_cache"})
SKILL_FILE = "SKILL.md"


def lf_bytes(raw: bytes) -> bytes:
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def sha256_lf(raw: bytes) -> str:
    return hashlib.sha256(lf_bytes(raw)).hexdigest()


def _skip_parts(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def discover_skill_dirs(root: Path) -> dict[str, Path]:
    """Map skill-id -> absolute skill directory. Empty if root is missing."""
    found: dict[str, Path] = {}
    if not root.is_dir():
        return found
    for marker in root.rglob(SKILL_FILE):
        if not marker.is_file() or _skip_parts(marker):
            continue
        skill_dir = marker.parent
        rel = skill_dir.relative_to(root).as_posix()
        found[rel] = skill_dir
    return dict(sorted(found.items()))


def _belongs_to(skill_dir: Path, file_path: Path, child_dirs: list[Path]) -> bool:
    for child in child_dirs:
        try:
            file_path.relative_to(child)
            return False
        except ValueError:
            continue
    return True


def inventory_skill(skill_dir: Path, sibling_skill_dirs: list[Path]) -> dict[str, Any]:
    children = [
        d
        for d in sibling_skill_dirs
        if d != skill_dir and d.is_relative_to(skill_dir)
    ]
    files: dict[str, str] = {}
    for path in skill_dir.rglob("*"):
        if not path.is_file() or _skip_parts(path.relative_to(skill_dir)):
            continue
        if not _belongs_to(skill_dir, path, children):
            continue
        rel = path.relative_to(skill_dir).as_posix()
        files[rel] = sha256_lf(path.read_bytes())
    files = dict(sorted(files.items()))
    payload = "".join(f"{k}={v}\n" for k, v in files.items()).encode("utf-8")
    return {
        "skill_id": skill_dir.name,
        "files": files,
        "file_list": list(files.keys()),
        "digest": hashlib.sha256(payload).hexdigest(),
        "bytes": sum(path.stat().st_size for path in skill_dir.rglob("*") if path.is_file()),
    }


def inventory(root: Path) -> dict[str, dict[str, Any]]:
    dirs = discover_skill_dirs(root)
    abs_dirs = list(dirs.values())
    out: dict[str, dict[str, Any]] = {}
    for skill_id, skill_dir in dirs.items():
        rec = inventory_skill(skill_dir, abs_dirs)
        rec["skill_id"] = skill_id
        rec["root"] = str(root)
        rec["path"] = str(skill_dir)
        out[skill_id] = rec
    return out


def reconcile(repo_root: Path, live_root: Path) -> dict[str, Any]:
    repo = inventory(repo_root)
    live = inventory(live_root)
    repo_ids = set(repo)
    live_ids = set(live)
    repo_only_ids = sorted(repo_ids - live_ids)
    live_only_ids = sorted(live_ids - repo_ids)
    shared = sorted(repo_ids & live_ids)
    identical_ids: list[str] = []
    divergent_ids: list[str] = []
    divergent_rows: list[dict[str, Any]] = []
    for skill_id in shared:
        if repo[skill_id]["digest"] == live[skill_id]["digest"]:
            identical_ids.append(skill_id)
        else:
            divergent_ids.append(skill_id)
            repo_files = repo[skill_id]["files"]
            live_files = live[skill_id]["files"]
            only_repo = sorted(set(repo_files) - set(live_files))
            only_live = sorted(set(live_files) - set(repo_files))
            changed = sorted(
                p
                for p in (set(repo_files) & set(live_files))
                if repo_files[p] != live_files[p]
            )
            divergent_rows.append(
                {
                    "skill_id": skill_id,
                    "repo_digest": repo[skill_id]["digest"],
                    "live_digest": live[skill_id]["digest"],
                    "files_changed": changed,
                    "files_repo_only": only_repo,
                    "files_live_only": only_live,
                    "file_list": sorted(set(repo_files) | set(live_files)),
                }
            )

    def pack(ids: list[str], side: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "skill_id": sid,
                "file_list": side[sid]["file_list"],
                "digest": side[sid]["digest"],
            }
            for sid in ids
        ]

    repo_only = pack(repo_only_ids, repo)
    live_only = pack(live_only_ids, live)
    routing = {
        "selectable_live_ids": sorted(live_ids),
        "catalogued_repo_ids": sorted(repo_ids),
        "unloadable_repo_only": repo_only_ids,
        "live_untracked": live_only_ids,
        "stale_or_forked": divergent_ids,
        "note": (
            "A live client loads the deployed skill tree. Repo-only skills are "
            "catalogued in the repository but cannot be selected for routing."
        ),
    }
    return {
        "repo_root": str(repo_root),
        "live_root": str(live_root),
        "repo_exists": repo_root.is_dir(),
        "live_exists": live_root.is_dir(),
        "repo_count": len(repo),
        "live_count": len(live),
        "counts": {
            "repo_only": len(repo_only_ids),
            "live_only": len(live_only_ids),
            "divergent": len(divergent_ids),
            "identical": len(identical_ids),
        },
        "repo_only": repo_only,
        "live_only": live_only,
        "divergent": divergent_rows,
        "identical": identical_ids,
        "routing": routing,
        "method": "set-difference-plus-lf-normalized-file-digest",
        "signals": ["presence", "sha256-lf"],
        "distinct_from_tst0079": (
            "TST-0079 tests sync-tool safety (refuse two-way overwrite). "
            "TST-0083 measures the availability consequence: repo-only skills "
            "are unloadable by a live router."
        ),
    }


def host_skill_roots(repo: Path) -> list[dict[str, Any]]:
    home = Path.home()
    candidates = [
        ("repo-skills", repo / "skills"),
        ("claude-live", home / ".claude" / "skills"),
        ("agents-live", home / ".agents" / "skills"),
        ("cursor-skills", home / ".cursor" / "skills"),
    ]
    rows = []
    for label, path in candidates:
        n = 0
        if path.is_dir():
            n = len(discover_skill_dirs(path))
        rows.append(
            {
                "label": label,
                "path": str(path),
                "exists": path.exists(),
                "is_dir": path.is_dir(),
                "skill_count": n,
            }
        )
    return rows


def route(skill_id: str, report: dict[str, Any]) -> dict[str, str]:
    live = set(report["routing"]["selectable_live_ids"])
    repo = set(report["routing"]["catalogued_repo_ids"])
    if skill_id in live:
        return {"skill_id": skill_id, "status": "AVAILABLE", "source": "live"}
    if skill_id in repo:
        return {
            "skill_id": skill_id,
            "status": "UNAVAILABLE",
            "reason": "repo-only-not-deployed",
        }
    return {"skill_id": skill_id, "status": "UNKNOWN", "reason": "not-in-either-tree"}
