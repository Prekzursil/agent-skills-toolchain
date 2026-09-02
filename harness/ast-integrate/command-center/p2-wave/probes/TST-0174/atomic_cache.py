#!/usr/bin/env python3
"""On-disk cache entry with atomic publish (tmp + os.replace).

B05/B07 production cache modules are absent on this worktree. This module is
the measured layer for TST-0174: readers of a published key must see either
the previous complete entry or a complete new one, never a torn write.
"""
from __future__ import annotations

import hashlib
import os
import struct
import tempfile
import time
from pathlib import Path

MAGIC = b"T174\x00"
HEADER_LEN = 5 + 4 + 32
TMP_PREFIX = ".tmp-TST0174-"
ABSENT = "ABSENT"
COMPLETE = "COMPLETE"
PARTIAL = "PARTIAL"
ERROR = "ERROR"


def encode(payload: bytes) -> bytes:
    return MAGIC + struct.pack(">I", len(payload)) + hashlib.sha256(payload).digest() + payload


def classify_bytes(data: bytes) -> tuple[str, str | None]:
    if not data:
        return PARTIAL, "empty"
    if not data.startswith(MAGIC):
        return PARTIAL, "bad-magic"
    if len(data) < HEADER_LEN:
        return PARTIAL, "truncated-header"
    (n,) = struct.unpack(">I", data[5:9])
    digest = data[9:41]
    payload = data[41:]
    if len(payload) < n:
        return PARTIAL, "truncated-payload"
    if len(payload) > n:
        return PARTIAL, "oversize"
    if hashlib.sha256(payload).digest() != digest:
        return PARTIAL, "checksum"
    return COMPLETE, hashlib.sha256(payload).hexdigest()


def classify_path(path: Path | str) -> tuple[str, str | None]:
    dest = Path(path)
    try:
        fd = os.open(dest, os.O_RDONLY)
    except FileNotFoundError:
        return ABSENT, None
    except OSError as exc:
        return ERROR, type(exc).__name__
    try:
        chunks: list[bytes] = []
        while True:
            buf = os.read(fd, 1 << 20)
            if not buf:
                break
            chunks.append(buf)
            if sum(len(c) for c in chunks) > 32 << 20:
                return PARTIAL, "oversize-read"
        data = b"".join(chunks)
    except OSError as exc:
        return ERROR, type(exc).__name__
    finally:
        os.close(fd)
    return classify_bytes(data)


def leftover_tmps(directory: Path | str) -> list[str]:
    root = Path(directory)
    if not root.is_dir():
        return []
    names = []
    for child in root.iterdir():
        if child.name.startswith(TMP_PREFIX):
            names.append(child.name)
    return sorted(names)


def atomic_publish(dest: Path | str, payload: bytes) -> None:
    dest_path = Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=TMP_PREFIX, suffix=".part", dir=str(dest_path.parent))
    tmp_path = Path(tmp)
    try:
        view = memoryview(payload)
        written = 0
        while written < len(payload):
            n = os.write(fd, view[written:])
            if n <= 0:
                raise OSError("short write")
            written += n
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.replace(tmp_path, dest_path)
        tmp_path = Path()
    finally:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        if tmp_path.name and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def inplace_publish(
    dest: Path | str,
    payload: bytes,
    *,
    pause_after: int = 2048,
    pause_s: float = 0.04,
) -> None:
    """Known-broken: in-place overwrite so a concurrent reader can see a torn file."""
    dest_path = Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    split = min(max(1, pause_after), max(1, len(payload) - 1))
    with open(dest_path, "wb") as handle:
        handle.write(payload[:split])
        handle.flush()
        os.fsync(handle.fileno())
        time.sleep(pause_s)
        handle.write(payload[split:])
        handle.flush()
        os.fsync(handle.fileno())


def write_worker(path: str, payload: bytes, mode: str) -> None:
    if mode == "atomic":
        atomic_publish(path, payload)
        return
    if mode == "inplace":
        inplace_publish(path, payload)
        return
    raise ValueError(f"unknown publish mode {mode!r}")
