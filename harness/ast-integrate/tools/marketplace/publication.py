"""Pack a certified workflow; exclude .git/caches/transcripts/credentials."""
from __future__ import annotations

import hashlib
import io
import json
import re
import tarfile
from dataclasses import dataclass, field
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
    """Publication attempted without an explicit, granted owner approval."""


@dataclass
class Gate:
    """Inventory-gate verdict computed from packed bytes.

    ``excluded_intersection`` lists archive members in the excluded class;
    ``credential_hits`` lists members whose bytes look credential-shaped.
    ``ok`` is True only when both lists are empty.
    """

    ok: bool
    excluded_intersection: list[str] = field(default_factory=list)
    credential_hits: list["CredHit"] = field(default_factory=list)


PUBLISH_ACTION = "marketplace-publish"


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
    """Fail closed when packed bytes carry excluded paths or credential-shaped data."""
    inv = inventory_from_packed(archive)
    intersection = paths_matching_excluded(inv)
    hits = scan_packed_credentials(archive)
    return Gate(
        ok=not intersection and not hits,
        excluded_intersection=intersection,
        credential_hits=hits,
    )


def plant_into_archive(archive: bytes, members: dict[str, bytes]) -> bytes:
    """Return a copy of ``archive`` with ``members`` appended as regular files.

    This bypasses :func:`pack_tree`'s allowlist on purpose: it is the adversarial
    fixture that lets the inventory gate be tested against packed bytes rather
    than against a pre-cleaned source tree. Existing members are preserved.
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r") as src, tarfile.open(
        fileobj=buf, mode="w"
    ) as dst:
        for m in src.getmembers():
            fh = src.extractfile(m) if m.isfile() else None
            dst.addfile(m, fh)
        for name in sorted(members):
            data = members[name]
            info = tarfile.TarInfo(name=name.replace("\\", "/"))
            info.size = len(data)
            info.mtime = 0
            info.mode = 0o644
            dst.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _approval_valid(approval: Any, unit: str | None) -> tuple[bool, str]:
    if not isinstance(approval, dict):
        return False, "no owner approval record"
    if approval.get("granted") is not True:
        return False, "owner approval not granted"
    if approval.get("action") != PUBLISH_ACTION:
        return False, f"approval action {approval.get('action')!r} != {PUBLISH_ACTION!r}"
    if not str(approval.get("owner") or "").strip():
        return False, "approval names no owner"
    if unit and approval.get("unit") not in (None, unit):
        return False, f"approval unit {approval.get('unit')!r} != {unit!r}"
    return True, ""


def publish(payload: dict[str, Any], approval: dict[str, Any] | None, *, unit: str | None = None) -> dict[str, Any]:
    """Transition an emitted payload to PUBLISHED under an explicit owner approval.

    Raises :class:`OwnerGateError` unless ``approval`` is a granted record for
    ``marketplace-publish`` naming an owner. The input payload is not mutated;
    the returned record carries the publication state and the approval used.
    """
    ok, why = _approval_valid(approval, unit)
    if not ok:
        raise OwnerGateError(f"publication refused: {why}")
    assert isinstance(approval, dict)
    record = json.loads(json.dumps(payload))
    pub = dict(record.get("publication") or {})
    pub.update(
        {
            "owner_gated": True,
            "published": True,
            "state": "PUBLISHED",
            "approval": {
                "action": approval["action"],
                "owner": approval["owner"],
                "unit": approval.get("unit"),
            },
        }
    )
    record["publication"] = pub
    record["state"] = "PUBLISHED"
    return record


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
