#!/usr/bin/env python3
"""Both-states control + negative control for the prose-stop recognizer."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import analyze  # noqa: E402
import stopping  # noqa: E402

ART = REPO / "command-center/design/council/CNL-0038-executable-runtime-semantics-for-the-6-deliberative-protoc.md"


def main() -> int:
    infix_ok, infix_why = stopping.is_readable("rounds >= 2 AND spoke_all == true")
    print(f"infix_control readable={infix_ok} classifier={infix_why}")
    if not infix_ok:
        print("FAILED:CNL-0038-probe2 infix path dead")
        return 1
    ctrl = analyze.both_states()
    neg = analyze.negative_control()
    print(ctrl["known_good"]["verbatim"])
    print(ctrl["planted_bad"]["verbatim"])
    print(
        f"silent_on_good={ctrl['silent_on_good']} "
        f"fires_on_bad={ctrl['fires_on_bad']} pass={ctrl['pass']}"
    )
    print(f"negative_control fire={neg['fire']} executable={neg['executable']}")
    print(f"negative_control what={neg['what_the_check_does']}")
    if not ctrl["pass"]:
        print("FAILED:CNL-0038-probe2 both-states did not discriminate")
        return 1
    if not (neg["fire"] is True and neg["executable"] is False):
        print("FAILED:CNL-0038-probe2 negative control did not reject")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    art_ctrl = doc.get("both_states") or {}
    if art_ctrl.get("pass") is not True:
        print("FAILED:CNL-0038-probe2 artifact both_states.pass")
        return 1
    if art_ctrl.get("known_good", {}).get("verbatim") != ctrl["known_good"]["verbatim"]:
        print("FAILED:CNL-0038-probe2 known-good verbatim drift")
        return 1
    if art_ctrl.get("planted_bad", {}).get("verbatim") != ctrl["planted_bad"]["verbatim"]:
        print("FAILED:CNL-0038-probe2 planted-bad verbatim drift")
        return 1
    print("SUCCESS:CNL-0038-probe2 both-states FIRE on planted-bad SILENT on known-good")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
