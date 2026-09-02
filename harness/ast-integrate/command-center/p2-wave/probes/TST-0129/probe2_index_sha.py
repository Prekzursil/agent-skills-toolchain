#!/usr/bin/env python3
"""Named probe 2: postcondition — index directory sha256 from a separate process.

Signal (a) is install exit+stderr (owned by probe 1). This probe owns signal (b):
spawn index_hash.py before a failed install, spawn it again after, require
byte-for-byte identical directory digest. Also requires the hasher PIDs differ
from this process. The write-partial mutant must change the digest (detector
control).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import harness as H  # noqa: E402

ART = REPO / "command-center/receipts/TST-0129.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:TST-0129-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0129" not in text:
        print("FAILED:TST-0129-probe2 sentinel absent")
        return 1
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:TST-0129-probe2 self-declared", doc.get("state"))
        return 1

    live = H.evaluate()
    parent = os.getpid()
    bh = live["blackhole"]
    empty = live["empty_index"]
    partial = live["mutant_write_partial"]

    before_pid = bh["before"]["pid"]
    after_pid = bh["after"]["pid"]
    same_sha = bh["before"]["sha256"] == bh["after"]["sha256"]
    empty_same = empty["before"]["sha256"] == empty["after"]["sha256"]
    independent = before_pid != parent and after_pid != parent
    empty_independent = empty["before"]["pid"] != parent

    summary = {
        "probe": "probe2-index-sha",
        "unit_id": "TST-0129",
        "parent_pid": parent,
        "blackhole_before_pid": before_pid,
        "blackhole_after_pid": after_pid,
        "blackhole_before_sha256": bh["before"]["sha256"],
        "blackhole_after_sha256": bh["after"]["sha256"],
        "blackhole_digest_identical": same_sha,
        "empty_digest_identical": empty_same,
        "empty_still_empty": empty["still_empty"],
        "hasher_independent": independent and empty_independent,
        "partial_mutant_changes_digest": partial["detector_rejects_mutant"],
        "partial_before_sha256": partial["before"]["sha256"],
        "partial_after_sha256": partial["after"]["sha256"],
    }
    print(json.dumps(summary, sort_keys=True))

    if not independent or not empty_independent:
        print("FAILED:TST-0129-probe2 hasher was not a separate process")
        return 1
    if not same_sha:
        print("FAILED:TST-0129-probe2 cached index digest changed after DNS failure")
        return 1
    if not empty_same or not empty["still_empty"]:
        print("FAILED:TST-0129-probe2 empty index was not left at zero bytes")
        return 1
    if not bh["assertion"]["holds"]:
        print("FAILED:TST-0129-probe2 fail-closed assertion did not hold")
        return 1
    if not partial["detector_rejects_mutant"]:
        print("FAILED:TST-0129-probe2 write-partial mutant did not change digest")
        return 1
    print("postcondition: index sha256 identical before/after failed install")
    print("SUCCESS:TST-0129-probe2 independent index digest unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
