#!/usr/bin/env python3
"""Slow JSONL append so a probe can SIGKILL the writer mid-record.

Two writers share one record builder and differ only in WHERE the slow bytes
land:

* ``--mode atomic`` (the shipped path) copies the published bytes to a
  ``.staging`` sibling, trickles the new line into the staging file, and only
  then ``os.replace``s it over the ledger. A kill at any point leaves the
  published file exactly as it was.
* ``--mode naive`` (the negative control) appends the same bytes straight
  into the published file, so a kill mid-line leaves a torn record that the
  per-line schema oracle must catch.

The record is a real ``run-ledger-v1`` line derived from the published chain
state, so a write that does complete is schema-conforming, not a decoy.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ledger as L  # noqa: E402

MODES = ("atomic", "naive")


def build_line(current: bytes, payload_bytes: int) -> bytes:
    """Next chain-consistent run-ledger-v1 line carrying ``payload_bytes`` of filler."""
    state = L.run_ledger_chain_state(current)
    record = {
        "kind": L.RUN_LEDGER_KIND,
        "seq": int(state["seq"]) + 1,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "actor": "kill-target",
        "unit_id": "IMP-0224",
        "phase": "7",
        "from_state": "seeded",
        "to_state": "appended",
        "correlation_id": "kill-target",
        "causality_id": "seed",
        "payload": {"filler": "x" * max(0, int(payload_bytes))},
        "prev_sha256": state["prev_sha256"],
    }
    errs = L.run_record_errors(record)
    if errs:
        raise SystemExit("kill_target built a non-conforming record: " + ", ".join(errs))
    return L.encode_run_record(record)


def trickle(fh, data: bytes, chunk_size: int, delay_s: float) -> None:
    step = max(1, int(chunk_size))
    for i in range(0, len(data), step):
        fh.write(data[i : i + step])
        fh.flush()
        if delay_s > 0:
            time.sleep(delay_s)


def write_atomic(dest: Path, line: bytes, current: bytes, chunk_size: int, delay_s: float) -> None:
    staging = dest.with_name(dest.name + ".staging")
    # Expose the staging file first so a probe can observe the in-flight write,
    # then trickle the new bytes into it; the published file is untouched until
    # the final rename.
    staging.write_bytes(current)
    time.sleep(0.05)
    with staging.open("ab") as fh:
        trickle(fh, line, chunk_size, delay_s)
    staging.replace(dest)


def write_naive(dest: Path, line: bytes, current: bytes, chunk_size: int, delay_s: float) -> None:
    if not current.endswith(b"\n") and current:
        line = b"\n" + line
    with dest.open("ab") as fh:
        trickle(fh, line, chunk_size, delay_s)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--path", required=True)
    p.add_argument("--mode", default="atomic", choices=MODES)
    p.add_argument("--payload-bytes", type=int, default=1024)
    p.add_argument("--chunk-size", type=int, default=256)
    p.add_argument("--delay-ms", type=float, default=2.0, help="sleep between chunks")
    args = p.parse_args()
    dest = Path(args.path)
    current = dest.read_bytes() if dest.is_file() else b""
    line = build_line(current, args.payload_bytes)
    delay_s = max(0.0, float(args.delay_ms)) / 1000.0
    if args.mode == "atomic":
        write_atomic(dest, line, current, args.chunk_size, delay_s)
    else:
        write_naive(dest, line, current, args.chunk_size, delay_s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
