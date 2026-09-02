"""Registry storage: content-addressed blob store plus atomic index writes.

Used by the IMP-0118 fixture-registry helpers and by IMP-0068 (index rebuilt
from blobs, kill-safe index replacement).  The index is only ever replaced via
write-to-temp + ``os.replace`` so a reader can observe the old or the new
document, never a partial one.  ``write_bytes_in_place`` exists as the
negative control (it can leave a partial file) and for the ``child`` CLI the
kill-point probes drive.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import IO, Any

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


def dumps_index(doc: dict[str, Any]) -> bytes:
    """Canonical index bytes: sorted keys, two-space indent, trailing newline."""
    if not isinstance(doc, dict) or not isinstance(doc.get("plugins"), list):
        raise ValueError("index document must be an object with a 'plugins' list")
    return (json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def loads_index(raw: bytes, *, source: str = "<bytes>") -> dict[str, Any]:
    """Parse index bytes; raise :class:`IndexCorrupt` on bad JSON or shape."""
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IndexCorrupt(source) from exc
    if not isinstance(doc, dict) or not isinstance(doc.get("plugins"), list):
        raise IndexCorrupt(source)
    return doc


def indexes_semantically_equal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    def canon(doc: dict[str, Any]) -> str:
        plugins = sorted(list(doc.get("plugins") or []), key=lambda p: str(p.get("name") or ""))
        return json.dumps({"plugins": plugins}, sort_keys=True)

    return canon(left) == canon(right)


def _write_chunks(
    fh: IO[bytes],
    payload: bytes,
    *,
    chunk: int,
    pause_at: int | None,
    pause_s: float,
) -> None:
    """Write ``payload`` in ``chunk``-sized fsynced pieces, pausing once at ``pause_at`` bytes."""
    step = chunk if chunk and chunk > 0 else max(len(payload), 1)
    paused = False
    for offset in range(0, len(payload), step):
        fh.write(payload[offset : offset + step])
        fh.flush()
        os.fsync(fh.fileno())
        written = min(offset + step, len(payload))
        if not paused and pause_at is not None and written >= pause_at:
            paused = True
            if pause_s > 0:
                time.sleep(pause_s)


def write_bytes_atomic(
    dest: Path,
    payload: bytes,
    *,
    chunk: int = 0,
    pause_at: int | None = None,
    pause_s: float = 0.0,
    tmp_report: Path | None = None,
) -> Path:
    """Write ``payload`` to a sibling temp file and ``os.replace`` it over ``dest``.

    A kill at any point leaves ``dest`` either untouched or fully replaced.
    """
    dest = Path(dest)
    tmp = dest.with_name(f"{dest.name}.{os.getpid()}.tmp")
    if tmp_report is not None:
        Path(tmp_report).write_text(str(tmp), encoding="utf-8")
    with open(tmp, "wb") as fh:
        _write_chunks(fh, payload, chunk=chunk, pause_at=pause_at, pause_s=pause_s)
    os.replace(tmp, dest)
    return dest


def write_bytes_in_place(
    dest: Path,
    payload: bytes,
    *,
    chunk: int = 0,
    pause_at: int | None = None,
    pause_s: float = 0.0,
    start_report: Path | None = None,
) -> Path:
    """Overwrite ``dest`` directly (NOT kill-safe; the negative control)."""
    dest = Path(dest)
    if start_report is not None:
        Path(start_report).write_text("start\n", encoding="utf-8")
    with open(dest, "r+b" if dest.exists() else "wb") as fh:
        fh.seek(0)
        _write_chunks(fh, payload, chunk=chunk, pause_at=pause_at, pause_s=pause_s)
        fh.truncate()
        fh.flush()
        os.fsync(fh.fileno())
    return dest


class RegistryStorage:
    """A registry root holding ``index.json`` and a content-addressed ``blobs/`` store."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.blob_dir = self.root / "blobs"
        self.blob_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / INDEX_NAME
        if not self.index_path.is_file():
            self._write_index({"plugins": []})

    def _write_index(self, doc: dict[str, Any]) -> None:
        write_bytes_atomic(self.index_path, dumps_index(doc))

    def read_index(self) -> dict[str, Any]:
        if not self.index_path.is_file():
            raise IndexMissing(str(self.index_path))
        return loads_index(self.index_path.read_bytes(), source=str(self.index_path))

    def _write_blob(self, plugin: dict[str, Any], blob: bytes) -> dict[str, Any]:
        name = str(plugin.get("name") or "")
        if not name:
            raise ValueError("plugin record needs a non-empty 'name'")
        digest = hashlib.sha256(blob).hexdigest()
        blob_path = self.blob_dir / f"{digest}.bin"
        meta_path = self.blob_dir / f"{digest}.json"
        write_bytes_atomic(blob_path, blob)
        write_bytes_atomic(
            meta_path, (json.dumps(plugin, sort_keys=True) + "\n").encode("utf-8")
        )
        return {
            "name": name,
            "digest": digest,
            "blob_path": str(blob_path),
            "meta_path": str(meta_path),
        }

    def put_package(self, plugin: dict[str, Any], blob: bytes) -> str:
        """Store the blob + metadata and upsert the plugin (by name) into the index."""
        stored = self._write_blob(plugin, blob)
        doc = self.read_index()
        plugins = [p for p in doc["plugins"] if p.get("name") != stored["name"]]
        rec = dict(plugin)
        rec["blob_sha256"] = stored["digest"]
        plugins.append(rec)
        doc["plugins"] = plugins
        self._write_index(doc)
        return stored["digest"]

    def plant_orphan_blob(self, plugin: dict[str, Any], blob: bytes) -> dict[str, Any]:
        """Store blob + metadata WITHOUT touching the index (an orphan for rebuild tests)."""
        return self._write_blob(plugin, blob)

    def list_blob_digests(self) -> list[str]:
        return sorted(p.stem for p in self.blob_dir.glob("*.bin"))

    def rebuild_from_blobs(self) -> dict[str, Any]:
        """Rebuild the index from every ``blobs/<digest>.json`` record, sorted by name."""
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


def _child_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="storage.py child")
    parser.add_argument("--mode", choices=("atomic", "in_place"), required=True)
    parser.add_argument("--dest", required=True)
    parser.add_argument("--payload-file", required=True)
    parser.add_argument("--pause-at", type=int, default=None)
    parser.add_argument("--pause-seconds", type=float, default=30.0)
    parser.add_argument("--chunk", type=int, default=0)
    parser.add_argument("--tmp-report", default=None)
    parser.add_argument("--start-report", default=None)
    args = parser.parse_args(argv)
    payload = Path(args.payload_file).read_bytes()
    dest = Path(args.dest)
    start_report = Path(args.start_report) if args.start_report else None
    if args.mode == "atomic":
        if start_report is not None:
            start_report.write_text("start\n", encoding="utf-8")
        write_bytes_atomic(
            dest,
            payload,
            chunk=args.chunk,
            pause_at=args.pause_at,
            pause_s=args.pause_seconds,
            tmp_report=Path(args.tmp_report) if args.tmp_report else None,
        )
    else:
        write_bytes_in_place(
            dest,
            payload,
            chunk=args.chunk,
            pause_at=args.pause_at,
            pause_s=args.pause_seconds,
            start_report=start_report,
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "child":
        return _child_main(argv[1:])
    print("usage: storage.py child --mode {atomic,in_place} --dest F --payload-file F [...]")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
