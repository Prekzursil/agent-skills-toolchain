"""File-by-file inventory of a disposable install tree."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

SKIP = {"__pycache__", ".git"}


def lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(lf(data)).hexdigest()


def iter_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    out: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP for part in path.parts):
            continue
        out.append(path)
    return out


def inventory(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in iter_files(root):
        data = lf(path.read_bytes())
        rel = path.relative_to(root).as_posix()
        rows.append({"path": rel, "sha256": sha256_bytes(data), "bytes": len(data)})
    return rows


def inventory_map(rows: list[dict[str, Any]]) -> dict[str, str]:
    return {r["path"]: r["sha256"] for r in rows}


def compare(pre: list[dict[str, Any]], post: list[dict[str, Any]]) -> dict[str, Any]:
    a = inventory_map(pre)
    b = inventory_map(post)
    only_pre = sorted(set(a) - set(b))
    only_post = sorted(set(b) - set(a))
    differ = sorted(p for p in set(a) & set(b) if a[p] != b[p])
    return {
        "identical": not only_pre and not only_post and not differ,
        "only_pre": only_pre,
        "only_post": only_post,
        "content_differ": differ,
        "pre_count": len(a),
        "post_count": len(b),
    }


def versions_present(root: Path) -> set[str]:
    found: set[str] = set()
    for path in iter_files(root):
        if path.name.endswith(".pending-reboot"):
            continue
        text = lf(path.read_bytes()).decode("utf-8", "replace")
        if "TST0061_VERSION=1.0.0" in text or '"version": "1.0.0"' in text:
            found.add("1.0.0")
        if "TST0061_VERSION=2.0.0" in text or '"version": "2.0.0"' in text:
            found.add("2.0.0")
    return found


def classify_tree(root: Path) -> str:
    if not root.is_dir() or not iter_files(root):
        return "absent"
    found = versions_present(root)
    if found == {"1.0.0", "2.0.0"}:
        return "mixed"
    if found == {"2.0.0"}:
        return "updated"
    if found == {"1.0.0"}:
        return "baseline"
    return "other"
