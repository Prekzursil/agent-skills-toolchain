"""Live worktree scan for nested git entries and vendored-tree markers."""
from __future__ import annotations

import json
import os
from pathlib import Path

from finder import find_git_find_cmd, find_git_os_walk, paths_of
from fingerprint import tree_merkle

VENDOR_DIR_NAMES = frozenset(
    {
        "vendor",
        "third_party",
        "third-party",
        "_vendor",
        "vendored",
        "3rdparty",
        "3rd_party",
    }
)

LICENSE_NAMES = (
    "LICENSE",
    "LICENSE.md",
    "LICENSE.txt",
    "COPYING",
    "COPYING.md",
    "NOTICE",
    "NOTICE.md",
)


def repo_root() -> Path:
    # probes/AUD-0009 -> probes -> p2-wave -> command-center -> repo
    return Path(__file__).resolve().parent.parents[3]


def classify_git_role(rel: str) -> str:
    if rel == ".git":
        return "host-repo"
    if rel.endswith("/.git") or rel == ".git":
        return "nested"
    return "nested"


def extract_metadata(tree: Path) -> dict:
    meta: dict = {
        "upstream_url": None,
        "version": None,
        "license": None,
        "declared_name": None,
        "sources": [],
    }
    lock = tree / "package-lock.json"
    pkg = tree / "package.json"
    if lock.is_file():
        try:
            data = json.loads(lock.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            data = None
        if isinstance(data, dict):
            meta["declared_name"] = data.get("name") or meta["declared_name"]
            meta["version"] = data.get("version") or meta["version"]
            pkgs = data.get("packages") or {}
            root_pkg = pkgs.get("") if isinstance(pkgs, dict) else None
            if isinstance(root_pkg, dict):
                meta["license"] = root_pkg.get("license") or meta["license"]
                meta["declared_name"] = root_pkg.get("name") or meta["declared_name"]
                meta["version"] = root_pkg.get("version") or meta["version"]
            meta["sources"].append("package-lock.json")
    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            data = None
        if isinstance(data, dict):
            meta["declared_name"] = data.get("name") or meta["declared_name"]
            meta["version"] = data.get("version") or meta["version"]
            meta["license"] = data.get("license") or meta["license"]
            repo = data.get("repository")
            if isinstance(repo, str):
                meta["upstream_url"] = repo
            elif isinstance(repo, dict):
                meta["upstream_url"] = repo.get("url") or meta["upstream_url"]
            meta["sources"].append("package.json")
    for name in LICENSE_NAMES:
        p = tree / name
        if p.is_file():
            text = p.read_text(encoding="utf-8", errors="replace")[:2000]
            low = text.lower()
            if meta["license"] is None:
                if "mit license" in low or low.startswith("mit "):
                    meta["license"] = "MIT"
                elif "apache license" in low:
                    meta["license"] = "Apache-2.0"
                elif "bsd" in low:
                    meta["license"] = "BSD"
                else:
                    meta["license"] = f"see:{name}"
            meta["sources"].append(name)
            break
    return meta


def find_vendor_marker_dirs(root: Path) -> list[Path]:
    root = root.resolve()
    found: list[Path] = []
    for dirpath, dirnames, _filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        rel_dir = Path(dirpath).resolve().relative_to(root).as_posix()
        # Do not treat this unit's own probe dir as a product vendored tree.
        if rel_dir.startswith("command-center/p2-wave/probes/AUD-0009"):
            dirnames[:] = []
            continue
        marked = [n for n in list(dirnames) if n in VENDOR_DIR_NAMES]
        for name in marked:
            found.append(Path(dirpath) / name)
            dirnames.remove(name)
        if ".git" in dirnames:
            dirnames.remove(".git")
    found.sort()
    return found


def live_git_inventory(root: Path) -> dict:
    walk_hits = find_git_os_walk(root)
    find_hits = find_git_find_cmd(root)
    walk_paths = paths_of(walk_hits)
    find_paths = paths_of(find_hits)
    rows = []
    for rel in sorted(set(walk_paths) | set(find_paths)):
        w = next((h for h in walk_hits if h["path"] == rel), None)
        f = next((h for h in find_hits if h["path"] == rel), None)
        src = w or f or {}
        rows.append(
            {
                "path": rel,
                "kind": src.get("kind"),
                "form": src.get("form"),
                "gitdir": src.get("gitdir"),
                "role": classify_git_role(rel),
                "seen_by_os_walk": w is not None,
                "seen_by_find": f is not None,
            }
        )
    return {
        "os_walk_count": len(walk_paths),
        "find_count": len(find_paths),
        "paths_agree": walk_paths == find_paths,
        "entries": rows,
    }


def live_vendor_inventory(root: Path) -> list[dict]:
    rows = []
    for tree in find_vendor_marker_dirs(root):
        rel = tree.relative_to(root).as_posix()
        fp = tree_merkle(tree)
        meta = extract_metadata(tree)
        rows.append(
            {
                "path": rel,
                "marker": tree.name,
                "declared": False,
                "undeclared_copy_without_marker": False,
                "file_count": fp["file_count"],
                "content_merkle": fp["merkle"],
                "upstream_url": meta["upstream_url"],
                "version": meta["version"],
                "license": meta["license"],
                "declared_name": meta["declared_name"],
                "metadata_sources": meta["sources"],
                "upstream_tarball_compare": "NOT-CHECKED",
                "upstream_tarball_reason": (
                    "No pinned upstream tarball is recorded beside this tree; "
                    "this inventory will not invent a URL+revision. Probe 2 "
                    "proves unmarked-copy detection on a fixture tarball instead."
                ),
            }
        )
    return rows


def gitmodules_present(root: Path) -> bool:
    return (root / ".gitmodules").is_file()
