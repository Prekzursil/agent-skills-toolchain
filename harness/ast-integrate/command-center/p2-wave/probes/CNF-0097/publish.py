#!/usr/bin/env python3
"""Build the published harness-plugin tarball from the A2 generator + payload."""
from __future__ import annotations

import hashlib
import io
import json
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
GEN_DIR = REPO / "command-center" / "p2-wave" / "probes" / "ARC-0010"
PAYLOAD = HERE / "payload"
DIST = HERE / "dist"
TARBALL_NAME = "harness-plugin-1.0.0.tar.gz"
PKG_ROOT = "harness-plugin-1.0.0"

sys.path.insert(0, str(GEN_DIR))
import generator as G  # noqa: E402


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def add_bytes(tar: tarfile.TarFile, name: str, data: bytes, mode: int = 0o644) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    info.mode = mode
    tar.addfile(info, io.BytesIO(data))


def payload_files() -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    mapping = {
        "install.py": PAYLOAD / "install.py",
        "health_check.py": PAYLOAD / "health_check.py",
        "prerequisites.json": PAYLOAD / "prerequisites.json",
        "plugin/hooks/pre-tool.py": PAYLOAD / "hooks" / "pre-tool.py",
    }
    for rel, path in mapping.items():
        files[rel] = path.read_bytes().replace(b"\r\n", b"\n")
    return files


def build(dest: Path | None = None) -> dict:
    registry = G.load_default_registry()
    generated = G.generate(registry)
    files = payload_files()
    for rel, data in generated.items():
        files[f"plugin/{rel}"] = data.replace(b"\r\n", b"\n")
    meta = {
        "file_count": len(files),
        "generator_id": G.GENERATOR_ID,
        "generator_version": G.GENERATOR_VERSION,
        "name": "harness",
        "version": "1.0.0",
        "files": sorted(files),
    }
    meta_bytes = (json.dumps(meta, indent=2, sort_keys=True) + "\n").encode("utf-8")
    files["META.json"] = meta_bytes
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz", format=tarfile.PAX_FORMAT, compresslevel=9) as tar:
        for rel in sorted(files):
            mode = 0o755 if rel.endswith(".py") else 0o644
            add_bytes(tar, f"{PKG_ROOT}/{rel}", files[rel], mode=mode)
    raw = buf.getvalue()
    dist = dest if dest is not None else DIST
    dist.mkdir(parents=True, exist_ok=True)
    out = dist / TARBALL_NAME
    out.write_bytes(raw)
    return {
        "path": out,
        "rel": out.relative_to(REPO).as_posix(),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "name": "harness",
        "version": "1.0.0",
        "file_count": len(files),
        "payload_sha256": digest_bytes(raw),
    }


if __name__ == "__main__":
    info = build()
    print(json.dumps({k: (str(v) if isinstance(v, Path) else v) for k, v in info.items()}, indent=2, sort_keys=True))
