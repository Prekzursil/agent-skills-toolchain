#!/usr/bin/env python3
"""Canonical digest of a directory of markdown and scripts.

Cosign sign-blob signs one blob. A plugin marketplace whose packages are
directories therefore needs a stable serialization first. This module hashes
each file, emits a sorted manifest of `sha256  posix/relpath` lines, then
hashes that manifest. The outer digest is what a keyless sign-blob would
attest to.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def iter_files(root: Path) -> list[Path]:
    files = [p for p in root.rglob("*") if p.is_file()]
    files.sort(key=lambda p: p.relative_to(root).as_posix())
    return files


def manifest_bytes(root: Path) -> bytes:
    lines: list[str] = []
    for path in iter_files(root):
        rel = path.relative_to(root).as_posix()
        lines.append(f"{file_sha256(path)}  {rel}")
    return ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")


def tree_digest(root: Path) -> dict:
    root = root.resolve()
    entries = []
    for path in iter_files(root):
        rel = path.relative_to(root).as_posix()
        entries.append({"path": rel, "sha256": file_sha256(path), "bytes": path.stat().st_size})
    manifest = manifest_bytes(root)
    return {
        "root": str(root),
        "file_count": len(entries),
        "entries": entries,
        "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
        "manifest_bytes": len(manifest),
    }


def digest_of_named(root: Path, names: list[str]) -> str:
    """Digest a subset of files (the partial-tree failure mode)."""
    lines = []
    for name in sorted(names):
        path = root / name
        lines.append(f"{file_sha256(path)}  {name}")
    blob = ("\n".join(lines) + "\n").encode("utf-8")
    return hashlib.sha256(blob).hexdigest()
