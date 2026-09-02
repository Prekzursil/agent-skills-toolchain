#!/usr/bin/env python3
"""Probe 1: a planted divergence is found by the differential.

Live control: comment document (accept/reject) and duplicate-key document
(value) must both surface. An agreeing document must not. A value-only
detector must miss the comment plant (negative control).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from generate import PLANTED, PLANTED_COMMENT, PLANTED_DUP  # noqa: E402
from parsers import classify, is_disagreement  # noqa: E402

AGREEING = '{"ok": true, "n": 1}'


def value_only(text: str) -> dict:
    row = classify(text)
    if row.get("kind") == "value":
        return row
    row = dict(row)
    row["kind"] = None
    return row


def main() -> int:
    comment = classify(PLANTED_COMMENT)
    dup = classify(PLANTED_DUP)
    ok = classify(AGREEING)

    print(json.dumps(
        {
            "planted_comment_kind": comment.get("kind"),
            "planted_dup_kind": dup.get("kind"),
            "agreeing_kind": ok.get("kind"),
            "comment_strict_accepted": comment["strict"]["accepted"],
            "comment_lenient_accepted": comment["lenient"]["accepted"],
            "dup_strict": dup["strict"]["value"],
            "dup_lenient": dup["lenient"]["value"],
        },
        sort_keys=True,
    ))

    if not is_disagreement(comment) or comment["kind"] != "accept-reject":
        print("FAILED:TST-0121-probe1 planted comment not accept-reject")
        return 1
    if comment["strict"]["accepted"] or not comment["lenient"]["accepted"]:
        print("FAILED:TST-0121-probe1 planted comment polarity wrong")
        return 1
    if not is_disagreement(dup) or dup["kind"] != "value":
        print("FAILED:TST-0121-probe1 planted duplicate key not value disagreement")
        return 1
    if dup["strict"]["value"] == dup["lenient"]["value"]:
        print("FAILED:TST-0121-probe1 duplicate-key values unexpectedly equal")
        return 1
    if dup["lenient"]["value"].get("dup") != "first":
        print("FAILED:TST-0121-probe1 lenient was not first-wins")
        return 1
    if dup["strict"]["value"].get("dup") != "second":
        print("FAILED:TST-0121-probe1 strict was not last-wins")
        return 1
    if is_disagreement(ok):
        print("FAILED:TST-0121-probe1 agreeing document reported as finding")
        return 1

    blind = value_only(PLANTED_COMMENT)
    if is_disagreement(blind):
        print("FAILED:TST-0121-probe1 value-only detector must miss comment plant")
        return 1
    if not is_disagreement(value_only(PLANTED_DUP)):
        print("FAILED:TST-0121-probe1 value-only detector missed value plant")
        return 1

    planted_kinds = {kind for kind, _ in PLANTED}
    if planted_kinds != {"accept-reject", "value"}:
        print("FAILED:TST-0121-probe1 planted set incomplete")
        return 1

    print("negative_control value-only missed comment plant (expected)")
    print("SUCCESS:TST-0121-probe1 planted divergence found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
