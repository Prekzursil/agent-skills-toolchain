#!/usr/bin/env python3
"""Victim writers: non-atomic streaming vs tmp+rename atomic publish.

Streaming writes a parseable, plausible JSON object FIRST (no sentinel),
fsyncs, then rewrites with the sentinel. SIGKILL in the hold window leaves
a truncated-but-plausible file at the destination.

Atomic writes the complete document (including sentinel) to a sibling tmp
file, fsyncs, then os.replace onto the destination. SIGKILL in the hold
window leaves the destination either absent or previously complete.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

PAYLOAD = "x" * 4096
VICTIM_UNIT = "VICTIM-0088"
VICTIM_SENTINEL = "SUCCESS:VICTIM-0088"


def _doc(unit_id: str, sentinel: str | None) -> dict:
    body = {
        "unit_id": unit_id,
        "state": "SUCCESS",
        "payload": PAYLOAD,
        "looks_plausible": True,
        "note": (
            "complete artifact with typed sentinel"
            if sentinel
            else "partial artifact; sentinel not yet written"
        ),
    }
    if sentinel:
        body["sentinel"] = sentinel
    return body


def _write_json(path: Path, doc: dict) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    return len(data.encode("utf-8"))


def _mark_ready(ready: Path, token: str) -> None:
    ready.parent.mkdir(parents=True, exist_ok=True)
    ready.write_text(token + "\n", encoding="utf-8", newline="\n")


def streaming_write(
    dest: Path,
    ready: Path,
    *,
    unit_id: str = VICTIM_UNIT,
    sentinel: str = VICTIM_SENTINEL,
    hold_seconds: float = 30.0,
    complete: bool = False,
) -> None:
    _write_json(dest, _doc(unit_id, None))
    _mark_ready(ready, "partial-flushed")
    if not complete:
        time.sleep(hold_seconds)
    _write_json(dest, _doc(unit_id, sentinel))


def atomic_write(
    dest: Path,
    ready: Path,
    *,
    unit_id: str = VICTIM_UNIT,
    sentinel: str = VICTIM_SENTINEL,
    hold_seconds: float = 30.0,
    complete: bool = False,
) -> None:
    tmp = dest.with_name(dest.name + ".tmp")
    _write_json(tmp, _doc(unit_id, sentinel))
    _mark_ready(ready, "tmp-flushed")
    if not complete:
        time.sleep(hold_seconds)
    os.replace(tmp, dest)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=("streaming", "atomic"), required=True)
    p.add_argument("--dest", required=True)
    p.add_argument("--ready", required=True)
    p.add_argument("--unit-id", default=VICTIM_UNIT)
    p.add_argument("--sentinel", default=VICTIM_SENTINEL)
    p.add_argument("--hold-seconds", type=float, default=30.0)
    p.add_argument("--complete", action="store_true")
    args = p.parse_args(argv)
    dest = Path(args.dest)
    ready = Path(args.ready)
    fn = streaming_write if args.mode == "streaming" else atomic_write
    fn(
        dest,
        ready,
        unit_id=args.unit_id,
        sentinel=args.sentinel,
        hold_seconds=args.hold_seconds,
        complete=args.complete,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
