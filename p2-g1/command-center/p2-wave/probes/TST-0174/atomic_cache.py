#!/usr/bin/env python3
"""TST-0174 measured layer: named-key cache entry publish + reader-side integrity classifier.

Production note (recorded in the receipt): platform/plugin/cache.py Cache.put is
content-addressed (key = sha256(data)), so two distinct payloads cannot share a
key and the A-vs-B same-key race cannot exist there. The catalog question --
two writers, one key, readers never see a partial entry -- is measured on this
module: the named-key publisher using the SAME atomic primitive the production
code uses (tempfile.mkstemp + os.fsync + os.replace, the pattern of
platform/plugin/fsops.py atomic_write_bytes).
"""
from __future__ import annotations

import hashlib
import json
import os
import struct
import tempfile
import time
from pathlib import Path

MAGIC = b"T174\x00"
KEY = "same-key"
HEADER = 4 + 4 + 32  # magic + uint32be length + sha256 trailer


def encode(payload: bytes) -> bytes:
    return MAGIC + struct.pack(">I", len(payload)) + hashlib.sha256(payload).digest() + payload


def classify(raw: bytes | None) -> str:
    """Reader-side integrity classification of one observation."""
    if raw is None:
        return "ABSENT"
    if len(raw) < HEADER:
        return "PARTIAL"
    if raw[:5] != MAGIC:
        return "PARTIAL"
    (ln,) = struct.unpack(">I", raw[5:9])
    body = raw[9:]
    if len(body) < ln + 32:
        return "PARTIAL"
    trailer, payload = body[:32], body[32 : 32 + ln]  # encode layout: sha-then-payload
    if hashlib.sha256(payload).digest() != trailer:
        return "PARTIAL"
    if payload.startswith(b"A" * 8):
        return "COMPLETE-A"
    if payload.startswith(b"B" * 8):
        return "COMPLETE-B"
    return "COMPLETE-OTHER"


def read_observation(path: Path) -> bytes | None:
    """One reader observation that NEVER blocks a concurrent os.replace.

    Windows: open via CreateFileW with FILE_SHARE_READ|WRITE|DELETE so the
    writers' rename can proceed while the entry is open; without delete-sharing
    every open handle stalls MoveFileEx and the trial storm-degrades.
    """
    if os.name != "nt":
        try:
            return path.read_bytes()
        except FileNotFoundError:
            return None
    import ctypes
    import msvcrt

    GENERIC_READ = 0x80000000
    SHARE_ALL = 0x1 | 0x2 | 0x4  # READ | WRITE | DELETE
    OPEN_EXISTING = 3
    FILE_ATTRIBUTE_NORMAL = 0x80
    INVALID = ctypes.c_void_p(-1).value
    h = ctypes.windll.kernel32.CreateFileW(
        str(path), GENERIC_READ, SHARE_ALL, None, OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL, None,
    )
    if h is None or h == INVALID or h == -1:
        return None  # absent (or vanished between exists and open)
    try:
        fd = msvcrt.open_osfhandle(h, os.O_RDONLY | getattr(os, "O_BINARY", 0))
        with os.fdopen(fd, "rb") as f:
            return f.read()
    except (OSError, ValueError):
        try:
            ctypes.windll.kernel32.CloseHandle(h)
        except Exception:
            pass
        return None


def publish_atomic(path: Path, payload: bytes) -> None:
    """tmp file + fsync + os.replace: readers see old or complete-new, never partial."""
    fd, tmpname = tempfile.mkstemp(prefix=".tmp-TST0174-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(encode(payload))
            f.flush()
            os.fsync(f.fileno())
        last: PermissionError | None = None
        for attempt in range(40):
            try:
                os.replace(tmpname, path)
                return
            except PermissionError as exc:
                last = exc
                time.sleep(0.002 * (attempt + 1))
        raise RuntimeError(f"os.replace exhausted retries: {last}") from last
    finally:
        if os.path.exists(tmpname):
            try:
                os.unlink(tmpname)
            except OSError:
                pass


def publish_inplace(path: Path, payload: bytes) -> None:
    """MUTANT (known-broken): in-place overwrite with a visible truncation window."""
    with open(path, "wb") as f:
        f.write(encode(payload)[: max(1, len(encode(payload)) // 2)])
        f.flush()
        time.sleep(0.04)  # widened torn-write window so a paced reader cannot miss it
        f.write(encode(payload)[max(1, len(encode(payload)) // 2) :])


def writer_loop(go_dir, entry, tag: str, stop_flag) -> None:
    """Persistent writer process body: poll go dir, publish its payload per trial.

    Paths arrive as raw strings from the subprocess -c bootstrap; coerce here."""
    go_dir, entry, stop_flag = Path(go_dir), Path(entry), Path(stop_flag)
    seen: set[int] = set()
    while not stop_flag.exists():
        for g in sorted(go_dir.glob("go-*.json")):
            n = int(g.stem.split("-")[1])
            if n in seen:
                continue
            try:
                spec = json.loads(g.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue  # mid-write read; retry on a later scan
            seen.add(n)
            payload = (spec["a"] if tag == "A" else spec["b"]).encode()
            if spec.get("mode") == "inplace":
                publish_inplace(entry, payload)
            else:
                publish_atomic(entry, payload)
            try:
                (go_dir.parent / "done" / f"{n}.{tag}").touch()
            except OSError:
                pass
        time.sleep(0.0005)
