"""Pack a certified workflow; exclude .git/caches/transcripts/credentials."""
from __future__ import annotations

import hashlib
import io
import json
import re
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

EXCLUDED_PREFIXES = (".git/", ".cache/", "transcripts/")
EXCLUDED_NAMES = {".git", ".cache"}
EXCLUDED_PARTS = {"__pycache__", "transcripts"}
CRED_RE = re.compile(rb"(AKIA[0-9A-Z]{16}|SECRET|PASSWORD|BEGIN OPENSSH|ghp_[A-Za-z0-9]+)")


@dataclass
class PackResult:
    archive: bytes
    omitted_excluded: list[str]
    sha256: str


@dataclass
class CredHit:
    path: str
    pattern_id: str


class OwnerGateError(RuntimeError):
    pass


@dataclass
class Gate:
    ok: bool


def _rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def _excluded(rel: str) -> bool:
    posix = rel.replace("\\", "/")
    name = posix.rsplit("/", 1)[-1]
    if posix in EXCLUDED_NAMES or posix.split("/")[0] in EXCLUDED_NAMES:
        return True
    if posix.startswith(EXCLUDED_PREFIXES):
        return True
    parts = posix.split("/")
    if any(p in EXCLUDED_PARTS for p in parts):
        return True
    if posix.endswith(".transcript") or "/transcripts/" in posix:
        return True
    if name in {".env", "secrets.json"} or name.endswith(".log"):
        return True
    if "SECRET" in posix.upper() and posix.endswith(".env"):
        return True
    return False


def pack_tree(root: Path) -> PackResult:
    root = Path(root)
    omitted: list[str] = []
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            rel = _rel(path, root)
            if _excluded(rel):
                omitted.append(rel)
                continue
            tf.add(path, arcname=rel)
    archive = buf.getvalue()
    return PackResult(archive=archive, omitted_excluded=omitted, sha256=hashlib.sha256(archive).hexdigest())


def inventory_from_packed(archive: bytes) -> list[str]:
    names = []
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r") as tf:
        for m in tf.getmembers():
            if m.isfile():
                names.append(m.name.replace("\\", "/"))
    return names


def paths_matching_excluded(inventory: Iterable[str]) -> list[str]:
    return [p for p in inventory if _excluded(p)]


def scan_packed_credentials(archive: bytes) -> list[CredHit]:
    hits: list[CredHit] = []
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r") as tf:
        for m in tf.getmembers():
            if not m.isfile():
                continue
            fh = tf.extractfile(m)
            if fh is None:
                continue
            data = fh.read()
            if CRED_RE.search(data):
                hits.append(CredHit(path=m.name, pattern_id="secret-shaped"))
    return hits


def inventory_gate(archive: bytes) -> Gate:
    inv = inventory_from_packed(archive)
    return Gate(ok=not paths_matching_excluded(inv) and not scan_packed_credentials(archive))


def emit_payload(root: Path) -> dict[str, Any]:
    packed = pack_tree(root)
    wf = {}
    wp = Path(root) / "workflow.json"
    if wp.is_file():
        wf = json.loads(wp.read_text(encoding="utf-8"))
    return {
        "identity": wf.get("id") or "wf.catalog-class.publication-demo",
        "version": wf.get("version") or "1.4.2",
        "permissions": wf.get("permissions") or {"tools": ["Read"]},
        "provenance": {"git_commit": "0" * 40},
        "sbom_entry": {"bomFormat": "CycloneDX"},
        "licence": (wf.get("licence") or {"spdx": "MIT"}),
        "benchmark_evidence": {"corpus_version": "corpus-2026.08"},
        "lineage": {"certified_by": "IMP-0203-fixture"},
        "publication": {
            "owner_gated": True,
            "published": False,
            "state": "awaiting-owner",
        },
        "packed": {"sha256": packed.sha256, "bytes": len(packed.archive)},
    }
