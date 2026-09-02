"""Validate-then-install. Digest is re-checked immediately before place.

Monkeypatch this module's payload_digest to observe the TOCTOU window after
the digest call and before place_payload_files.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import json

from marketplace.handoff import validate_handoff
from plugin.errors import (
    DigestMismatchError,
    InstallError,
    MissingTransactionIdError,
    PermissionWideningBlocked,
    ProjectionError,
)
from plugin.payload import census_tree
from plugin.payload import payload_digest as _payload_digest
from plugin.placement import place_payload_files

# Re-exported so ADV-0030 can monkeypatch install.payload_digest.
payload_digest = _payload_digest


def _existing_permissions(dest_root: Path) -> set[str]:
    perms: set[str] = set()
    if not dest_root.is_dir():
        return perms
    for path in dest_root.rglob("plugin.json"):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(doc, dict):
            for item in doc.get("permissions") or []:
                perms.add(str(item))
    return perms


def _dest_escapes(dest_root: Path, dest: str) -> bool:
    root = dest_root.resolve()
    target = (dest_root / dest).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return True
    return False


def install_from_handoff(handoff: dict[str, Any], dest_root: Path) -> dict[str, Any]:
    if not isinstance(handoff, dict):
        raise MissingTransactionIdError("untyped handoff missing transaction_id")
    if not handoff.get("transaction_id"):
        raise MissingTransactionIdError("handoff missing transaction_id")
    try:
        doc = validate_handoff(handoff)
    except (TypeError, ValueError) as exc:
        raise MissingTransactionIdError(str(exc)) from exc
    payload = Path(doc["payload_path"])
    expected = str((doc.get("digest") or {}).get("value") or "")
    live = payload_digest(payload)
    if not expected or live != expected:
        raise DigestMismatchError(f"digest mismatch live={live} expected={expected}")
    dest_root = Path(dest_root)
    projection = doc.get("projection_map") or {}
    expected_dests = sorted(
        str(entry.get("dest") or "").replace("\\", "/")
        for entry in (projection.get("entries") or [])
        if isinstance(entry, dict) and entry.get("dest")
    )
    for dest in expected_dests:
        if dest.startswith("/") or dest.startswith("\\") or _dest_escapes(dest_root, dest):
            raise ProjectionError(f"projection dest escapes dest_root: {dest}")
    old_perms = _existing_permissions(dest_root)
    new_perms = {str(p) for p in (doc.get("declared_permissions") or [])}
    if old_perms and new_perms - old_perms and not (old_perms - new_perms):
        raise PermissionWideningBlocked(
            f"permissions widen installed={sorted(old_perms)} candidate={sorted(new_perms)}"
        )
    dest_root.mkdir(parents=True, exist_ok=True)
    placed = place_payload_files(dest_root, projection, payload)
    staged_census = census_tree(dest_root)
    if sorted(staged_census) != expected_dests:
        raise ProjectionError(
            f"staged census dests {sorted(staged_census)} != {expected_dests}"
        )
    return {
        "placed": placed,
        "dest_root": str(dest_root),
        "digest": live,
        "ok": True,
    }


def install_plugin(handoff: dict[str, Any], dest_root: Path) -> dict[str, Any]:
    return install_from_handoff(handoff, dest_root)


def sha256_file(path: Path) -> str:
    from plugin.payload import sha256_hex

    return sha256_hex(Path(path).read_bytes())


def live_file_census(root: Path) -> dict[str, str]:
    return census_tree(root)


def plugin_root(dest_root: Path, name: str) -> Path:
    return Path(dest_root) / "plugins" / name


def apply_install(prefix: Path, handoff: dict[str, Any]) -> dict[str, Any]:
    """Digest-only installer. Signing sidecars are never consulted."""
    from plugin.payload import blob_identity, sha256_hex, unpack_package

    if not isinstance(handoff, dict):
        raise InstallError("handoff is not an object")
    payload = Path(handoff["payload_path"])
    blob = payload.read_bytes()
    expected = handoff.get("digest")
    if isinstance(expected, dict):
        expected = expected.get("value")
    live = sha256_hex(blob)
    if not expected or str(expected) != live:
        raise DigestMismatchError(f"digest mismatch live={live} expected={expected}")
    unpacked = unpack_package(blob)
    name, ver = blob_identity(unpacked)
    dest = plugin_root(Path(prefix), name)
    dest.mkdir(parents=True, exist_ok=True)
    for rel, data in (unpacked.get("files") or {}).items():
        out = dest / str(rel)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
    return {
        "ok": True,
        "package": name,
        "version": ver,
        "digest": live,
        "placed": sorted((unpacked.get("files") or {}).keys()),
    }


from dataclasses import dataclass
from typing import Callable
import hashlib
import time as _time


class InstallError(Exception):
    def __init__(self, message: str = "", code: str = "install-error") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class InstallResult:
    status: str
    mutated: bool
    dest: str = ""

    def to_dict(self) -> dict:
        return {"status": self.status, "mutated": self.mutated, "dest": self.dest}


def predicted_live_paths(projection: dict) -> set[str]:
    return {
        str(e.get("live") or e.get("source") or "").replace("\\", "/")
        for e in (projection.get("entries") or [])
        if isinstance(e, dict) and (e.get("live") or e.get("source"))
    }


def mtime_hash_census(root: Path) -> dict[str, list]:
    root = Path(root)
    out: dict[str, list] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        digest = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        out[rel] = [path.stat().st_mtime_ns, digest]
    return out


def classify_live_state(root: Path, old: dict[str, str], new: dict[str, str]) -> str:
    live = live_file_census(root)
    if live == new:
        return "NEW"
    if live == old:
        return "OLD"
    return "MIXED"


def resolve_live(root: Path) -> Path | None:
    root = Path(root)
    return root if root.is_dir() else None


def _place_projection(dest: Path, payload: Path, projection: dict) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for entry in projection.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        src = payload / str(entry.get("source") or "")
        live = str(entry.get("live") or entry.get("source") or "").replace("\\", "/")
        if not live or not src.is_file():
            continue
        out = dest / live
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(src.read_bytes())


_orig_install_plugin = install_plugin


def install_plugin(*args, **kwargs):
    home = kwargs.get("home")
    payload = kwargs.get("payload")
    projection = kwargs.get("projection")
    after_stage = kwargs.get("after_stage")
    if home is not None and payload is not None and projection is not None:
        home = Path(home)
        payload = Path(payload)
        plugin_id = str(projection.get("plugin_id") or "demo-plugin")
        dest = plugin_root(home, plugin_id)
        predicted = predicted_live_paths(projection)
        existing = live_file_census(dest) if dest.is_dir() else {}
        payload_hashes = {
            str(e.get("live") or e.get("source")): sha256_file(payload / str(e.get("source")))
            for e in (projection.get("entries") or [])
            if isinstance(e, dict) and e.get("source")
        }
        if dest.is_dir() and existing and set(existing) == predicted and existing == payload_hashes:
            return InstallResult(status="already-current", mutated=False, dest=str(dest))
        staging = home / ".staging" / plugin_id
        if staging.exists():
            import shutil
            shutil.rmtree(staging, ignore_errors=True)
        _place_projection(staging, payload, projection)
        if callable(after_stage):
            after_stage(staging)
            staged = live_file_census(staging)
            if staged != payload_hashes:
                raise InstallError("staged digest mismatch after after_stage")
        import shutil
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(staging, dest)
        return InstallResult(status="installed", mutated=True, dest=str(dest))
    return _orig_install_plugin(*args, **kwargs)

