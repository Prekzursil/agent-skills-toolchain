"""On-disk fixture registry helpers for IMP-0118."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

REGISTRY_REL = "tools/marketplace/fixture/registry"
INDEX_NAME = "index.json"


def registry_dir(repo: Path) -> Path:
    return Path(repo) / REGISTRY_REL


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def normalised(data):
    if isinstance(data, dict):
        return json.dumps(data, sort_keys=True, separators=(",", ":"))
    if isinstance(data, str):
        data = data.encode("utf-8")
    return data.replace(b"\r\n", b"\n")


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(normalised(data)).hexdigest()


def rebuild_index(root: Path) -> dict[str, Any]:
    index_path = Path(root) / "index.json"
    return read_json(index_path)


class IndexCorrupt(ValueError):
    pass


class IndexMissing(FileNotFoundError):
    pass


def indexes_semantically_equal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    def canon(doc: dict[str, Any]) -> str:
        plugins = sorted(list(doc.get("plugins") or []), key=lambda p: str(p.get("name") or ""))
        return json.dumps({"plugins": plugins}, sort_keys=True)

    return canon(left) == canon(right)


class RegistryStorage:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.blob_dir = self.root / "blobs"
        self.blob_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.json"
        if not self.index_path.is_file():
            self._write_index({"plugins": []})

    def _write_index(self, doc: dict[str, Any]) -> None:
        tmp = self.index_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.index_path)

    def read_index(self) -> dict[str, Any]:
        if not self.index_path.is_file():
            raise IndexMissing(str(self.index_path))
        raw = self.index_path.read_bytes()
        try:
            doc = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise IndexCorrupt(str(self.index_path)) from exc
        if not isinstance(doc, dict) or not isinstance(doc.get("plugins"), list):
            raise IndexCorrupt(str(self.index_path))
        return doc

    def put_package(self, plugin: dict[str, Any], blob: bytes) -> str:
        name = str(plugin.get("name") or "")
        digest = hashlib.sha256(blob).hexdigest()
        blob_path = self.blob_dir / f"{digest}.bin"
        meta_path = self.blob_dir / f"{digest}.json"
        tmp = blob_path.with_suffix(".bin.tmp")
        tmp.write_bytes(blob)
        tmp.replace(blob_path)
        meta_path.write_text(json.dumps(plugin, sort_keys=True) + "\n", encoding="utf-8")
        doc = self.read_index()
        plugins = [p for p in doc["plugins"] if p.get("name") != name]
        rec = dict(plugin)
        rec["blob_sha256"] = digest
        plugins.append(rec)
        doc["plugins"] = plugins
        self._write_index(doc)
        return digest

    def rebuild_from_blobs(self) -> dict[str, Any]:
        plugins: list[dict[str, Any]] = []
        for meta in sorted(self.blob_dir.glob("*.json")):
            rec = json.loads(meta.read_text(encoding="utf-8"))
            rec["blob_sha256"] = meta.stem
            plugins.append(rec)
        plugins.sort(key=lambda p: str(p.get("name") or ""))
        doc = {"plugins": plugins}
        self._write_index(doc)
        return doc

    def recover_index(self) -> dict[str, Any]:
        return self.rebuild_from_blobs()
