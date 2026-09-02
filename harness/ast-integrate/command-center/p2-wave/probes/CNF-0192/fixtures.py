"""Deterministic CNF-0192 fixture trees (healthy, deleted, empty, unreadable)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

ENTRY_IDS = ("alpha", "beta", "gamma")
KIND = "cnf-0192-bucket-artifact"
READABLE_TOKEN = "READABLE"


def digest_bytes(raw: bytes) -> tuple[str, int]:
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def payload(eid: str, *, readable: bool = True) -> dict:
    body = {
        "id": eid,
        "kind": KIND,
        "payload": {"label": eid, "ok": True},
    }
    if readable:
        body["consumer_token"] = READABLE_TOKEN
    return body


def encode(doc: dict) -> bytes:
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_tree(
    root: Path,
    *,
    delete: str | None = None,
    empty: str | None = None,
    unreadable: str | None = None,
    tiny: str | None = None,
    extra_unmanifested: bool = False,
) -> Path:
    """Write a mini artifact-manifest tree. Paths are relative to ``root``."""
    bucket = root / "bucket"
    bucket.mkdir(parents=True, exist_ok=True)
    items: list[dict] = []
    for eid in ENTRY_IDS:
        rel = f"bucket/{eid}.json"
        path = root / rel
        if eid == unreadable:
            raw = encode(payload(eid, readable=False))
        else:
            raw = encode(payload(eid, readable=True))
        if eid == empty:
            raw = b""
        elif eid == tiny:
            raw = b"x"
        path.write_bytes(raw)
        if eid == delete:
            path.unlink()
            on_disk = b""
            sha, nbytes = digest_bytes(raw)
        else:
            on_disk = path.read_bytes()
            sha, nbytes = digest_bytes(on_disk)
        items.append(
            {
                "id": eid,
                "path": rel,
                "sha256": sha,
                "bytes": nbytes,
                "consumer": "json-required-keys",
                "claimed_present": True,
            }
        )
    if extra_unmanifested:
        (root / "bucket" / "orphan-unmanifested.json").write_text(
            json.dumps({"id": "orphan", "note": "not in manifest"}, indent=2) + "\n",
            encoding="utf-8",
        )
    manifest = {
        "schema_version": 1,
        "kind": "artifact-manifest",
        "artifact_root": ".",
        "bytes_hashed": "worktree",
        "artifacts": items,
    }
    mpath = root / "ARTIFACT-MANIFEST.json"
    mpath.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return mpath


def write_healthy(root: Path) -> Path:
    return write_tree(root)


def ids() -> Iterable[str]:
    return ENTRY_IDS
