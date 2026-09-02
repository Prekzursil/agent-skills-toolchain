#!/usr/bin/env python3
"""Probe 2: two-reviewer capture both-states, overlay reject, overclaim."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from capture import NEGATIVE_CONTROL_VERBATIM, capture_check  # noqa: E402
from common import OUT_REL, REPO, Reject, apply_operator_overlay, load_records, materialize_preset  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0105-probe2 {msg}")
    return 1


def main() -> int:
    rec = load_records()
    planted = capture_check(rec["capture_planted_bad"])
    clean_split = capture_check(rec["capture_known_good"])
    clean_accept = capture_check(rec["capture_dual_accept_independent"])

    if planted["fire"] is not True:
        return fail(f"planted-bad did not fire {planted}")
    needed = {"seal-broken", "rationale-clone"}
    if not needed.issubset(set(planted["reasons"])):
        return fail(f"planted reasons {planted['reasons']} missing {needed}")
    if planted["accept_blocked"] is not True:
        return fail("planted ACCEPT was not blocked")

    if clean_split["fire"] is not False:
        return fail(f"clean split fired {clean_split}")
    if clean_split["action"] != "recruit-R3":
        return fail(f"clean split action {clean_split['action']}")

    if clean_accept["fire"] is not False:
        return fail(f"independent dual-accept fired {clean_accept}")
    if clean_accept["action"] != "editor-nocapture-then-accept":
        return fail(f"dual-accept action {clean_accept['action']}")

    this = materialize_preset(rec["preset_cnl0105"])
    try:
        apply_operator_overlay(this, rec["operator_illegal_overlay"])
        return fail("illegal overlay of voting.method was accepted")
    except Reject as exc:
        overlay_msg = str(exc)
        if "voting.method" not in overlay_msg:
            return fail(f"reject message missing dial {overlay_msg}")

    out = REPO / OUT_REL
    if not out.is_file():
        return fail(f"artifact absent {OUT_REL}")
    text = out.read_text(encoding="utf-8")
    doc = json.loads(text)
    lib = doc.get("library_status") or {}
    if lib.get("on_this_tree") is True:
        return fail("overclaim: artifact asserts 12-COUNCIL is on this tree")
    if "12-COUNCIL-PROTOCOLS-AND-PRESETS.json were read" in text.lower():
        return fail("overclaim: artifact claims the library was read")
    live_planted = ((doc.get("capture") or {}).get("planted_bad") or {}).get("fire")
    live_clean = ((doc.get("capture") or {}).get("known_good_split") or {}).get("fire")
    if live_planted is not True or live_clean is not False:
        return fail(f"artifact capture drifted planted={live_planted} clean={live_clean}")
    nc = doc.get("negative_control") or {}
    if not nc.get("verbatim"):
        return fail("negative control verbatim absent")
    if "seal-broken" not in nc["verbatim"]:
        return fail("negative control verbatim missing the planted state")

    print(
        json.dumps(
            {
                "planted_fire": planted["fire"],
                "planted_reasons": planted["reasons"],
                "clean_split_fire": clean_split["fire"],
                "clean_split_action": clean_split["action"],
                "dual_accept_fire": clean_accept["fire"],
                "dual_accept_action": clean_accept["action"],
                "overlay_rejected": True,
                "library_on_this_tree": lib.get("on_this_tree"),
            },
            sort_keys=True,
        )
    )
    print("negative_control_verbatim=" + NEGATIVE_CONTROL_VERBATIM)
    print(
        f"capture planted_fire={planted['fire']} clean_silent={not clean_split['fire']} "
        f"overlay_rejected=True overclaim_ok=True"
    )
    print("SUCCESS:CNL-0105-probe2 capture both-states overlay overclaim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
