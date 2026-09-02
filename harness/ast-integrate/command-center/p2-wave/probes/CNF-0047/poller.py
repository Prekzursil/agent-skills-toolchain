#!/usr/bin/env python3
"""Sidecar poller: writes monitor-status.json until killed. Not the ledger."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import monitor as M  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) < 5:
        print("FAILED:poller usage ledger artifact unit_id status", file=sys.stderr)
        return 2
    ledger = Path(argv[1])
    artifact = Path(argv[2])
    unit_id = argv[3]
    status = Path(argv[4])
    while True:
        doc = M.classify(
            unit_id=unit_id,
            ledger=ledger,
            artifact=artifact,
            sample_s=0.08,
        )
        status.write_text(json.dumps(doc, sort_keys=True) + "\n", encoding="utf-8")
        time.sleep(0.05)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
