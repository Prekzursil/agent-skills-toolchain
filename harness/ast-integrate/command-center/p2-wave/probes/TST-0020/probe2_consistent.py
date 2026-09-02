#!/usr/bin/env python3
"""Named probe 2: consistent counts pass; failure message names the invariant; reviewer."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from reviewer import review  # noqa: E402
from tests import (  # noqa: E402
    test_consistent_counts_pass,
    test_failure_message_names_the_violated_invariant,
)

ART = REPO / "command-center/receipts/TST-0020.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:TST-0020-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0020" not in text:
        print("FAILED:TST-0020-probe2 sentinel absent")
        return 1
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:TST-0020-probe2 self-declared", doc.get("state"))
        return 1

    t2 = test_consistent_counts_pass()
    t3 = test_failure_message_names_the_violated_invariant()
    rev = review()
    if not t2["ok"]:
        print("FAILED:TST-0020-probe2 test_consistent_counts_pass")
        print(json.dumps(t2, indent=2, default=str)[:3000])
        return 1
    if not t3["ok"]:
        print("FAILED:TST-0020-probe2 test_failure_message_names_the_violated_invariant")
        print(json.dumps(t3, indent=2, default=str)[:3000])
        return 1
    if rev.get("verdict") != "PASS" or rev.get("independent") is not True:
        print("FAILED:TST-0020-probe2 reviewer")
        print(json.dumps(rev, indent=2, default=str)[:3000])
        return 1
    if rev.get("executed_both_states") is not True:
        print("FAILED:TST-0020-probe2 reviewer did not execute both states")
        return 1

    rec_rev = doc.get("reviewer") or {}
    if rec_rev.get("independent") is not True or rec_rev.get("verdict") != "PASS":
        print("FAILED:TST-0020-probe2 receipt reviewer not independent PASS")
        return 1
    if rec_rev.get("executed_both_states") is not True:
        print("FAILED:TST-0020-probe2 receipt reviewer missing executed_both_states")
        return 1

    named = t3.get("named") or []
    if len(named) < 3 or not all(row.get("ok") for row in named):
        print("FAILED:TST-0020-probe2 invariant names missing from messages")
        return 1

    payload = {
        "probe": "probe2-consistent-and-named-invariant",
        "unit_id": "TST-0020",
        "consistent_ok": True,
        "named_invariants": [row["invariant"] for row in named],
        "reviewer_verdict": rev.get("verdict"),
        "reviewer_independent": True,
        "published_on_consistent": t2.get("published_numbers"),
    }
    print(json.dumps(payload, sort_keys=True, default=str)[:4000])
    print(
        "named="
        + ",".join(row["invariant"] for row in named)
        + f" reviewer={rev.get('verdict')}"
    )
    print("SUCCESS:TST-0020-probe2 consistent-counts-and-named-invariant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
