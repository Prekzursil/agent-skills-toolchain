"""Crash-safe durable store used by TST-0169 cold resume.

Stand-in for catalog input tools/lib/handled-ledger.mjs, which is absent on
this worktree. Writes never land under the process temp directory unless a
caller explicitly opts into the VOLATILE mutant used only as a detector
control.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class VolatileStoreError(RuntimeError):
    """Persist or load targeted a reboot-cleared location."""


def temp_root() -> Path:
    return Path(tempfile.gettempdir()).resolve()


def is_under_temp(path: Path) -> bool:
    resolved = path.resolve()
    tmp = temp_root()
    try:
        resolved.relative_to(tmp)
        return True
    except ValueError:
        return False


def assert_durable(path: Path, *, allow_volatile: bool = False) -> Path:
    resolved = path.resolve()
    if not allow_volatile and is_under_temp(resolved):
        raise VolatileStoreError(
            f"refusing store under reboot-cleared temp {temp_root()}: {resolved}"
        )
    return resolved


def atomic_write_bytes(path: Path, data: bytes, *, allow_volatile: bool = False) -> Path:
    target = assert_durable(path, allow_volatile=allow_volatile)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    with open(tmp, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, target)
    dir_fd = os.open(str(target.parent), os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)
    return target


def atomic_write_json(path: Path, doc: Any, *, allow_volatile: bool = False) -> Path:
    payload = (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")
    return atomic_write_bytes(path, payload, allow_volatile=allow_volatile)


def read_json(path: Path, *, allow_volatile: bool = False) -> Any:
    target = assert_durable(path, allow_volatile=allow_volatile)
    return json.loads(target.read_text(encoding="utf-8"))
