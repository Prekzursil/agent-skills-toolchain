#!/usr/bin/env python3
"""Diff produced artifact-tree layouts and cross-reference consumers.

Layout sources: directory names, filename patterns, and ARTIFACT-MANIFEST keys.
A path mentioned only in prose still counts as a consumer. A path with no
consumer is reported as no-consumer (never assumed safe).
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

PROSE_EXT = {".md", ".rst", ".txt"}
TOOL_EXT = {".py", ".js", ".ts", ".mjs"}
GATE_EXT = {".sh", ".bash"}
CONFIG_EXT = {".json", ".yml", ".yaml", ".toml"}
SKIP_PARTS = {"__pycache__", ".git", "node_modules"}
MANIFEST_NAMES = ("ARTIFACT-MANIFEST.json", "MANIFEST.json")


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _should_skip(path: Path) -> bool:
    return any(part in SKIP_PARTS or part.endswith(".pyc") for part in path.parts)


def extract_manifest_keys(doc: Any) -> dict[str, str]:
    """Pull key -> relative path from a layout manifest."""
    out: dict[str, str] = {}
    if not isinstance(doc, dict):
        return out
    artifacts = doc.get("artifacts", doc.get("files", doc.get("entries")))
    if isinstance(artifacts, dict):
        for key, value in artifacts.items():
            if isinstance(value, str) and value.strip():
                out[str(key)] = value.replace("\\", "/")
            elif isinstance(value, dict) and isinstance(value.get("path"), str):
                out[str(key)] = value["path"].replace("\\", "/")
    elif isinstance(artifacts, list):
        for i, item in enumerate(artifacts):
            if isinstance(item, str) and item.strip():
                out[f"idx-{i}"] = item.replace("\\", "/")
            elif isinstance(item, dict) and isinstance(item.get("path"), str):
                key = str(item.get("key") or item.get("id") or item.get("name") or f"idx-{i}")
                out[key] = item["path"].replace("\\", "/")
    return out


def list_tree(root: Path) -> dict[str, Any]:
    root = root.resolve()
    files: list[str] = []
    directories: set[str] = set()
    suffixes: Counter[str] = Counter()
    dir_patterns: Counter[str] = Counter()
    if not root.is_dir():
        return {
            "root": str(root),
            "files": [],
            "directories": [],
            "filename_patterns": {},
            "directory_patterns": {},
            "manifest_keys": {},
            "manifest_path": None,
        }
    for path in sorted(root.rglob("*")):
        if _should_skip(path):
            continue
        rel = _rel(path, root)
        if path.is_dir():
            directories.add(rel)
            continue
        if not path.is_file():
            continue
        files.append(rel)
        suffix = path.suffix.lower() or "<none>"
        suffixes[suffix] += 1
        parent = Path(rel).parent.as_posix()
        if parent == ".":
            parent = ""
        pattern = f"{parent}/*{suffix}" if parent else f"*{suffix}"
        dir_patterns[pattern] += 1
        for ancestor in Path(rel).parents:
            if str(ancestor) != ".":
                directories.add(ancestor.as_posix())

    manifest_path = None
    manifest_keys: dict[str, str] = {}
    for name in MANIFEST_NAMES:
        candidate = root / name
        if candidate.is_file():
            manifest_path = name
            try:
                doc = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                doc = None
            manifest_keys = extract_manifest_keys(doc)
            break

    return {
        "root": root.as_posix(),
        "files": files,
        "directories": sorted(directories),
        "filename_patterns": dict(sorted(suffixes.items())),
        "directory_patterns": dict(sorted(dir_patterns.items())),
        "manifest_keys": manifest_keys,
        "manifest_path": manifest_path,
    }


def _guess_moves(removed: Iterable[str], added: Iterable[str]) -> list[dict[str, str]]:
    """Pair removed/added paths that share a basename (directory or rename move)."""
    rem = list(removed)
    add = list(added)
    used_add: set[str] = set()
    moves: list[dict[str, str]] = []
    for old in rem:
        base = Path(old).name
        matches = [n for n in add if n not in used_add and Path(n).name == base]
        if len(matches) == 1:
            used_add.add(matches[0])
            kind = "directory-move" if Path(old).parent != Path(matches[0]).parent else "rename"
            moves.append({"from": old, "to": matches[0], "kind": kind})
    leftover_rem = [p for p in rem if p not in {m["from"] for m in moves}]
    leftover_add = [p for p in add if p not in used_add]
    # filename-pattern change: same parent directory, different suffix, unique pair
    for old in list(leftover_rem):
        parent = Path(old).parent.as_posix()
        stem = Path(old).stem
        matches = [
            n
            for n in leftover_add
            if Path(n).parent.as_posix() == parent and Path(n).stem == stem and n != old
        ]
        if len(matches) == 1:
            leftover_rem.remove(old)
            leftover_add.remove(matches[0])
            moves.append({"from": old, "to": matches[0], "kind": "filename-pattern"})
    return moves


def diff_layouts(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    bf = set(before.get("files") or [])
    af = set(after.get("files") or [])
    bd = set(before.get("directories") or [])
    ad = set(after.get("directories") or [])
    removed = sorted(bf - af)
    added = sorted(af - bf)
    moves = _guess_moves(removed, added)
    moved_from = {m["from"] for m in moves}
    moved_to = {m["to"] for m in moves}
    bk = before.get("manifest_keys") or {}
    ak = after.get("manifest_keys") or {}
    key_changes = []
    for key in sorted(set(bk) | set(ak)):
        ov, nv = bk.get(key), ak.get(key)
        if ov == nv:
            continue
        if ov is None:
            key_changes.append({"key": key, "change": "added", "before": None, "after": nv})
        elif nv is None:
            key_changes.append({"key": key, "change": "removed", "before": ov, "after": None})
        else:
            key_changes.append({"key": key, "change": "retargeted", "before": ov, "after": nv})
    changed = sorted(bf ^ af)
    for row in key_changes:
        for p in (row.get("before"), row.get("after")):
            if isinstance(p, str) and p and p not in changed and (p in bf or p in af):
                changed.append(p)
    changed = sorted(set(changed))
    return {
        "removed_paths": [p for p in removed if p not in moved_from],
        "added_paths": [p for p in added if p not in moved_to],
        "moved_paths": moves,
        "changed_paths": changed,
        "directory_names_added": sorted(ad - bd),
        "directory_names_removed": sorted(bd - ad),
        "filename_patterns_before": before.get("filename_patterns") or {},
        "filename_patterns_after": after.get("filename_patterns") or {},
        "directory_patterns_before": before.get("directory_patterns") or {},
        "directory_patterns_after": after.get("directory_patterns") or {},
        "manifest_key_changes": key_changes,
    }


def classify_consumer(path: Path, consumer_root: Path) -> str:
    rel = _rel(path, consumer_root)
    ext = path.suffix.lower()
    parts = Path(rel).parts
    if ext in PROSE_EXT or (parts and parts[0] in {"docs", "doc", "handbook"}):
        return "prose"
    if parts and parts[0] in {"tools", "tool"} or ext in TOOL_EXT:
        return "tool"
    if parts and parts[0] in {"workflows", "workflow"}:
        return "workflow"
    if parts and parts[0] in {"gates", "gate"} or ext in GATE_EXT:
        return "gate"
    if ext in CONFIG_EXT:
        return "config"
    return "other"


def find_consumers(rel_path: str, consumer_root: Path) -> list[dict[str, str]]:
    """Scan the consumer inventory for exact posix-path mentions."""
    needle = rel_path.replace("\\", "/")
    hits: list[dict[str, str]] = []
    if not consumer_root.is_dir() or not needle:
        return hits
    for path in sorted(consumer_root.rglob("*")):
        if not path.is_file() or _should_skip(path):
            continue
        if path.suffix.lower() in {".bin", ".pyc", ".png", ".jpg", ".woff"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if needle not in text:
            continue
        crel = _rel(path, consumer_root)
        hits.append(
            {
                "consumer": crel,
                "kind": classify_consumer(path, consumer_root),
                "path_referenced": needle,
            }
        )
    return hits


def _finding(consumers: list[dict[str, str]]) -> str:
    if not consumers:
        return "no-consumer"
    kinds = {c.get("kind") for c in consumers}
    if kinds and kinds <= {"prose"}:
        return "prose-only-consumer"
    return "named-consumer"


def cross_reference(changed_paths: list[str], consumer_root: Path) -> list[dict[str, Any]]:
    rows = []
    for rel in changed_paths:
        consumers = find_consumers(rel, consumer_root)
        rows.append(
            {
                "path": rel,
                "consumers": consumers,
                "consumer_finding": _finding(consumers),
                "assumed_safe": False,
                "explicit_no_consumer": _finding(consumers) == "no-consumer",
            }
        )
    return rows


def analyze(before_root: Path, after_root: Path, consumer_root: Path) -> dict[str, Any]:
    before = list_tree(before_root)
    after = list_tree(after_root)
    delta = diff_layouts(before, after)
    xref = cross_reference(delta["changed_paths"], consumer_root)
    incomplete = [
        r["path"]
        for r in xref
        if r["consumer_finding"] not in {"named-consumer", "prose-only-consumer", "no-consumer"}
    ]
    orphan_inventory = []
    all_paths = sorted(set(before["files"]) | set(after["files"]))
    for rel in all_paths:
        consumers = find_consumers(rel, consumer_root)
        if not consumers:
            orphan_inventory.append(
                {
                    "path": rel,
                    "in_before": rel in before["files"],
                    "in_after": rel in after["files"],
                    "consumer_finding": "no-consumer",
                    "assumed_safe": False,
                }
            )
    every_changed_classified = bool(xref) and not incomplete and len(xref) == len(delta["changed_paths"])
    return {
        "before": before,
        "after": after,
        "delta": delta,
        "consumer_cross_reference": xref,
        "unreferenced_inventory": orphan_inventory,
        "every_changed_path_classified": every_changed_classified,
        "incomplete_classifications": incomplete,
    }


def live_contract_vs_disk(repo: Path) -> dict[str, Any]:
    """Catalog-contracted output_path layout vs files actually on disk."""
    catalog_path = repo / "command-center" / "WORK-UNIT-CATALOG.json"
    manifest_rel = "command-center/ARTIFACT-MANIFEST.json"
    manifest_present = (repo / manifest_rel).is_file()
    if not catalog_path.is_file():
        return {
            "catalog_present": False,
            "manifest_present": manifest_present,
            "manifest_path": manifest_rel,
        }
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "catalog_present": True,
            "catalog_parse_error": type(exc).__name__,
            "manifest_present": manifest_present,
            "manifest_path": manifest_rel,
        }
    units = catalog.get("work_units") or []
    present = 0
    absent = 0
    absent_confirmation: list[str] = []
    present_samples: list[str] = []
    seen: set[str] = set()
    for unit in units:
        if not isinstance(unit, dict):
            continue
        rel = str(unit.get("output_path") or "").replace("\\", "/")
        if not rel or rel in seen:
            continue
        seen.add(rel)
        exists = (repo / rel).is_file() and (repo / rel).stat().st_size > 0
        if exists:
            present += 1
            if len(present_samples) < 12:
                present_samples.append(rel)
        else:
            absent += 1
            if rel.startswith("command-center/confirmation/") and len(absent_confirmation) < 20:
                absent_confirmation.append(rel)
    return {
        "catalog_present": True,
        "manifest_present": manifest_present,
        "manifest_path": manifest_rel,
        "unique_output_paths": len(seen),
        "present_on_disk": present,
        "absent_on_disk": absent,
        "present_samples": present_samples,
        "absent_confirmation_samples": absent_confirmation,
        "note": (
            "Live tree has one produced state. The catalog output_path set is the "
            "contracted layout; on-disk presence is the produced layout. "
            f"{manifest_rel} is the named CNF-0058 input and is "
            + ("present" if manifest_present else "ABSENT")
            + "."
        ),
    }
