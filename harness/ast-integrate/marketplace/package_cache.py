"""Content-addressed package cache used by ADV-0024 marketplace-publish."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class ContentAddressedPackageCache:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "blobs").mkdir(parents=True, exist_ok=True)

    def _registry_path(self) -> Path:
        return self.root / "registry.json"

    def _load(self) -> dict[str, Any]:
        path = self._registry_path()
        if not path.is_file():
            return {"packages": {}}
        return json.loads(path.read_text(encoding="utf-8"))

    def _save(self, doc: dict[str, Any]) -> None:
        self._registry_path().write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def blob_path(self, digest: str) -> Path:
        return self.root / "blobs" / str(digest)

    def publish(self, name: str, payload: bytes, version: str) -> dict[str, Any]:
        digest = _digest(payload)
        dest = self.blob_path(digest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload)
        src = self.root / "source" / name / digest
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(payload)
        entry = {
            "name": name,
            "version": version,
            "digest": digest,
            "bytes": len(payload),
        }
        doc = self._load()
        packages = doc.setdefault("packages", {})
        packages[f"{name}@{version}"] = entry
        self._save(doc)
        return entry
