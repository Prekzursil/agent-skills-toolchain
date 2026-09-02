#!/usr/bin/env python3
"""Isolated ledger rollback that may only APPEND to EVENTS.jsonl.

Product rollback of command-center state is not shipped as ROLLBACK-MANIFEST.md
on this worktree. This rehearsal is the rollback-under-test for CNF-0049: it
restores nothing by rewriting history. It records the inverse as a new event
through tools/command-center/close.py:append_event (open-append, never a
truncate-and-rewrite of the file).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import close  # noqa: E402

ROLLBACK_TS = "2026-08-24T18:00:00+00:00"
ROLLBACK_PAYLOAD: dict[str, Any] = {
    "id": "R-M08",
    "reason": "CNF-0049-isolated-rehearsal",
    "restored_disposition": None,
    "ts": ROLLBACK_TS,
    "verb": "rollback",
}


def rollback_append_only(
    events_path: Path, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    if not events_path.is_file():
        raise FileNotFoundError(f"ledger missing: {events_path}")
    before = events_path.read_bytes()
    close.append_event(payload or ROLLBACK_PAYLOAD, events_path)
    after = events_path.read_bytes()
    return {
        "events_path": str(events_path),
        "before_bytes": len(before),
        "after_bytes": len(after),
        "appended": len(after) - len(before),
        "writer": "tools/command-center/close.py:append_event",
        "mode": "open-append",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CNF-0049 append-only ledger rollback")
    parser.add_argument("--events", required=True, help="path to EVENTS.jsonl")
    parser.add_argument("--reason", default=ROLLBACK_PAYLOAD["reason"])
    args = parser.parse_args(argv)
    payload = dict(ROLLBACK_PAYLOAD)
    payload["reason"] = args.reason
    try:
        result = rollback_append_only(Path(args.events), payload)
    except (OSError, FileNotFoundError) as exc:
        print(f"FAILED:CNF-0049-rollback {exc}")
        return 1
    print(json.dumps(result, sort_keys=True))
    print("SUCCESS:CNF-0049-rollback appended")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
