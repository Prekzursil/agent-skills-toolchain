"""Repo-vs-live registration reconciler. Reports both directions; never deploys."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

KINDS = ("skill", "hook", "rule", "command")


def _load(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return doc if isinstance(doc, dict) else {}


def enumerate_fs(root: str | Path) -> dict[str, set[str]]:
    root = Path(root)
    out: dict[str, set[str]] = {k: set() for k in KINDS}
    skills = root / "skills"
    if skills.is_dir():
        for dirpath, dirnames, filenames in os.walk(skills):
            dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__"}]
            if "SKILL.md" in filenames:
                rel = Path(dirpath).relative_to(skills).as_posix()
                out["skill"].add(rel)
    hooks = root / "hooks"
    if hooks.is_dir():
        for dirpath, dirnames, filenames in os.walk(hooks):
            dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__"}]
            for name in filenames:
                if not name.endswith(".json"):
                    continue
                low = name.lower()
                if low == "manifest.json" or low.endswith("-manifest.json"):
                    continue
                stem = Path(name).stem
                if stem.startswith("hook."):
                    stem = stem[5:]
                out["hook"].add(stem)
    rules = root / "rules"
    if rules.is_dir():
        for dirpath, dirnames, filenames in os.walk(rules):
            dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__"}]
            for name in filenames:
                if name.endswith(".md"):
                    rel = (Path(dirpath) / name).relative_to(rules).as_posix()
                    out["rule"].add(rel)
    commands = root / "commands"
    if commands.is_dir():
        for dirpath, dirnames, filenames in os.walk(commands):
            dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__"}]
            for name in filenames:
                low = name.lower()
                if low.endswith("-manifest.json") or low == "manifest.json":
                    continue
                rel = (Path(dirpath) / name).relative_to(commands).as_posix()
                out["command"].add(rel)
    return out


def enumerate_manifest(root: str | Path) -> dict[str, set[str]]:
    root = Path(root)
    out: dict[str, set[str]] = {k: set() for k in KINDS}
    for item in _load(root / "skills" / "DEPLOYED-MANIFEST.json").get("skills") or []:
        if isinstance(item, str):
            out["skill"].add(item)
    for item in _load(root / "hooks" / "_dispatch" / "manifest.json").get("hooks") or []:
        if isinstance(item, str):
            out["hook"].add(item)
    for item in _load(root / "rules" / "RULES-MANIFEST.json").get("rules") or []:
        if isinstance(item, str):
            out["rule"].add(item)
    for item in _load(root / "commands" / "COMMANDS-MANIFEST.json").get("commands") or []:
        if isinstance(item, str):
            out["command"].add(item)
    return out


def flatten(grouped: dict[str, Iterable[str]]) -> set[str]:
    ids: set[str] = set()
    for kind, items in grouped.items():
        for item in items:
            ids.add(f"{kind}:{item}")
    return ids


def snapshot_tree(root: str | Path) -> dict[str, str]:
    root = Path(root)
    snap: dict[str, str] = {}
    if not root.is_dir():
        return snap
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__"}]
        for name in filenames:
            path = Path(dirpath) / name
            rel = path.relative_to(root).as_posix()
            snap[rel] = f"{path.stat().st_size}:{path.stat().st_mtime_ns}"
    return snap


def host_candidates(repo: str | Path) -> list[dict[str, Any]]:
    repo = Path(repo)
    homes = [
        repo / "skills",
        Path.home() / ".claude" / "skills",
        Path.home() / ".codex" / "skills",
        Path.home() / ".agents" / "skills",
    ]
    rows = []
    for path in homes:
        n = 0
        if path.is_dir():
            n = sum(1 for _ in path.rglob("*") if _.is_file())
        rows.append(
            {
                "path": str(path),
                "is_dir": path.is_dir(),
                "file_count": n,
                "kind": path.name,
            }
        )
    return rows


def reconcile(repo_root: str | Path, live_root: str | Path) -> dict[str, Any]:
    repo_root = Path(repo_root)
    live_root = Path(live_root)
    fs_repo = flatten(enumerate_fs(repo_root))
    fs_live = flatten(enumerate_fs(live_root))
    man_repo = flatten(enumerate_manifest(repo_root))
    man_live = flatten(enumerate_manifest(live_root))
    repo_only = sorted(fs_repo - fs_live)
    live_only = sorted(fs_live - fs_repo)
    in_both = sorted(fs_repo & fs_live)
    sets_agree = fs_repo == man_repo and fs_live == man_live
    in_sync = not repo_only and not live_only
    return {
        "method": "filesystem-walk",
        "independent_method": "kind-manifest-parse",
        "repo_only": repo_only,
        "live_only": live_only,
        "in_both": in_both,
        "counts": {
            "repo_only": len(repo_only),
            "live_only": len(live_only),
            "in_both": len(in_both),
            "repo_fs": len(fs_repo),
            "live_fs": len(fs_live),
        },
        "sets_agree": sets_agree,
        "auto_deploy": False,
        "writes": [],
        "live_tree_mutated": False,
        "live_only_measured": True,
        "live_only_assumed_empty": False,
        "in_sync": in_sync,
        "live_surface": str(live_root),
        "fs_repo": sorted(fs_repo),
        "fs_live": sorted(fs_live),
        "manifest_repo": sorted(man_repo),
        "manifest_live": sorted(man_live),
    }
