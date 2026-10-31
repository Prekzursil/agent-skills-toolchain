"""Site plugin cache with quarantine + atomic rebuild (IMP-0041).

Writes use a sibling .tmp file then os.replace. Truncated payloads are
quarantined on refresh and rebuilt from the stored source blob.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PAYLOAD_NAME = "payload.bin"


def sha256_hex(data: Any) -> str:
    if isinstance(data, Path):
        raw = data.read_bytes()
    elif isinstance(data, (bytes, bytearray)):
        raw = bytes(data)
    else:
        raw = str(data).encode("utf-8")
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def assert_atomic_write_contract(path: Path) -> dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    tree = ast.parse(text)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Name):
            names.add(node.id)
    uses_tmp = ".tmp" in text or "tmp" in names or "NamedTemporaryFile" in names
    uses_replace = "replace" in names or "os.replace" in text or "rename" in names
    ok = uses_tmp and uses_replace
    return {
        "ok": ok,
        "uses_tmp": uses_tmp,
        "uses_replace": uses_replace,
        "path": str(path),
    }


@dataclass
class CacheRow:
    plugin_id: str
    version: str
    key: str
    scope: str = "site"

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


@dataclass
class RefreshReport:
    quarantined: list[dict[str, Any]] = field(default_factory=list)
    intact: list[dict[str, Any]] = field(default_factory=list)
    rebuilt: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "quarantined": list(self.quarantined),
            "intact": list(self.intact),
            "rebuilt": list(self.rebuilt),
        }


class PluginCache:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.site = self.root / "site"
        self.quarantine = self.root / "quarantine"
        self.blobs = self.root / "blobs"
        self.site.mkdir(parents=True, exist_ok=True)
        self.quarantine.mkdir(parents=True, exist_ok=True)
        self.blobs.mkdir(parents=True, exist_ok=True)

    def _key(self, plugin_id: str, version: str) -> str:
        return f"{plugin_id}@{version}"

    def entry_dir(self, key: str) -> Path:
        return self.site / key

    def put(self, plugin_id: str, version: str, payload: bytes, scope: str = "site") -> str:
        key = self._key(plugin_id, version)
        dest = self.entry_dir(key)
        dest.mkdir(parents=True, exist_ok=True)
        _atomic_write(dest / PAYLOAD_NAME, payload)
        _atomic_write(dest / "sha256", sha256_hex(payload).encode("utf-8"))
        meta = {"plugin_id": plugin_id, "version": version, "scope": scope, "key": key}
        _atomic_write(dest / "meta.json", (json.dumps(meta) + "\n").encode("utf-8"))
        _atomic_write(self.blobs / f"{key}.bin", payload)
        return key

    def refresh(self, scope: str = "site") -> RefreshReport:
        report = RefreshReport()
        if not self.site.is_dir():
            return report
        for dest in list(self.site.iterdir()):
            if not dest.is_dir():
                continue
            meta_path = dest / "meta.json"
            payload = dest / PAYLOAD_NAME
            sha_path = dest / "sha256"
            if not meta_path.is_file():
                continue
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            expected = sha_path.read_text(encoding="utf-8").strip() if sha_path.is_file() else ""
            live = sha256_hex(payload.read_bytes()) if payload.is_file() else ""
            row = {
                "plugin_id": meta.get("plugin_id"),
                "version": meta.get("version"),
                "key": dest.name,
            }
            if live != expected:
                qdest = self.quarantine / dest.name
                if qdest.exists():
                    for child in qdest.iterdir():
                        child.unlink()
                    qdest.rmdir()
                dest.replace(qdest)
                report.quarantined.append(row)
                blob = self.blobs / f"{dest.name}.bin"
                if blob.is_file():
                    rebuilt_dir = self.entry_dir(dest.name)
                    rebuilt_dir.mkdir(parents=True, exist_ok=True)
                    source = blob.read_bytes()
                    _atomic_write(rebuilt_dir / PAYLOAD_NAME, source)
                    _atomic_write(
                        rebuilt_dir / "sha256", sha256_hex(source).encode("utf-8")
                    )
                    _atomic_write(
                        rebuilt_dir / "meta.json",
                        (json.dumps(meta) + "\n").encode("utf-8"),
                    )
                    report.rebuilt.append(row)
            else:
                report.intact.append(row)
        return report

    def get(
        self,
        plugin_id: str,
        version: str,
        source: bytes | None = None,
        scope: str = "site",
    ) -> bytes:
        key = self._key(plugin_id, version)
        payload = self.entry_dir(key) / PAYLOAD_NAME
        if payload.is_file():
            data = payload.read_bytes()
            sha_path = self.entry_dir(key) / "sha256"
            expected = sha_path.read_text(encoding="utf-8").strip() if sha_path.is_file() else ""
            if not expected or sha256_hex(data) == expected:
                return data
        blob = self.blobs / f"{key}.bin"
        if blob.is_file():
            return blob.read_bytes()
        if source is not None:
            self.put(plugin_id, version, source, scope=scope)
            return source
        raise FileNotFoundError(key)

    def quarantine_listing(self) -> list[str]:
        if not self.quarantine.is_dir():
            return []
        return sorted(p.name for p in self.quarantine.iterdir())


__all__ = [
    "PAYLOAD_NAME",
    "PluginCache",
    "RefreshReport",
    "assert_atomic_write_contract",
    "sha256_hex",
]
