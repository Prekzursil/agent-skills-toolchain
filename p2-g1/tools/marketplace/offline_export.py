"""Offline bundle: zip of blobs + manifest. Incomplete closure is refused."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any, Iterable

from marketplace.digest import sha256_hex


class IncompleteClosure(RuntimeError):
    pass


def export_offline_bundle(
    *,
    index: dict[str, Any],
    blobs: dict[str, bytes],
    private_keys: dict[str, bytes] | None = None,
    package_key_id: str | None = None,
    selection: Iterable[tuple[str, str]] | None = None,
    dest: str | Path,
    created_at: str = "",
    signed_at: str = "",
) -> dict[str, Any]:
    dest = Path(dest)
    wanted: list[tuple[str, str]] = list(selection or [])
    if not wanted:
        for name, versions in (index.get("packages") or {}).items():
            for ver in versions:
                wanted.append((name, ver))
    closed: list[tuple[str, str]] = []
    pending = list(wanted)
    seen: set[tuple[str, str]] = set()
    while pending:
        name, ver = pending.pop(0)
        if (name, ver) in seen:
            continue
        seen.add((name, ver))
        rec = ((index.get("packages") or {}).get(name) or {}).get(ver)
        if rec is None:
            raise IncompleteClosure(f"missing {name}@{ver}")
        closed.append((name, ver))
        for dep in rec.get("deps") or []:
            dname, dver = dep.split("@", 1)
            pending.append((dname, dver))
    entries = []
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, ver in closed:
            rec = ((index.get("packages") or {}).get(name) or {}).get(ver)
            blob_key = rec.get("blob") or f"{name}/{ver}"
            data = blobs.get(blob_key)
            if data is None:
                raise IncompleteClosure(f"missing blob {blob_key}")
            member = f"blobs/{blob_key}"
            zf.writestr(member, data)
            entries.append(
                {
                    "package": name,
                    "version": ver,
                    "blob_path": member,
                    "digest": sha256_hex(data),
                }
            )
        manifest = {
            "created_at": created_at,
            "signed_at": signed_at,
            "package_key_id": package_key_id,
            "entries": entries,
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
    return manifest


def zip_blob_members(path: str | Path) -> list[str]:
    with zipfile.ZipFile(path) as zf:
        return sorted(n for n in zf.namelist() if n.startswith("blobs/") and not n.endswith("/"))


def extract_offline_bundle(src: str | Path, dest: str | Path) -> Path:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(src) as zf:
        zf.extractall(dest)
    return dest


def extracted_blob_paths(root: str | Path) -> list[str]:
    root = Path(root)
    blobs = root / "blobs"
    if not blobs.is_dir():
        return []
    rels = []
    for p in sorted(blobs.rglob("*")):
        if p.is_file():
            rels.append(p.relative_to(root).as_posix())
    return rels
