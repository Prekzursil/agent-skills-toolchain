"""Hashing walker that follows ROLLBACK-MANIFEST trees exactly.

Reserved Windows device names (NUL/CON/AUX/PRN/COM1/LPT1) must be opened
with the extended-length prefix. A naive open raises the historical
ValueError and a swallowed crash reports zero files.
"""
from __future__ import annotations

import hashlib
import os
import re
import stat
from pathlib import Path
from typing import Iterable

RESERVED_STEMS = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
)
TREE_LINE = re.compile(r"^-\s+`([^`]+)`\s*$")


def is_reserved_device_name(name: str) -> bool:
    stem = name.split(".")[0].upper()
    return stem in RESERVED_STEMS


def parse_affected_trees(manifest_text: str) -> list[str]:
    trees: list[str] = []
    in_section = False
    for raw in manifest_text.splitlines():
        line = raw.rstrip()
        if line.strip() == "## Affected trees":
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if not in_section:
            continue
        m = TREE_LINE.match(line.strip())
        if m:
            rel = m.group(1).replace("\\", "/").strip().strip("/")
            if rel and ".." not in rel.split("/"):
                trees.append(rel)
    if not trees:
        raise ValueError("ROLLBACK-MANIFEST has no affected trees")
    return trees


def extended_length_path(path: Path) -> str:
    """Windows extended-length prefix; POSIX returns the resolved native path."""
    resolved = str(path.resolve())
    if os.name == "nt":
        if resolved.startswith("\\\\?\\"):
            return resolved
        if resolved.startswith("\\\\"):
            return "\\\\?\\UNC\\" + resolved[2:]
        return "\\\\?\\" + resolved
    return resolved


def read_bytes(path: Path, *, extended: bool) -> bytes:
    if is_reserved_device_name(path.name) and not extended:
        raise ValueError(f"path is on mount '\\\\.\\{path.name}'")
    target = extended_length_path(path) if extended else str(path)
    with open(target, "rb") as fh:
        return fh.read()


def _iter_files(tree: Path) -> Iterable[Path]:
    if not tree.is_dir():
        return
    stack = [tree]
    seen: set[int] = set()
    while stack:
        current = stack.pop()
        try:
            st = current.lstat()
        except OSError as exc:
            raise RuntimeError(f"incomplete walk: cannot stat {current}: {exc}") from exc
        if stat.S_ISLNK(st.st_mode):
            continue
        ident = (st.st_dev, st.st_ino)
        if ident in seen:
            continue
        seen.add(ident)
        if stat.S_ISDIR(st.st_mode):
            try:
                names = sorted(os.listdir(current))
            except OSError as exc:
                raise RuntimeError(f"incomplete walk: cannot list {current}: {exc}") from exc
            for name in reversed(names):
                if name in {".git", "__pycache__"}:
                    continue
                stack.append(current / name)
            continue
        if stat.S_ISREG(st.st_mode):
            yield current


def hash_trees(
    root: Path,
    trees: list[str],
    *,
    extended: bool,
) -> dict[str, dict]:
    """Return {posix-relpath: {sha256, bytes, extended_length_path}}."""
    out: dict[str, dict] = {}
    root = root.resolve()
    for rel in trees:
        tree = (root / rel).resolve()
        if not str(tree).startswith(str(root)):
            raise RuntimeError(f"tree escapes root: {rel}")
        for path in _iter_files(tree):
            rel_path = path.relative_to(root).as_posix()
            data = read_bytes(path, extended=extended)
            digest = hashlib.sha256(data).hexdigest()
            out[rel_path] = {
                "path": rel_path,
                "sha256": digest,
                "bytes": len(data),
                "extended_length_path": extended_length_path(path),
                "reserved": is_reserved_device_name(path.name),
            }
    return out


def naive_hash_swallowed(root: Path, trees: list[str]) -> tuple[dict[str, dict], str | None]:
    """Naive walker: reserved names crash; swallow -> empty set (the defect)."""
    try:
        return hash_trees(root, trees, extended=False), None
    except ValueError as exc:
        return {}, f"{type(exc).__name__}: {exc}"


def manifest_rows(hashed: dict[str, dict]) -> list[dict]:
    rows = []
    for path in sorted(hashed):
        rec = hashed[path]
        rows.append(
            {
                "path": rec["path"],
                "sha256": rec["sha256"],
                "bytes": rec["bytes"],
            }
        )
    return rows


def fingerprint(hashed: dict[str, dict]) -> dict[str, str]:
    return {p: hashed[p]["sha256"] for p in hashed}


def symmetric_difference(pre: dict[str, str], post: dict[str, str]) -> dict:
    keys_pre = set(pre)
    keys_post = set(post)
    only_in_pre = sorted(keys_pre - keys_post)
    only_in_post = sorted(keys_post - keys_pre)
    content_changed = sorted(k for k in keys_pre & keys_post if pre[k] != post[k])
    return {
        "only_in_pre": only_in_pre,
        "only_in_post": only_in_post,
        "content_changed": content_changed,
        "empty": not (only_in_pre or only_in_post or content_changed),
    }


def residue_rows(diff: dict) -> list[dict]:
    rows = [{"path": p, "direction": "only_in_pre"} for p in diff["only_in_pre"]]
    rows.extend(
        {"path": p, "direction": "only_in_post_rollback"} for p in diff["only_in_post"]
    )
    rows.extend(
        {"path": p, "direction": "content_changed"} for p in diff["content_changed"]
    )
    return rows
