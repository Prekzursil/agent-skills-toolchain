#!/usr/bin/env python3
"""Named probe 2: detector controls (truncation + retained-line timestamp rewrite).

Does not call rollback. Mutates copies of the seeded ledger so a one-line
truncation fails the prefix check as designed, and a rewritten timestamp is
visible to the prefix hash while remaining invisible to line count.
This is the independent reviewer surface required by CNF-0049.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import (  # noqa: E402
    recorded_from_artifact,
    run_timestamp_rewrite_control,
    run_truncation_control,
)

ART = REPO / "command-center/confirmation/CNF-0049-ledger-append-only.json"


def main() -> int:
    trunc = run_truncation_control()
    ts = run_timestamp_rewrite_control()
    print(json.dumps({"truncation_control": trunc, "timestamp_rewrite_control": ts}, sort_keys=True))
    if not trunc.get("prefix_check_failed_as_designed"):
        print("FAILED:CNF-0049-probe2 truncation control did not fire")
        return 1
    if trunc.get("truncated_line_count") != trunc.get("before_line_count") - 1:
        print("FAILED:CNF-0049-probe2 truncation did not drop exactly one line")
        return 1
    if not ts.get("caught_by_prefix_hash"):
        print("FAILED:CNF-0049-probe2 timestamp rewrite invisible to prefix hash")
        return 1
    if not ts.get("invisible_to_line_count"):
        print("FAILED:CNF-0049-probe2 timestamp rewrite changed line count")
        return 1
    if ts.get("line_count_before") != ts.get("line_count_after_rewrite"):
        print("FAILED:CNF-0049-probe2 line counts diverged")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0049-probe2 confirmation artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0049-probe2 self-declared {doc.get('state')}")
        return 1
    rec = recorded_from_artifact(doc)
    rec_tr = (rec["tests"] or {}).get("truncation_control") or {}
    rec_ts = (rec["tests"] or {}).get("timestamp_rewrite_control") or {}
    if rec_tr.get("prefix_check_failed_as_designed") is not True:
        print("FAILED:CNF-0049-probe2 artifact truncation control not recorded")
        return 1
    if rec_ts.get("caught_by_prefix_hash") is not True:
        print("FAILED:CNF-0049-probe2 artifact timestamp hash catch not recorded")
        return 1
    if rec_ts.get("invisible_to_line_count") is not True:
        print("FAILED:CNF-0049-probe2 artifact line-count invisibility not recorded")
        return 1
    if rec_tr.get("before_prefix_hash") and rec_tr.get("before_prefix_hash") != trunc["before_prefix_hash"]:
        print("FAILED:CNF-0049-probe2 artifact truncation before hash != live")
        return 1
    if rec_ts.get("before_prefix_hash") != ts["before_prefix_hash"]:
        print("FAILED:CNF-0049-probe2 artifact timestamp before hash != live")
        return 1
    if rec_ts.get("rewritten_prefix_hash") != ts["rewritten_prefix_hash"]:
        print("FAILED:CNF-0049-probe2 artifact rewritten hash != live")
        return 1
    verdict = rec["verdict"] or {}
    if not verdict.get("truncation_control_failed_as_designed"):
        print("FAILED:CNF-0049-probe2 verdict missing truncation control flag")
        return 1
    print(
        "truncation_fired=True timestamp_hash_caught=True "
        f"line_count_unchanged={ts['invisible_to_line_count']}"
    )
    print("SUCCESS:CNF-0049-probe2 detector controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
