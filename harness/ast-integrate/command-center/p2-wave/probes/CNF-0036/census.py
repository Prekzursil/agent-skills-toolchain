"""File-level hash census for a disposable snapshot root."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def hash_bytes(raw: bytes) -> tuple[str, int]:
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def hash_manifest(root: Path) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts:
            continue
        digest, size = hash_bytes(path.read_bytes())
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": digest,
                "bytes": size,
            }
        )
    return rows


def tree_sha256(manifest: list[dict]) -> str:
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def record(root: Path, exit_code: int, message: str) -> dict:
    manifest = hash_manifest(root)
    return {
        "exit_code": int(exit_code),
        "message": str(message),
        "tree_sha256": tree_sha256(manifest),
        "hash_manifest": manifest,
    }
