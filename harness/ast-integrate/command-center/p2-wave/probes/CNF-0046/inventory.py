"""Hash walker for a rollback prefix. LF-normalised sha256, same as G-1 measure."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from scenario import FILES, lf_sha, known_hashes


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def version_label(rel: str, sha: str) -> str:
    known = known_hashes()
    if known["v1"].get(rel) == sha:
        return "v1"
    if known["v2"].get(rel) == sha:
        return "v2"
    if sha == lf_sha(b""):
        return "empty"
    return "neither-v1-nor-v2"


def walk(root: Path) -> dict[str, Any]:
    files = []
    for rel in FILES:
        path = root / rel
        if not path.is_file():
            files.append(
                {
                    "path": rel,
                    "present": False,
                    "sha256": "",
                    "bytes": 0,
                    "version": "missing",
                }
            )
            continue
        sha, size = digest_file(path)
        files.append(
            {
                "path": rel,
                "present": True,
                "sha256": sha,
                "bytes": size,
                "version": version_label(rel, sha),
            }
        )
    return {"root": root.as_posix(), "files": files}


def versions(inv: dict[str, Any]) -> dict[str, str]:
    return {row["path"]: row["version"] for row in inv.get("files") or []}


def mixed_version(inv: dict[str, Any]) -> bool:
    labels = set(versions(inv).values())
    return "v1" in labels and "v2" in labels


def corrupted(inv: dict[str, Any]) -> bool:
    return any(
        row.get("version") in {"neither-v1-nor-v2", "empty", "missing"}
        for row in inv.get("files") or []
    )


def all_version(inv: dict[str, Any], label: str) -> bool:
    rows = inv.get("files") or []
    return bool(rows) and all(row.get("version") == label for row in rows)
