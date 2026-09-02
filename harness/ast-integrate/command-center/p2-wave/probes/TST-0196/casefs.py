#!/usr/bin/env python3
"""NTFS-like case-insensitive destination used by TST-0196.

Linux hosts are case-sensitive. Windows default volumes are not: two names
that differ only in case share one inode, FindFirstFile returns the *stored*
casing, and CreateFile/write on an existing fold does not retitle the file.
A case-only rename therefore needs an explicit rename (typically via a
temporary name), not a content copy keyed on a folded path.
"""
from __future__ import annotations

import hashlib
from typing import Any


def fold(rel: str) -> str:
    return rel.replace("\\", "/").casefold()


def posix(rel: str) -> str:
    return rel.replace("\\", "/")


class CaseInsensitiveFS:
    """One inode per case-folded relative path; stored casing is sticky on write."""

    def __init__(self) -> None:
        self._nodes: dict[str, dict[str, Any]] = {}

    def write(self, rel: str, data: bytes) -> str:
        rel = posix(rel)
        key = fold(rel)
        node = self._nodes.get(key)
        if node is None:
            self._nodes[key] = {"rel": rel, "data": data}
            return rel
        node["data"] = data
        return str(node["rel"])

    def rename(self, old: str, new: str) -> str:
        old, new = posix(old), posix(new)
        old_key, new_key = fold(old), fold(new)
        if old_key not in self._nodes:
            raise FileNotFoundError(old)
        if old_key == new_key:
            self._nodes[old_key]["rel"] = new
            return new
        if new_key in self._nodes:
            raise FileExistsError(new)
        node = self._nodes.pop(old_key)
        node["rel"] = new
        self._nodes[new_key] = node
        return new

    def delete(self, rel: str) -> None:
        key = fold(rel)
        if key in self._nodes:
            del self._nodes[key]

    def get(self, rel: str) -> bytes | None:
        node = self._nodes.get(fold(rel))
        return None if node is None else bytes(node["data"])

    def exact_name(self, rel: str) -> str | None:
        node = self._nodes.get(fold(rel))
        return None if node is None else str(node["rel"])

    def list_exact(self) -> list[str]:
        return sorted(str(n["rel"]) for n in self._nodes.values())

    def sha256(self, rel: str) -> str | None:
        data = self.get(rel)
        if data is None:
            return None
        return hashlib.sha256(data).hexdigest()

    def snapshot(self) -> dict[str, str]:
        return {rel: self.sha256(rel) or "" for rel in self.list_exact()}
