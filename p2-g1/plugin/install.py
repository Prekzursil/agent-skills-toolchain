"""Validate-then-install. Digest is re-checked immediately before place.

Monkeypatch this module's payload_digest to observe the TOCTOU window after
the digest call and before place_payload_files.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from marketplace.handoff import validate_handoff
from plugin.errors import DigestMismatchError, InstallError
from plugin.payload import census_tree
from plugin.payload import payload_digest as _payload_digest
from plugin.placement import place_payload_files

# Re-exported so ADV-0030 can monkeypatch install.payload_digest.
payload_digest = _payload_digest


def install_from_handoff(handoff: dict[str, Any], dest_root: Path) -> dict[str, Any]:
    if not isinstance(handoff, dict):
        raise InstallError("handoff is not an object")
    doc = validate_handoff(handoff)
    payload = Path(doc["payload_path"])
    expected = str((doc.get("digest") or {}).get("value") or "")
    live = payload_digest(payload)
    if not expected or live != expected:
        raise DigestMismatchError(f"digest mismatch live={live} expected={expected}")
    dest_root = Path(dest_root)
    dest_root.mkdir(parents=True, exist_ok=True)
    projection = doc.get("projection_map") or {}
    expected_dests = sorted(
        str(entry.get("dest") or "").replace("\\", "/")
        for entry in (projection.get("entries") or [])
        if isinstance(entry, dict) and entry.get("dest")
    )
    placed = place_payload_files(dest_root, projection, payload)
    staged_census = census_tree(dest_root)
    if sorted(staged_census) != expected_dests:
        raise InstallError(
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
