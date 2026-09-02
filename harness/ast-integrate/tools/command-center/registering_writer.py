"""Emit-time artifact registration (completion condition 11) for IMP-0454.

A file that reaches disk through ``RegisteringWriter.emit`` is registered in
the writer-owned manifest *inside the same call*, before ``emit`` returns.
A later reconciliation sweep is deliberately read-only: it reports the set
difference between durable files and manifest paths and never writes a row.

That split is the unit's load-bearing claim. Trusting an in-memory
``emitted_paths`` list misses a direct ``open()`` bypass; walking disk and
the manifest JSON does not. Auto-registering inside the sweep would hide
the bypass and turn condition 11 into a later pass rather than a
construction property.

``tools/command-center/unit_manifest.py --write`` is a different, global
index. This module does not call it.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

CONTRACT = "emit-time-artifact-registration"
DERIVATION = "registering_writer.emit (not a later sweep)"
SCHEMA_VERSION = 1


class EmitError(ValueError):
    """Relative path rejected or emit rolled back; destination is unchanged."""


def digest_file(path: Path) -> tuple[str, int]:
    """SHA-256 and length after CRLF-to-LF normalisation (same as G-1)."""
    raw = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def digest_bytes(payload: bytes) -> tuple[str, int]:
    raw = payload.replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _as_bytes(body: str | bytes) -> bytes:
    if isinstance(body, bytes):
        return body
    if isinstance(body, str):
        return body.encode("utf-8")
    raise EmitError(f"body must be str or bytes, not {type(body).__name__}")


def normalize_rel(rel: str) -> str:
    """Reject empty, absolute, and ``..`` paths. Preserve POSIX relative form."""
    if not isinstance(rel, str) or not rel.strip():
        raise EmitError("relative path required")
    raw = rel.replace("\\", "/").strip()
    if raw.startswith("/") or (len(raw) >= 2 and raw[1] == ":"):
        raise EmitError(f"absolute path rejected: {rel!r}")
    parts = [p for p in raw.split("/") if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        raise EmitError(f"path escapes artifact root or is empty: {rel!r}")
    return "/".join(parts)


def _skip_name(name: str) -> bool:
    return (
        name.startswith(".")
        or name.endswith(".tmp")
        or name.endswith(".partial")
    )


def list_disk_artifacts(artifact_root: Path, manifest_path: Path) -> list[str]:
    """Durable files under ``artifact_root``, relative POSIX paths, sorted.

    Excludes the manifest itself, ``*.tmp`` / ``*.partial`` scratch, and
    dotfiles. Must stay aligned with the independent rglob walker in
    ``command-center/p2-wave/probes/IMP-0454/scenario.py``.
    """
    root = Path(artifact_root)
    man_res = Path(manifest_path).resolve() if Path(manifest_path).exists() else None
    found: set[str] = set()
    if not root.is_dir():
        return []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if man_res is not None and path.resolve() == man_res:
            continue
        if _skip_name(path.name):
            continue
        found.add(path.relative_to(root).as_posix())
    return sorted(found)


def _empty_manifest() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "contract": CONTRACT,
        "derivation": DERIVATION,
        "artifacts": [],
    }


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    path = Path(manifest_path)
    if not path.is_file():
        return _empty_manifest()
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise EmitError("manifest is not a JSON object")
    rows = doc.get("artifacts")
    if rows is None:
        doc["artifacts"] = []
    elif not isinstance(rows, list):
        raise EmitError("manifest artifacts is not a list")
    doc.setdefault("schema_version", SCHEMA_VERSION)
    doc.setdefault("contract", CONTRACT)
    doc.setdefault("derivation", DERIVATION)
    return doc


def registered_paths(manifest_path: Path) -> list[str]:
    doc = load_manifest(manifest_path)
    out: list[str] = []
    for row in doc.get("artifacts") or []:
        if isinstance(row, dict) and isinstance(row.get("path"), str):
            out.append(row["path"].replace("\\", "/"))
    return out


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with tmp.open("wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def _write_manifest(path: Path, doc: Mapping[str, Any]) -> None:
    text = json.dumps(dict(doc), indent=2, sort_keys=True) + "\n"
    _atomic_write_bytes(Path(path), text.encode("utf-8"))


def _upsert_row(doc: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    artifacts = [a for a in (doc.get("artifacts") or []) if isinstance(a, dict)]
    rel = row["path"]
    replaced = False
    new_rows: list[dict[str, Any]] = []
    for existing in artifacts:
        if existing.get("path") == rel:
            new_rows.append(row)
            replaced = True
        else:
            new_rows.append(existing)
    if not replaced:
        new_rows.append(row)
    out = dict(doc)
    out["artifacts"] = new_rows
    out["schema_version"] = SCHEMA_VERSION
    out["contract"] = CONTRACT
    out["derivation"] = DERIVATION
    return out


@dataclass(frozen=True)
class ReconcileResult:
    """Read-only disk-versus-manifest set difference."""

    disk: list[str]
    registered: list[str]
    unregistered: list[str]
    orphan_rows: list[str]
    unregistered_count: int
    set_difference_empty: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "disk": list(self.disk),
            "registered": list(self.registered),
            "unregistered": list(self.unregistered),
            "orphan_rows": list(self.orphan_rows),
            "unregistered_count": self.unregistered_count,
            "set_difference_empty": self.set_difference_empty,
        }


def reconcile(artifact_root: Path, manifest_path: Path) -> ReconcileResult:
    """Report unregistered files and orphan rows. Does not write the manifest."""
    disk = list_disk_artifacts(artifact_root, manifest_path)
    registered = sorted(set(registered_paths(manifest_path)))
    disk_set, reg_set = set(disk), set(registered)
    unregistered = sorted(disk_set - reg_set)
    orphans = sorted(reg_set - disk_set)
    return ReconcileResult(
        disk=disk,
        registered=registered,
        unregistered=unregistered,
        orphan_rows=orphans,
        unregistered_count=len(unregistered),
        set_difference_empty=not unregistered and not orphans,
    )


class RegisteringWriter:
    """Write a file and persist its manifest row in the same ``emit`` call."""

    def __init__(self, artifact_root: Path | str, manifest_path: Path | str) -> None:
        self.artifact_root = Path(artifact_root)
        self.manifest_path = Path(manifest_path)
        self._emitted: list[str] = []

    @property
    def emitted_paths(self) -> list[str]:
        """In-memory claim of paths this instance emitted. Misses bypasses."""
        return list(self._emitted)

    def emit(
        self,
        rel: str,
        body: str | bytes,
        *,
        unit_id: str,
        role: str = "artifact",
    ) -> dict[str, Any]:
        """Write ``rel`` under the artifact root and register it immediately.

        On any failure the destination and the on-disk manifest are restored
        to their pre-call bytes (a true no-op), including in-memory
        ``emitted_paths``.
        """
        rel_n = normalize_rel(rel)
        dest = self.artifact_root / rel_n
        try:
            dest.resolve().relative_to(self.artifact_root.resolve())
        except ValueError as exc:
            raise EmitError(f"path escapes artifact root: {rel!r}") from exc
        if self.manifest_path.exists() and dest.resolve() == self.manifest_path.resolve():
            raise EmitError("refusing to emit over the manifest file")

        data = _as_bytes(body)
        dest_existed = dest.is_file()
        old_dest = dest.read_bytes() if dest_existed else None
        man_existed = self.manifest_path.is_file()
        old_man = self.manifest_path.read_bytes() if man_existed else None
        partial = dest.with_name(dest.name + ".partial")
        remembered = False

        try:
            self.artifact_root.mkdir(parents=True, exist_ok=True)
            dest.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write_bytes(partial, data)
            sha, size = digest_file(partial)
            row = {
                "path": rel_n,
                "sha256": sha,
                "bytes": size,
                "present": True,
                "role": role,
                "unit_id": unit_id,
            }
            doc = _upsert_row(load_manifest(self.manifest_path), row)
            _write_manifest(self.manifest_path, doc)
            os.replace(partial, dest)
            live_sha, live_size = digest_file(dest)
            if live_sha != sha or live_size != size:
                raise EmitError("post-replace digest drifted from registered row")
            if rel_n not in self._emitted:
                self._emitted.append(rel_n)
                remembered = True
            return dict(row)
        except Exception:
            if remembered and self._emitted and self._emitted[-1] == rel_n:
                self._emitted.pop()
            if partial.exists():
                partial.unlink()
            if dest_existed and old_dest is not None:
                _atomic_write_bytes(dest, old_dest)
            elif dest.exists() and not dest_existed:
                dest.unlink()
            if man_existed and old_man is not None:
                _atomic_write_bytes(self.manifest_path, old_man)
            elif self.manifest_path.exists() and not man_existed:
                self.manifest_path.unlink()
            raise
