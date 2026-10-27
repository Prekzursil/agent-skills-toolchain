"""Index + lockfile reference scanner (independent of provenance walk)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from gc_store import load_index, load_lockfiles


def _hex(value: object) -> str:
    text = str(value or "").strip()
    if text.startswith("sha256:"):
        text = text[7:]
    return text.lower()


class IndexLockfileScan:
    def __init__(self, refs: dict[str, list[str]]) -> None:
        self._refs = refs

    def refs_for(self, digest_hex: str) -> list[str]:
        return list(self._refs.get(_hex(digest_hex), []))

    def all_hexes(self) -> set[str]:
        return set(self._refs)


def scan_index_and_lockfiles(root: Path) -> IndexLockfileScan:
    refs: dict[str, list[str]] = {}
    for item in load_index(root):
        digest = _hex(item.get("digest") or item.get("blob_digest"))
        if digest:
            refs.setdefault(digest, []).append("index.json:" + str(item.get("name") or ""))
    for item in load_lockfiles(root):
        digest = _hex(item.get("blob_digest") or item.get("digest"))
        if digest:
            src = str(item.get("_lockfile") or "lockfile")
            refs.setdefault(digest, []).append(src + ":" + str(item.get("name") or ""))
    return IndexLockfileScan(refs)
