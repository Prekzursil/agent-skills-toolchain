#!/usr/bin/env python3
"""Named probe 1: live grep -c || echo 0 contradiction fails the run; no number published."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from reproduce import planted_bad  # noqa: E402
from tests import test_contradictory_counts_fail_the_run  # noqa: E402

ART = REPO / "command-center/receipts/TST-0020.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:TST-0020-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0020" not in text:
        print("FAILED:TST-0020-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    if doc.get("unit_id") != "TST-0020":
        print("FAILED:TST-0020-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:TST-0020-probe1 self-declared", doc.get("state"))
        return 1

    live = planted_bad()
    t1 = test_contradictory_counts_fail_the_run()
    if not t1["ok"]:
        print("FAILED:TST-0020-probe1 test_contradictory_counts_fail_the_run")
        print(json.dumps(t1, indent=2, default=str)[:3000])
        return 1
    if not live.get("doubled_zero"):
        print("FAILED:TST-0020-probe1 grep -c || echo 0 did not print 0 then 0")
        print(json.dumps(live, indent=2, default=str)[:2000])
        return 1
    if live.get("fired") is not True or live.get("published_numbers") is not None:
        print("FAILED:TST-0020-probe1 live contradiction was not detector-failure with no number")
        print(json.dumps(live, indent=2, default=str)[:2000])
        return 1

    repro = doc.get("reproduction") or {}
    post = repro.get("post_processor") or {}
    if post.get("classification") != "detector-failure":
        print("FAILED:TST-0020-probe1 receipt did not classify reproduction as detector-failure")
        return 1
    if post.get("published_numbers") is not None:
        print("FAILED:TST-0020-probe1 receipt published a number for the contradiction")
        return 1
    if "mutex-all-hit-empty-intersection" not in (post.get("violated_invariants") or []):
        print("FAILED:TST-0020-probe1 receipt did not name mutex invariant")
        return 1

    payload = {
        "probe": "probe1-contradictory",
        "unit_id": "TST-0020",
        "doubled_zero": True,
        "raw_lines": live.get("raw_lines"),
        "naive_claims": live.get("naive_claims"),
        "classification": live.get("classification"),
        "published_numbers": live.get("published_numbers"),
        "violated": live.get("violated_invariants"),
        "test_ok": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"doubled_zero={live.get('raw_lines')} claims={live.get('naive_claims')} "
        f"published={live.get('published_numbers')}"
    )
    print("SUCCESS:TST-0020-probe1 contradictory-counts-fail-the-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
