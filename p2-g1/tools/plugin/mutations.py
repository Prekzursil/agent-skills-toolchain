"""Mutation fingerprinting for dry-run vs journal equality (IMP-0032)."""
from __future__ import annotations

import hashlib
from typing import Any, Iterable


def _rec(item: Any) -> tuple:
    if isinstance(item, dict):
        return (
            str(item.get("op") or ""),
            str(item.get("path") or "").replace("\\", "/"),
            str(item.get("after_sha256") or item.get("sha256") or ""),
            int(item.get("after_bytes") or item.get("bytes") or 0),
        )
    if hasattr(item, "op"):
        return (
            str(getattr(item, "op", "")),
            str(getattr(item, "path", "")).replace("\\", "/"),
            str(getattr(item, "after_sha256", "") or getattr(item, "sha256", "")),
            int(getattr(item, "after_bytes", 0) or getattr(item, "bytes", 0) or 0),
        )
    return (str(item),)


def fingerprints(records: Iterable[Any]) -> tuple:
    return tuple(sorted(_rec(item) for item in (records or [])))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


__all__ = ["fingerprints", "sha256_bytes"]
