#!/usr/bin/env python3
"""Probe 2: both-states leak checker + negative control.

The checker FIRES on every planted-bad fixture and is SILENT on every
known-good fixture. Negative control: name-in-dissent is the state the
check is meant to reject; the raw reasons are printed verbatim.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import anonymity as A  # noqa: E402

OUT = HERE / "probe2-both-states.raw.json"


def main() -> int:
    A.dump_fixtures()
    table = A.both_states()
    planted = A.check_bundle(A.build_fixture("bad-name-in-dissent"))
    good = A.check_bundle(A.build_fixture("good-pseudonymous"))
    doc = {
        "table": table,
        "negative_control": {
            "state_meant_to_reject": "bad-name-in-dissent",
            "fired": planted["fired"],
            "reasons": planted["reasons"],
            "verbatim": (
                "check_bundle(bad-name-in-dissent) fired="
                f"{planted['fired']} reasons={json.dumps(planted['reasons'])}"
            ),
        },
        "known_good": {
            "kind": "good-pseudonymous",
            "fired": good["fired"],
            "silent": good["silent"],
            "reasons": good["reasons"],
            "verbatim": (
                "check_bundle(good-pseudonymous) fired="
                f"{good['fired']} silent={good['silent']} reasons={json.dumps(good['reasons'])}"
            ),
        },
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"fired_on_every_bad={table['fired_on_every_bad']} silent_on_every_good={table['silent_on_every_good']}")
    for row in table["rows"]:
        print(
            f"  {row['kind']}: want_fire={row['want_fire']} fired={row['fired']} "
            f"ok={row['ok']} reasons={row['reasons']}"
        )
    print(doc["negative_control"]["verbatim"])
    print(doc["known_good"]["verbatim"])
    if not table["pass"] or not planted["fired"] or not good["silent"]:
        print("FAILED:CNL-0007-probe2 both-states did not discriminate")
        return 1
    print("SUCCESS:CNL-0007-probe2 both-states and negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
