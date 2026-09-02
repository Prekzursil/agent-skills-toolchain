"""Deterministic demo payload shared by the installer / repair probes.

The payload is a tiny but complete plugin: a ``plugin.json`` manifest, one
hook definition, one markdown skill and an executable shim.  Every byte and
mode is fixed here so that two independent writers produce the same tar blob
and therefore the same ``sha256:`` digest -- the property the lockfile-pin,
projection and repair probes all rely on.

:func:`write_deterministic_tar` writes a gzip'd tar whose bytes depend only on
the member names, contents and modes (sorted names, zero mtimes, uid/gid 0,
no owner names, gzip header mtime 0 and no filename), and returns the digest
of the blob it wrote.  :func:`read_tar_members` and :func:`tree_digest` are the
matching read-side helpers.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import stat
import tarfile
from pathlib import Path
from typing import Any, Mapping

__all__ = [
    "HOOK_REL",
    "MANIFEST_REL",
    "PACKAGE_NAME",
    "PACKAGE_VERSION",
    "PAYLOAD_FILES",
    "PAYLOAD_MODES",
    "PROJECTION_MAP",
    "SHIM_REL",
    "SKILL_REL",
    "blob_digest",
    "coerce_bytes",
    "manifest_bytes",
    "member_digests",
    "payload_files_for",
    "read_tar_members",
    "tree_digest",
    "write_deterministic_tar",
    "write_payload_tree",
]

PACKAGE_NAME = "demo"
PACKAGE_VERSION = "1.0.0"

MANIFEST_REL = "plugin.json"
HOOK_REL = "hooks/pre.json"
SKILL_REL = "skills/hello/SKILL.md"
SHIM_REL = "bin/demo"


def manifest_bytes(
    name: str = PACKAGE_NAME, version: str = PACKAGE_VERSION, **extra: Any
) -> bytes:
    """Canonical ``plugin.json`` bytes for the demo payload (sorted keys, LF)."""
    doc: dict[str, Any] = {
        "name": name,
        "version": version,
        "description": "Deterministic demo plugin used by installer and repair probes.",
        "license": "MIT",
    }
    doc.update(extra)
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")


PAYLOAD_FILES: dict[str, bytes] = {
    MANIFEST_REL: manifest_bytes(),
    HOOK_REL: (
        json.dumps(
            {
                "event": "pre-tool",
                "command": "bin/demo --pre",
                "timeout_ms": 1000,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8"),
    SKILL_REL: (
        "---\n"
        "name: hello\n"
        "description: Say hello from the demo plugin.\n"
        "---\n"
        "\n"
        "# hello\n"
        "\n"
        "Reply with a one-line greeting, then stop.\n"
    ).encode("utf-8"),
    SHIM_REL: b"#!/bin/sh\n# demo shim: never executed by the installer\necho hello from demo\n",
}

PAYLOAD_MODES: dict[str, int] = {rel: 0o644 for rel in PAYLOAD_FILES}
PAYLOAD_MODES[SHIM_REL] = 0o755

PROJECTION_MAP: dict[str, str] = {rel: rel for rel in PAYLOAD_FILES}


def coerce_bytes(data: Any) -> bytes:
    """Accept ``bytes``/``bytearray``/``str`` member content."""
    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    if isinstance(data, str):
        return data.encode("utf-8")
    raise TypeError(
        f"payload member content must be bytes or str, got {type(data).__name__}"
    )


def payload_files_for(
    version: str = PACKAGE_VERSION, name: str = PACKAGE_NAME
) -> dict[str, bytes]:
    """The demo payload with ``plugin.json`` rewritten for ``name``/``version``."""
    files = dict(PAYLOAD_FILES)
    files[MANIFEST_REL] = manifest_bytes(name=name, version=version)
    return files


def blob_digest(blob: bytes) -> str:
    return "sha256:" + hashlib.sha256(blob).hexdigest()


def member_digests(files: Mapping[str, Any]) -> dict[str, str]:
    """Per-member ``sha256`` hex digests (sorted by member name)."""
    return {
        rel: hashlib.sha256(coerce_bytes(data)).hexdigest()
        for rel, data in sorted(files.items())
    }


def _check_rel(rel: str) -> str:
    parts = Path(rel).as_posix().split("/")
    if (
        not rel
        or rel.startswith("/")
        or any(p in ("", ".", "..") for p in parts)
        or ":" in parts[0]
    ):
        raise ValueError(f"unsafe payload member name {rel!r}")
    return "/".join(parts)


def write_deterministic_tar(
    dest: str | Path,
    files: Mapping[str, Any] | None = None,
    modes: Mapping[str, int] | None = None,
) -> str:
    """Write ``files`` as a reproducible ``.tar.gz`` at ``dest``; return ``sha256:<hex>``.

    Members are added in sorted order with ``mtime=0``, ``uid=gid=0`` and empty
    owner names; the gzip wrapper carries ``mtime=0`` and no filename, so the
    blob bytes are a pure function of names, contents and modes.
    """
    dest_path = Path(dest)
    members = files if files is not None else PAYLOAD_FILES
    member_modes = modes if modes is not None else PAYLOAD_MODES
    raw_tar = io.BytesIO()
    with tarfile.open(fileobj=raw_tar, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for rel in sorted(members):
            name = _check_rel(rel)
            data = coerce_bytes(members[rel])
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            info.mode = int(member_modes.get(rel, 0o644)) & 0o7777
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.type = tarfile.REGTYPE
            tar.addfile(info, io.BytesIO(data))
    gz_buf = io.BytesIO()
    with gzip.GzipFile(fileobj=gz_buf, mode="wb", mtime=0) as gz:
        gz.write(raw_tar.getvalue())
    blob = gz_buf.getvalue()
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(blob)
    return blob_digest(blob)


def read_tar_members(path: str | Path) -> list[dict[str, Any]]:
    """Describe the regular-file members of a tar written by this module."""
    rows: list[dict[str, Any]] = []
    with tarfile.open(str(path), mode="r:*") as tar:
        for info in tar.getmembers():
            if not info.isreg():
                continue
            handle = tar.extractfile(info)
            data = handle.read() if handle is not None else b""
            rows.append(
                {
                    "name": info.name,
                    "size": info.size,
                    "mode": info.mode & 0o7777,
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )
    return rows


def write_payload_tree(
    root: str | Path,
    files: Mapping[str, Any] | None = None,
    modes: Mapping[str, int] | None = None,
) -> list[str]:
    """Materialise ``files`` under ``root`` with their modes; return the sorted rel paths."""
    base = Path(root)
    members = files if files is not None else PAYLOAD_FILES
    member_modes = modes if modes is not None else PAYLOAD_MODES
    placed: list[str] = []
    for rel in sorted(members):
        name = _check_rel(rel)
        target = base / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(coerce_bytes(members[rel]))
        mode = int(member_modes.get(rel, 0o644)) & 0o7777
        if mode & stat.S_IXUSR:
            target.chmod(mode)
        placed.append(name)
    return placed


def tree_digest(root: str | Path) -> str:
    """``tree:<hex>`` over sorted ``(relpath, NUL, bytes)`` of every file under ``root``."""
    base = Path(root)
    digest = hashlib.sha256()
    for path in sorted(p for p in base.rglob("*") if p.is_file()):
        digest.update(path.relative_to(base).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return "tree:" + digest.hexdigest()
