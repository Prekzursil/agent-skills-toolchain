"""Registry-versus-deployed reconciliation for marketplace-first A3.

A: registry id with no non-empty installed PACKAGE.json (registry-not-deployed).
B: installed package directory with no registry id (deployed-not-in-registry).
H: both present, payload bytes do not match the canonical registry blob.

The three integers are NEVER folded into an 'agree' score. disagreement_count
is the sum of disagreeing items (A+B+H), a count of problems, not a pass.
Empty PACKAGE.json counts as missing (A), not present.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

PACKAGE_NAME = "PACKAGE.json"


def canonical_blob(entry: Mapping[str, Any]) -> bytes:
    payload = {
        "id": str(entry.get("id") or ""),
        "kind": str(entry.get("kind") or ""),
        "version": str(entry.get("version") or ""),
    }
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def load_registry(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"registry {path} is not an object")
    entries = doc.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"registry {path} has no entries")
    return doc


def installed_ids(install_root: Path) -> dict[str, dict[str, Any]]:
    """Map package id -> {path, size, sha256} for non-empty PACKAGE.json dirs."""
    out: dict[str, dict[str, Any]] = {}
    if not install_root.is_dir():
        return out
    for child in sorted(install_root.iterdir()):
        if not child.is_dir():
            continue
        pid = child.name
        if not pid or pid.startswith(".") or "/" in pid or ".." in pid:
            continue
        pkg = child / PACKAGE_NAME
        if not pkg.is_file():
            continue
        try:
            raw = pkg.read_bytes()
        except OSError:
            continue
        if len(raw) < 1:
            continue
        out[pid] = {
            "id": pid,
            "path": str(pkg),
            "rel_package": f"{install_root.as_posix().rstrip('/')}/{pid}/{PACKAGE_NAME}",
            "size": len(raw),
            "sha256": sha256_bytes(raw),
        }
    return out


def reconcile(
    registry: Mapping[str, Any],
    install_root: Path,
    *,
    registry_path: str = "",
) -> dict[str, Any]:
    entries = list(registry.get("entries") or [])
    by_id: dict[str, dict[str, Any]] = {}
    dup_ids: list[str] = []
    seen: list[str] = []
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        eid = str(entry.get("id") or "").strip()
        if not eid:
            continue
        if eid in by_id:
            dup_ids.append(eid)
        by_id[eid] = entry
        seen.append(eid)

    deployed = installed_ids(install_root)
    a_rows: list[dict[str, str]] = []
    for eid, entry in by_id.items():
        info = deployed.get(eid)
        pkg = install_root / eid / PACKAGE_NAME
        if info is None:
            reason = "empty" if pkg.is_file() and pkg.stat().st_size < 1 else "missing"
            a_rows.append(
                {
                    "id": eid,
                    "expected_path": f"{install_root.as_posix()}/{eid}/{PACKAGE_NAME}",
                    "reason": reason,
                }
            )

    b_rows: list[dict[str, str]] = []
    for eid, info in deployed.items():
        if eid not in by_id:
            b_rows.append(
                {
                    "id": eid,
                    "path": str(info.get("rel_package") or info.get("path") or eid),
                    "reason": "unregistered",
                }
            )

    h_rows: list[dict[str, str]] = []
    for eid, entry in by_id.items():
        info = deployed.get(eid)
        if info is None:
            continue
        want = sha256_bytes(canonical_blob(entry))
        got = str(info.get("sha256") or "")
        if got != want:
            h_rows.append(
                {
                    "id": eid,
                    "reason": "hash-mismatch",
                    "registry_blob_sha256": want,
                    "deployed_sha256": got,
                }
            )

    a_count = len(a_rows)
    b_count = len(b_rows)
    h_count = len(h_rows)
    return {
        "registry_path": registry_path,
        "install_root": install_root.as_posix(),
        "install_root_present": install_root.is_dir(),
        "registry_entry_count": len(entries),
        "registry_id_count": len(by_id),
        "deployed_package_count": len(deployed),
        "duplicate_ids": sorted(set(dup_ids)),
        "registry_not_deployed_count": a_count,
        "registry_not_deployed": a_rows,
        "deployed_not_in_registry_count": b_count,
        "deployed_not_in_registry": b_rows,
        "hash_mismatch_count": h_count,
        "hash_mismatches": h_rows,
        "disagreement_count": a_count + b_count + h_count,
        "direction_a_fail": a_count > 0 or bool(dup_ids),
        "direction_b_fail": b_count > 0,
        "hash_fail": h_count > 0,
        "both_sides_clean": a_count == 0
        and b_count == 0
        and h_count == 0
        and not dup_ids,
    }
