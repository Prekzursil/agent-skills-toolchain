#!/usr/bin/env python3
"""Artifact publishers under test for TST-0146.

atomic_publish: write a sibling tmp, fsync, then os.replace onto dest.
non_atomic_publish: planted detector-control — truncating in-place write.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path


def atomic_publish(dest: Path, data: bytes) -> None:
    """Publish `data` so dest is never a readable partial."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=dest.name + ".",
        suffix=".tmp",
        dir=str(dest.parent),
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(str(tmp), str(dest))
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def non_atomic_publish(dest: Path, data: bytes) -> None:
    """Detector-control writer: truncate dest then write in place."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def _write_chunks(fh, data: bytes, pause_at: int, chunk: int) -> None:
    written = 0
    while written < len(data):
        nxt = data[written : written + chunk]
        fh.write(nxt)
        fh.flush()
        written += len(nxt)
        if pause_at > 0 and written >= pause_at:
            # Park here so the parent can SIGKILL at a known offset.
            time.sleep(30)
            return
    os.fsync(fh.fileno())


def child_atomic(dest: Path, data: bytes, pause_at: int, chunk: int, tmp_report: Path) -> None:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=dest.name + ".",
        suffix=".tmp",
        dir=str(dest.parent),
    )
    tmp = Path(tmp_name)
    # Report tmp path without Path.write_text (that call is the non-atomic tell).
    with open(str(tmp_report), "w", encoding="utf-8") as rf:
        rf.write(str(tmp) + "\n")
        rf.flush()
        os.fsync(rf.fileno())
    try:
        with os.fdopen(fd, "wb") as fh:
            _write_chunks(fh, data, pause_at, chunk)
            if pause_at <= 0 or pause_at >= len(data):
                os.replace(str(tmp), str(dest))
                return
        time.sleep(30)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def child_non_atomic(dest: Path, data: bytes, pause_at: int, chunk: int) -> None:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as fh:
        _write_chunks(fh, data, pause_at, chunk)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("role", choices=["child"])
    p.add_argument("--mode", choices=["atomic", "non_atomic"], required=True)
    p.add_argument("--dest", required=True)
    p.add_argument("--payload-file", required=True)
    p.add_argument("--pause-at", type=int, required=True)
    p.add_argument("--chunk", type=int, default=64)
    p.add_argument("--tmp-report", default="")
    ns = p.parse_args(argv)
    data = Path(ns.payload_file).read_bytes()
    dest = Path(ns.dest)
    if ns.mode == "atomic":
        if not ns.tmp_report:
            print("child-atomic needs --tmp-report", file=sys.stderr)
            return 2
        child_atomic(dest, data, ns.pause_at, ns.chunk, Path(ns.tmp_report))
    else:
        child_non_atomic(dest, data, ns.pause_at, ns.chunk)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
