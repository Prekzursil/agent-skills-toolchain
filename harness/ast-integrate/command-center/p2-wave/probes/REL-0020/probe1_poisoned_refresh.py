#!/usr/bin/env python3
"""Probe 1: empty-cache silence, poisoned-no-refresh FAIL, poisoned-refresh NEW bytes.

Re-runs the drill on fresh profiles. Also checks the receipt recorded the same
behavioural quotes (not version strings).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import drill as D  # noqa: E402
from packages import NEW_BEHAVIOUR, NEW_VERSION, OLD_BEHAVIOUR  # noqa: E402

ART = REPO / "command-center/receipts/REL-0020.json"


def main() -> int:
    empty = D.empty_cache_both_states()
    print(
        "empty_off={0} empty_on={1} silent_both={2}".format(
            empty["without_refresh"]["behaviour"],
            empty["with_refresh"]["behaviour"],
            empty["silent_in_both_states"],
        )
    )
    if not empty["silent_in_both_states"]:
        print("FAILED:REL-0020-probe1 empty-cache control did not stay silent in both states")
        return 1

    off = D.poisoned_without_refresh()
    print(
        "poison_off behaviour={0} version={1} hit={2} perceives={3}".format(
            off["behaviour"], off["version"], off["hit"], off["perceives_defect"]
        )
    )
    if not off["perceives_defect"]:
        print("FAILED:REL-0020-probe1 refresh-disabled did not observe old bytes")
        return 1
    if off["behaviour"] != OLD_BEHAVIOUR:
        print("FAILED:REL-0020-probe1 expected OLD_BEHAVIOUR quote")
        return 1
    if off["version"] != NEW_VERSION:
        print("FAILED:REL-0020-probe1 install did not write the new version sidecar")
        return 1
    if off["behaviour"] == off["version"]:
        print("FAILED:REL-0020-probe1 behaviour collapsed onto the version string")
        return 1
    if len(off["seeded"]) < 3:
        print("FAILED:REL-0020-probe1 too few cache locations seeded")
        return 1

    on = D.poisoned_with_refresh()
    print(
        "poison_on behaviour={0} version={1} hit={2} new_bytes={3}".format(
            on["behaviour"], on["version"], on["hit"], on["new_bytes_execute"]
        )
    )
    if not on["new_bytes_execute"]:
        print("FAILED:REL-0020-probe1 refresh-enabled did not execute new bytes")
        return 1
    if on["behaviour"] != NEW_BEHAVIOUR:
        print("FAILED:REL-0020-probe1 expected NEW_BEHAVIOUR quote")
        return 1
    if on["behaviour"] == on["version"]:
        print("FAILED:REL-0020-probe1 new behaviour equals version string")
        return 1

    if not ART.is_file():
        print("FAILED:REL-0020-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:REL-0020-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:REL-0020" not in ART.read_text(encoding="utf-8"):
        print("FAILED:REL-0020-probe1 sentinel absent")
        return 1
    ev = doc.get("evidence") or {}
    if ev.get("quoted_old_execution") != OLD_BEHAVIOUR:
        print("FAILED:REL-0020-probe1 receipt old quote mismatch")
        return 1
    if ev.get("quoted_new_execution") != NEW_BEHAVIOUR:
        print("FAILED:REL-0020-probe1 receipt new quote mismatch")
        return 1
    if ev.get("version_string_is_not_behaviour") is not True:
        print("FAILED:REL-0020-probe1 receipt missing version-is-not-behaviour flag")
        return 1
    ctrl = doc.get("controls") or {}
    if ctrl.get("empty_cache_silent_in_both_states") is not True:
        print("FAILED:REL-0020-probe1 receipt empty-cache control false")
        return 1
    if ctrl.get("detector_fires_when_refresh_disabled") is not True:
        print("FAILED:REL-0020-probe1 receipt detector control false")
        return 1
    ok, why = D.receipt_honest(doc)
    if not ok:
        print(f"FAILED:REL-0020-probe1 receipt_honest {why}")
        return 1
    print("SUCCESS:REL-0020-probe1 poisoned refresh drill")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
