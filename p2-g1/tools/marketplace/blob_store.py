"""Content-addressed blob store with persisted refcounts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


class CorruptedBlobError(Exception):
    def __init__(
        self,
        message: str,
        *,
        actual: str | None = None,
        digest: str | None = None,
    ):
        super().__init__(message)
        self.actual = actual
        self.digest = digest


class ReferencedBlobError(Exception):
    def __init__(self, message: str, *, refcount: int = 0):
        super().__init__(message)
        self.refcount = refcount


def digest_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def list_object_files(root: Path) -> list[Path]:
    obj = Path(root) / "objects"
    if not obj.is_dir():
        return []
    return sorted(p for p in obj.iterdir() if p.is_file())


def load_index_file(root: Path) -> dict:
    path = Path(root) / "index.json"
    if not path.is_file():
        return {"objects": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def refcount_from_index(index: dict, digest: str) -> int:
    rec = (index.get("objects") or {}).get(digest) or {}
    refs = rec.get("refs") or {}
    if isinstance(refs, dict):
        return sum(int(v) for v in refs.values())
    if isinstance(refs, list):
        return len(refs)
    return int(rec.get("refcount") or 0)


class BlobStore:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        (self.root / "objects").mkdir(parents=True, exist_ok=True)
        if not (self.root / "index.json").is_file():
            self._write_index({"objects": {}})

    def _index(self) -> dict:
        return load_index_file(self.root)

    def _write_index(self, index: dict) -> None:
        path = self.root / "index.json"
        path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _obj_path(self, digest: str) -> Path:
        return self.root / "objects" / digest

    def put(self, payload: bytes, ref: str | None = None) -> str:
        digest = digest_bytes(payload)
        if not ref:
            ref = digest
        path = self._obj_path(digest)
        if not path.is_file():
            path.write_bytes(payload)
        index = self._index()
        objects = index.setdefault("objects", {})
        rec = objects.setdefault(digest, {"refs": {}, "size": len(payload)})
        refs = rec.setdefault("refs", {})
        refs[ref] = int(refs.get(ref) or 0) + 1
        rec["size"] = len(payload)
        self._write_index(index)
        return digest

    def get(self, digest: str) -> bytes:
        path = self._obj_path(digest)
        data = path.read_bytes()
        actual = digest_bytes(data)
        if actual != digest:
            raise CorruptedBlobError(
                "blob digest mismatch", actual=actual, digest=digest
            )
        return data

    def refcount(self, digest: str) -> int:
        return refcount_from_index(self._index(), digest)

    def release(self, digest: str, ref: str) -> None:
        index = self._index()
        rec = (index.get("objects") or {}).get(digest)
        if not rec:
            return
        refs = rec.setdefault("refs", {})
        if ref in refs:
            refs[ref] = int(refs[ref]) - 1
            if refs[ref] <= 0:
                refs.pop(ref, None)
        self._write_index(index)

    def delete(self, digest: str) -> None:
        rc = self.refcount(digest)
        if rc > 0:
            raise ReferencedBlobError("blob still referenced", refcount=rc)
        path = self._obj_path(digest)
        if path.is_file():
            path.unlink()
        index = self._index()
        (index.get("objects") or {}).pop(digest, None)
        self._write_index(index)
