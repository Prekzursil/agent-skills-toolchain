#!/usr/bin/env python3
"""B07 cockpit cache publisher under test for TST-0156.

Publish contract
----------------
Atomic mode (production default): write a sibling tmp, fsync, then
``os.replace`` onto the cache path. A reader of the dest path therefore
sees either the previous complete object or the new complete object.

Direct mode (mutation control): truncate-and-write the dest path in
place. A cancel mid-write can expose a truncated cache file. The
mutation must make partial reads appear; otherwise the detector is dead.

Production monitorcore / cockpit cache writers are discovered if present.
This module is the executable publisher when those paths are absent.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "TST-0156"
CACHE_NAME = "panel.cache.json"
TMP_PREFIX = ".panel.cache.json."
TMP_SUFFIX = ".tmp"
SCHEMA = 1
KIND = "b07-cockpit-panel-cache"

PRODUCTION_CANDIDATES = [
    "tools/monitorcore/cache_publish.py",
    "tools/cockpit/cache_publish.py",
    "platform/lib/monitor/cache_publish.py",
]


def production_publisher() -> str | None:
    for rel in PRODUCTION_CANDIDATES:
        if (REPO / rel).is_file():
            return rel
    return None


def tmp_path_for(dest: Path, pid: int | None = None) -> Path:
    pid = os.getpid() if pid is None else pid
    return dest.with_name(f"{TMP_PREFIX}{pid}{TMP_SUFFIX}")


def is_orphan_tmp(path: Path, dest: Path) -> bool:
    name = path.name
    return (
        path.parent == dest.parent
        and name.startswith(TMP_PREFIX)
        and name.endswith(TMP_SUFFIX)
        and name != dest.name
    )


def scavenge_orphans(cache_dir: Path, dest: Path) -> list[str]:
    removed: list[str] = []
    if not cache_dir.is_dir():
        return removed
    for child in cache_dir.iterdir():
        if is_orphan_tmp(child, dest):
            try:
                child.unlink()
                removed.append(child.name)
            except OSError:
                pass
    return removed


def scan_orphans(cache_dir: Path, dest: Path) -> list[str]:
    if not cache_dir.is_dir():
        return []
    return [p.name for p in cache_dir.iterdir() if is_orphan_tmp(p, dest)]


def encode_cache(seq: int, body: bytes) -> bytes:
    digest = hashlib.sha256(body).hexdigest()
    doc = {
        "kind": KIND,
        "schema": SCHEMA,
        "unit_id": UNIT,
        "seq": seq,
        "body_sha256": digest,
        "body_b64_len": len(body),
        "body_hex": body.hex(),
    }
    blob = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return blob + b"\n"


def classify_bytes(raw: bytes | None) -> str:
    """COMPLETE | PARTIAL | ABSENT — independent of the writer process."""
    if raw is None:
        return "ABSENT"
    if not raw:
        return "PARTIAL"
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "PARTIAL"
    if not isinstance(doc, dict):
        return "PARTIAL"
    if doc.get("kind") != KIND or doc.get("schema") != SCHEMA:
        return "PARTIAL"
    hex_body = doc.get("body_hex")
    sha = doc.get("body_sha256")
    if not isinstance(hex_body, str) or not isinstance(sha, str):
        return "PARTIAL"
    try:
        body = bytes.fromhex(hex_body)
    except ValueError:
        return "PARTIAL"
    if hashlib.sha256(body).hexdigest() != sha:
        return "PARTIAL"
    if int(doc.get("body_b64_len") or -1) != len(body):
        return "PARTIAL"
    return "COMPLETE"


def read_dest(dest: Path) -> tuple[str, int, dict[str, Any] | None]:
    if not dest.is_file():
        return "ABSENT", 0, None
    raw = dest.read_bytes()
    verdict = classify_bytes(raw)
    parsed = None
    if verdict == "COMPLETE":
        parsed = json.loads(raw.decode("utf-8"))
    return verdict, len(raw), parsed


def publish_atomic(dest: Path, payload: bytes) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = tmp_path_for(dest)
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        written = 0
        while written < len(payload):
            n = os.write(fd, payload[written:])
            if n <= 0:
                raise OSError("short write to cockpit cache tmp")
            written += n
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(str(tmp), str(dest))
    return dest


def publish_direct(dest: Path, payload: bytes) -> Path:
    """Mutation: in-place truncate + write. Cancel can expose a torn dest."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(dest), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        written = 0
        while written < len(payload):
            n = os.write(fd, payload[written:])
            if n <= 0:
                raise OSError("short write to cockpit cache dest")
            written += n
        os.fsync(fd)
    finally:
        os.close(fd)
    return dest


def _hold_loop(go: Path) -> None:
    while not go.is_file():
        time.sleep(0.002)


def writer_main(argv: list[str] | None = None) -> int:
    """Child process: write hold_after bytes, signal ready, wait, finish."""
    import argparse

    p = argparse.ArgumentParser(prog="cache_publish")
    p.add_argument("--dest", required=True)
    p.add_argument("--payload", required=True)
    p.add_argument("--mode", choices=("atomic", "direct"), required=True)
    p.add_argument("--hold-after-bytes", type=int, required=True)
    p.add_argument("--ready", required=True)
    p.add_argument("--go", required=True)
    args = p.parse_args(argv)

    dest = Path(args.dest)
    payload = Path(args.payload).read_bytes()
    hold = int(args.hold_after_bytes)
    if hold <= 0 or hold >= len(payload):
        print("FAILED:cache_publish hold_after_bytes must split the payload", file=sys.stderr)
        return 2
    dest.parent.mkdir(parents=True, exist_ok=True)
    ready = Path(args.ready)
    go = Path(args.go)
    ready.parent.mkdir(parents=True, exist_ok=True)

    if args.mode == "atomic":
        tmp = tmp_path_for(dest)
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            os.write(fd, payload[:hold])
            os.fsync(fd)
            ready.write_text("ready\n", encoding="utf-8")
            _hold_loop(go)
            rest = payload[hold:]
            written = 0
            while written < len(rest):
                n = os.write(fd, rest[written:])
                if n <= 0:
                    raise OSError("short write after go")
                written += n
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(str(tmp), str(dest))
        return 0

    fd = os.open(str(dest), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        os.write(fd, payload[:hold])
        os.fsync(fd)
        ready.write_text("ready\n", encoding="utf-8")
        _hold_loop(go)
        rest = payload[hold:]
        written = 0
        while written < len(rest):
            n = os.write(fd, rest[written:])
            if n <= 0:
                raise OSError("short write after go")
            written += n
        os.fsync(fd)
    finally:
        os.close(fd)
    return 0


# Names the harness/probes import.
encode_cache = encode_cache
publish_atomic = publish_atomic
read_dest = read_dest
scan_orphans = scan_orphans
scavenge_orphans = scavenge_orphans
production_publisher = production_publisher


if __name__ == "__main__":
    raise SystemExit(writer_main())
