"""Durable JSON persist: write-temp, fsync, atomic replace. Reject torn leftovers."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

REGISTRY_NAME = "registry.json"


def dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def atomic_write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dumps(obj).encode("utf-8")
    tmp = path.with_name(path.name + ".tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(str(tmp), flags, 0o644)
    try:
        written = 0
        while written < len(payload):
            written += os.write(fd, payload[written:])
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, path)
    if os.name == "posix":
        # Directory fsync is POSIX-only; Windows cannot os.open() a directory
        # (PermissionError). os.replace() above is already atomic there, so
        # durability semantics are unchanged on both platforms.
        dirfd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)


def load_json(path: Path) -> Any:
    if path.suffix == ".tmp" or path.name.endswith(".tmp"):
        raise ValueError(f"refusing torn leftover {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def registry_path(work: Path) -> Path:
    return work / REGISTRY_NAME
