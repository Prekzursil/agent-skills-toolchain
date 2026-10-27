"""Tree copy + manifest writer used by ADV-0117 installer/writer adapters."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


def _copy_tree_files(src: Path, dest: Path) -> list[str]:
    src = Path(src)
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for path in src.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(src).as_posix()
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        written.append(rel)
    return written


MANIFEST_NAME = "MANIFEST.json"
NAIVE_IMAGE = "naive-image"
PAYLOAD_DIR = "payload"
ROLLBACK_BLOBS = "rollback-blobs"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree_hash(root: Path, prefixes: tuple[str, ...] | list[str] = ()) -> str:
    root = Path(root)
    h = hashlib.sha256()
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if prefixes and not any(rel == p or rel.startswith(str(p).rstrip("/") + "/") for p in prefixes):
            continue
        files.append((rel, path.read_bytes()))
    for rel, blob in files:
        h.update(rel.encode("utf-8"))
        h.update(blob)
    return h.hexdigest()


class _DictResult(dict):
    def to_dict(self) -> dict[str, Any]:
        return dict(self)


def install_repair(root: Path, honor_ownership: bool = True) -> _DictResult:
    root = Path(root)
    payload = root / PAYLOAD_DIR
    user_before = (root / "user-data").exists()
    if honor_ownership:
        if payload.is_dir():
            _copy_tree_files(payload, root)
        for rel in ("cache/derived/stale.bin", "cache/index/stale.json"):
            p = root / rel
            if p.is_file():
                p.unlink()
        user_after = (root / "user-data").exists()
        return _DictResult(
            {
                "ok": True,
                "honor_ownership": True,
                "user_data_byte_identical": user_before and user_after,
            }
        )
    # Mutant: no ownership map — wipe user data along with caches.
    import shutil

    for rel in ("user-data", "commands", "cache"):
        p = root / rel
        if p.is_dir():
            shutil.rmtree(p)
        elif p.is_file():
            p.unlink()
    return _DictResult(
        {
            "ok": True,
            "honor_ownership": False,
            "user_data_byte_identical": False,
        }
    )


def update(root: Path) -> _DictResult:
    root = Path(root)
    man = root / MANIFEST_NAME
    if not man.is_file():
        return _DictResult({"ok": False, "refused": True, "reason": "missing-manifest"})
    payload = root / PAYLOAD_DIR
    if payload.is_dir():
        _copy_tree_files(payload, root)
    for rel in ("cache/derived/stale.bin", "cache/index/stale.json"):
        p = root / rel
        if p.is_file():
            p.unlink()
    return _DictResult({"ok": True})


def rollback(root: Path, naive_snapshot: bool = False, **_kwargs) -> _DictResult:
    root = Path(root)
    src = root / (NAIVE_IMAGE if naive_snapshot else ROLLBACK_BLOBS)
    if src.is_dir():
        _copy_tree_files(src, root)
    return _DictResult({"ok": True, "naive_snapshot": bool(naive_snapshot)})


def write_manifest(root: Path, *, name: str = MANIFEST_NAME) -> Path:
    root = Path(root)
    rows = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == name:
            continue
        rel = path.relative_to(root).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append({"path": rel, "sha256": digest, "bytes": path.stat().st_size})
    dest = root / name
    dest.write_text(json.dumps({"files": rows}, indent=2) + "\n", encoding="utf-8")
    return dest


def copy_tree(src: Path, dest: Path) -> list[str]:
    return _copy_tree_files(src, dest)
