#!/usr/bin/env python3
"""Append-only council event store (B07 persistence contract for TST-0286).

On-disk format:
  MAGIC ("CLOG1\\n") then zero or more records.
  Each record: 8-byte big-endian payload length + 32-byte sha256 + payload bytes.
  Payload is canonical JSON (sort_keys, separators=(',', ':')).

Atomic persist: write MAGIC+records to `<path>.tmp`, fsync, os.replace onto `<path>`.
A crash that leaves a truncated record is detected on load and raised as TornWriteError
rather than silently resuming from a half-written state.
"""
from __future__ import annotations

import hashlib
import json
import os
import struct
import sys
import time
from pathlib import Path
from typing import Any

MAGIC = b"CLOG1\n"
LEN_FMT = ">Q"
LEN_SIZE = 8
HASH_SIZE = 32


class StoreError(Exception):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


class TornWriteError(StoreError):
    def __init__(self, detail: str) -> None:
        super().__init__("torn-write", detail)


def _payload_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def _record_bytes(obj: Any) -> bytes:
    payload = _payload_bytes(obj)
    digest = hashlib.sha256(payload).digest()
    return struct.pack(LEN_FMT, len(payload)) + digest + payload


def encode_log(events: list[Any]) -> bytes:
    return MAGIC + b"".join(_record_bytes(e) for e in events)


def decode_log(raw: bytes) -> list[dict]:
    if not raw:
        raise TornWriteError("empty-file")
    if not raw.startswith(MAGIC):
        raise StoreError("bad-magic", f"prefix={raw[:16]!r}")
    pos = len(MAGIC)
    events: list[dict] = []
    n = len(raw)
    while pos < n:
        remaining = n - pos
        if remaining < LEN_SIZE:
            raise TornWriteError(
                f"truncated-length-prefix at offset={pos} remaining={remaining}"
            )
        (payload_len,) = struct.unpack(LEN_FMT, raw[pos : pos + LEN_SIZE])
        pos += LEN_SIZE
        if remaining - LEN_SIZE < HASH_SIZE:
            raise TornWriteError(f"truncated-checksum at offset={pos}")
        digest = raw[pos : pos + HASH_SIZE]
        pos += HASH_SIZE
        if n - pos < payload_len:
            raise TornWriteError(
                f"truncated-payload at offset={pos} want={payload_len} remaining={n - pos}"
            )
        payload = raw[pos : pos + payload_len]
        pos += payload_len
        got = hashlib.sha256(payload).digest()
        if got != digest:
            raise TornWriteError("checksum-mismatch")
        try:
            obj = json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise TornWriteError(f"unparseable-payload:{exc}") from exc
        if not isinstance(obj, dict):
            raise StoreError("non-object-event", type(obj).__name__)
        events.append(obj)
    return events


def load(path: Path) -> list[dict]:
    if not path.is_file():
        raise StoreError("missing-log", str(path))
    return decode_log(path.read_bytes())


def persist_atomic(path: Path, events: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = encode_log(events)
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        os.write(fd, blob)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(str(tmp), str(path))


def _slow_append_main(path: Path) -> int:
    """Write MAGIC + a long record, pausing after a fsynced prefix so a parent can SIGKILL."""
    payload = b"T" * 8192
    rec = struct.pack(LEN_FMT, len(payload)) + hashlib.sha256(payload).digest() + payload
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        os.write(fd, MAGIC)
        os.fsync(fd)
        prefix = rec[:24]
        os.write(fd, prefix)
        os.fsync(fd)
        time.sleep(8.0)
        os.write(fd, rec[24:])
        os.fsync(fd)
    finally:
        os.close(fd)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) == 2 and args[0] == "--slow-append":
        return _slow_append_main(Path(args[1]))
    print("usage: store.py --slow-append PATH", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
