#!/usr/bin/env python3
"""IMP-0072 probe 1: genuine log verifies; writer rejects rewrite.

Signal 1 of the catalog evidence pair: chain verification PASSES over a
genuine five-action log (publish, yank, deprecate, revoke, moderate).
Append-only: replace/overwrite/truncate are refused and the prefix bytes
do not move.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.event_chain import (  # noqa: E402
    ACTIONS,
    AppendOnlyViolation,
    EventLog,
    GENESIS_HASH,
    build_demo_log,
    verify_log,
)

RECEIPT = REPO / "command-center/receipts/IMP-0072.json"


def main() -> int:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size < 200:
        print("FAILED:IMP-0072-probe1 receipt missing")
        return 1
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if "SUCCESS:IMP-0072" not in blob:
        print("FAILED:IMP-0072-probe1 sentinel absent")
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0072-p1-") as td:
        path = Path(td) / "registry-events.jsonl"
        records = build_demo_log(path)
        clean = verify_log(path)
        if not clean.ok or clean.record_count != 5:
            print("FAILED:IMP-0072-probe1 genuine log did not verify", clean.as_dict())
            return 1
        if {r["action"] for r in records} != ACTIONS:
            print("FAILED:IMP-0072-probe1 missing action kinds", {r["action"] for r in records})
            return 1
        if records[0]["prev_hash"] != GENESIS_HASH:
            print("FAILED:IMP-0072-probe1 genesis prev_hash")
            return 1
        for i in range(1, 5):
            if records[i]["prev_hash"] != records[i - 1]["record_hash"]:
                print(f"FAILED:IMP-0072-probe1 link {i}")
                return 1

        log = EventLog(path)
        prefix = path.read_bytes()
        refused = []
        for label, call in (
            ("replace", lambda: log.replace(seq=3, payload={"message": "nope"})),
            ("overwrite", lambda: log.overwrite(seq=1)),
            ("truncate", lambda: log.truncate()),
            ("rewrite_prefix", lambda: log.rewrite_prefix()),
        ):
            try:
                call()
            except AppendOnlyViolation:
                refused.append(label)
            else:
                print(f"FAILED:IMP-0072-probe1 writer accepted {label}")
                return 1
        if path.read_bytes() != prefix:
            print("FAILED:IMP-0072-probe1 rewrite mutated prefix")
            return 1

        extra = log.append(
            action="publish",
            actor="publisher:alice",
            package_id="demo-pkg",
            version="1.0.1",
            ts="2026-08-24T17:30:00Z",
            payload={"digest": "c" * 64},
        )
        after = path.read_bytes()
        if not after.startswith(prefix):
            print("FAILED:IMP-0072-probe1 append mutated prefix")
            return 1
        if extra["prev_hash"] != records[-1]["record_hash"]:
            print("FAILED:IMP-0072-probe1 append did not chain")
            return 1
        again = verify_log(path)
        if not again.ok or again.record_count != 6:
            print("FAILED:IMP-0072-probe1 post-append verify", again.as_dict())
            return 1

    payload = {
        "pass": True,
        "probe": "probe1-untampered-and-append-only",
        "unit_id": "IMP-0072",
        "genuine_verified": True,
        "record_count": 5,
        "actions": sorted(ACTIONS),
        "rewrite_refused": refused,
        "append_preserved_prefix": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print("rewrite_refused=" + ",".join(refused) + " genuine_ok=True")
    print("SUCCESS:IMP-0072-probe1 genuine chain verifies; writer rejects rewrite")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
