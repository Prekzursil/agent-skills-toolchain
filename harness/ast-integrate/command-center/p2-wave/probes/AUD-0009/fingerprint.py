"""Content fingerprint of a tree versus an upstream tarball's member hashes.

Matching file-byte merkle (not tar header bytes) detects an undeclared copy
that has no vendor/ marker. A mutated file must mismatch.
"""
from __future__ import annotations

import hashlib
import io
import os
import tarfile
from pathlib import Path


SKIP_DIR_NAMES = frozenset(
    {".git", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_merkle(root: Path) -> dict:
    root = root.resolve()
    rows: list[tuple[str, str, int]] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(n for n in dirnames if n not in SKIP_DIR_NAMES)
        for fn in sorted(filenames):
            p = Path(dirpath) / fn
            if not p.is_file() or p.is_symlink():
                continue
            rel = p.relative_to(root).as_posix()
            digest = file_sha256(p)
            rows.append((rel, digest, p.stat().st_size))
    h = hashlib.sha256()
    for rel, digest, size in rows:
        h.update(f"{rel}\0{digest}\0{size}\n".encode("utf-8"))
    return {
        "merkle": h.hexdigest(),
        "file_count": len(rows),
        "files": [{"path": r, "sha256": d, "bytes": s} for r, d, s in rows],
    }


def tarball_member_merkle(tar_bytes: bytes) -> dict:
    rows: list[tuple[str, str, int]] = []
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:*") as tf:
        for member in sorted(tf.getmembers(), key=lambda m: m.name):
            if not member.isfile():
                continue
            extracted = tf.extractfile(member)
            if extracted is None:
                continue
            data = extracted.read()
            digest = hashlib.sha256(data).hexdigest()
            name = member.name.lstrip("./")
            rows.append((name, digest, len(data)))
    h = hashlib.sha256()
    for rel, digest, size in rows:
        h.update(f"{rel}\0{digest}\0{size}\n".encode("utf-8"))
    return {
        "merkle": h.hexdigest(),
        "file_count": len(rows),
        "files": [{"path": r, "sha256": d, "bytes": s} for r, d, s in rows],
        "tarball_sha256": hashlib.sha256(tar_bytes).hexdigest(),
        "tarball_bytes": len(tar_bytes),
    }


def make_deterministic_tarball(src_dir: Path) -> bytes:
    """ustar with sorted members, mtime=0, so header hash is stable for the fixture."""
    buf = io.BytesIO()
    src_dir = src_dir.resolve()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for dirpath, dirnames, filenames in os.walk(src_dir, followlinks=False):
            dirnames.sort()
            for fn in sorted(filenames):
                p = Path(dirpath) / fn
                if not p.is_file():
                    continue
                rel = p.relative_to(src_dir).as_posix()
                info = tarfile.TarInfo(name=rel)
                data = p.read_bytes()
                info.size = len(data)
                info.mtime = 0
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def compare_tree_to_tarball(tree: Path, tar_bytes: bytes) -> dict:
    tree_fp = tree_merkle(tree)
    tar_fp = tarball_member_merkle(tar_bytes)
    match = tree_fp["merkle"] == tar_fp["merkle"]
    return {
        "match": match,
        "tree_merkle": tree_fp["merkle"],
        "tarball_member_merkle": tar_fp["merkle"],
        "tarball_sha256": tar_fp["tarball_sha256"],
        "tree_file_count": tree_fp["file_count"],
        "tarball_file_count": tar_fp["file_count"],
    }
