#!/usr/bin/env python3
"""Probe 1: slow-but-progressing must stay SILENT; genuine stuck must FIRE.

Wall-clock on the known-good fixture is larger than on the planted-bad one, so
a duration-only heuristic would invert the labels. This probe records that
inversion-risk and asserts the ledger+cycle detector does not take it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from detector import classify_path  # noqa: E402

GOOD = HERE / "fixtures" / "known_good_slow_progress.json"
BAD = HERE / "fixtures" / "planted_bad_deadlock.json"


def main() -> int:
    good = classify_path(GOOD)
    bad = classify_path(BAD)
    good_ms = int(good.get("wall_ms") or 0)
    bad_ms = int(bad.get("wall_ms") or 0)
    errors: list[str] = []
    if good["label"] != "PROGRESSING" or good["fired"]:
        errors.append(f"known-good fired or mislabeled: {good['label']}")
    if bad["label"] != "DEADLOCKED" or not bad["fired"]:
        errors.append(f"planted-bad silent or mislabeled: {bad['label']}")
    if good_ms <= bad_ms:
        errors.append(f"wall-clock control inverted: good_ms={good_ms} bad_ms={bad_ms}")
    if not bad.get("cycle"):
        errors.append("planted-bad has no wait-for cycle")
    if not bad.get("frozen"):
        errors.append("planted-bad ledger not frozen")
    if good.get("frozen"):
        errors.append("known-good ledger frozen")
    if good["next_rung"].get("rung") is not None:
        errors.append(f"known-good climbed a rung: {good['next_rung']}")
    if bad["next_rung"].get("rung") != "recruit":
        errors.append(f"planted-bad first rung != recruit: {bad['next_rung']}")

    payload = {
        "probe": "probe1_slow_vs_stuck",
        "unit_id": "CNL-0084",
        "known_good": {
            "label": good["label"],
            "fired": good["fired"],
            "silent": good["silent"],
            "wall_ms": good_ms,
            "frozen": good["frozen"],
            "cycle": good["cycle"],
            "reason": good["reason"],
            "next_rung": good["next_rung"].get("rung"),
        },
        "planted_bad": {
            "label": bad["label"],
            "fired": bad["fired"],
            "silent": bad["silent"],
            "wall_ms": bad_ms,
            "frozen": bad["frozen"],
            "cycle": bad["cycle"],
            "reason": bad["reason"],
            "next_rung": bad["next_rung"].get("rung"),
            "trigger": bad["next_rung"].get("trigger"),
        },
        "wall_clock_would_invert": good_ms > bad_ms,
        "pass": not errors,
        "errors": errors,
    }
    print(json.dumps(payload, sort_keys=True))
    if errors:
        print("FAILED:CNL-0084-probe1 " + "; ".join(errors))
        return 1
    print(
        "slow_progress silent=True wall_ms="
        f"{good_ms} stuck FIRE=True wall_ms={bad_ms} "
        "wall_clock_would_invert=True first_rung=recruit"
    )
    print("SUCCESS:CNL-0084-probe1 slow-progress silent; stuck fires; wall-clock is not the predicate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
