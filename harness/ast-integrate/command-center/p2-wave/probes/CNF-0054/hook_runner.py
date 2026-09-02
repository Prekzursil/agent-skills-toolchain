#!/usr/bin/env python3
"""Observable hook process: append one execution-log line, then exit as configured.

The inventory reader consumes only this log. Manifest presence is not written here.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 3:
        print("FAILED:hook-runner usage log_path payload_json", file=sys.stderr)
        return 2
    log_path = Path(sys.argv[1])
    payload = json.loads(sys.argv[2])
    exit_code = int(payload.get("exit_code", 0))
    record = {
        "seq": int(payload["seq"]),
        "hook_id": str(payload["hook_id"]),
        "event": str(payload["event"]),
        "exit_code": exit_code,
        "source": "execution-log",
        "tool": payload.get("tool"),
    }
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
        fh.flush()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
