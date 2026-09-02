#!/usr/bin/env python3
"""Named probe 1: live set difference both directions, matching the receipt."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import extract as E  # noqa: E402

ART = REPO / "command-center/receipts/TST-0051.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:TST-0051-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:TST-0051-probe1 unparseable {exc}")
        return 1
    if not isinstance(doc, dict):
        print("FAILED:TST-0051-probe1 not an object")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:TST-0051-probe1 self-declared {st}")
        return 1
    if "SUCCESS:TST-0051" not in text:
        print("FAILED:TST-0051-probe1 sentinel absent")
        return 1
    if doc.get("unit_id") != "TST-0051":
        print(f"FAILED:TST-0051-probe1 unit_id {doc.get('unit_id')}")
        return 1

    live = E.live_snapshot(REPO, include_canonical=True)
    diff = E.set_difference(live)
    rec_diff = doc.get("set_difference") or {}
    for key in ("policy_minus_tooling", "tooling_minus_policy"):
        if list(rec_diff.get(key) or []) != list(diff.get(key) or []):
            print(f"FAILED:TST-0051-probe1 {key} drift")
            print("live", diff.get(key))
            print("receipt", rec_diff.get(key))
            return 1
    if rec_diff.get("both_directions_printed") is not True:
        print("FAILED:TST-0051-probe1 both_directions_printed not true")
        return 1
    if list(doc.get("policy_declared") or []) != list(live["policy_declared"]):
        print("FAILED:TST-0051-probe1 policy_declared drift")
        return 1
    if list(doc.get("tooling_enforced") or []) != list(live["tooling_enforced"]):
        print("FAILED:TST-0051-probe1 tooling_enforced drift")
        return 1

    answers = doc.get("answers") or {}
    unrun = [g for g in live["policy_declared"] if g not in set(live["ran"])]
    can_skip = bool(live["allow_release"] and unrun)
    if answers.get("release_can_proceed_with_unrun_gate") is not can_skip:
        print("FAILED:TST-0051-probe1 skip-answer drift")
        return 1

    payload = {
        "policy_minus_tooling": diff["policy_minus_tooling"],
        "tooling_minus_policy": diff["tooling_minus_policy"],
        "sets_equal": diff["sets_equal"],
        "release_can_proceed_with_unrun_gate": can_skip,
        "never_run_count": len(unrun),
        "policy_count": diff["policy_count"],
        "tooling_count": diff["tooling_count"],
        "both_directions": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "policy_minus_tooling="
        + json.dumps(diff["policy_minus_tooling"])
        + " tooling_minus_policy="
        + json.dumps(diff["tooling_minus_policy"])
    )
    print("SUCCESS:TST-0051-probe1 set-difference both directions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
