#!/usr/bin/env python3
"""Probe 2: a planted untested blueprint turns the harness red (both-states)."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from blueprint_conformance.harness import (  # noqa: E402
    DEFAULT_LIBRARY,
    copy_library,
    register,
    run_suite,
    scaffold_blueprint,
)

PLANTED_ID = "wf.planted.untested"


def main() -> int:
    good = run_suite(DEFAULT_LIBRARY)
    silent_on_good = (not good["untested_ids"]) and good["ok"] is True and good["hand_list"] is False

    with tempfile.TemporaryDirectory(prefix="imp0231-plant-") as td:
        planted_root = copy_library(DEFAULT_LIBRARY, Path(td) / "library")
        original_ids = list(good["registry_ids"])
        rels = scaffold_blueprint(planted_root, PLANTED_ID)
        register(planted_root, PLANTED_ID, rels["blueprint"])
        # Broken state: hand-maintained list omits the planted member.
        bad = run_suite(planted_root, only_ids=original_ids)
        # Control: the same planted member is exercisable when discovered from the registry.
        live = run_suite(planted_root)

    fired_on_bad = PLANTED_ID in bad["untested_ids"] and bad["ok"] is False and bad["hand_list"] is True
    planted_valid = (
        live["ok"] is True
        and PLANTED_ID in live["exercised_ids"]
        and PLANTED_ID not in live["untested_ids"]
    )
    payload = {
        "planted_id": PLANTED_ID,
        "good_untested": good["untested_ids"],
        "bad_untested": bad["untested_ids"],
        "fired_on_bad_state": fired_on_bad,
        "silent_on_good_state": silent_on_good,
        "planted_valid_when_discovered": planted_valid,
        "live_registry_count": live["registry_count"],
        "bad_exercised": bad["exercised_ids"],
        "live_exercised": live["exercised_ids"],
        "good_suite_ok": good["ok"],
        "bad_suite_ok": bad["ok"],
        "live_suite_ok": live["ok"],
    }
    print(json.dumps(payload, indent=2))
    if not silent_on_good:
        print("FAILED:IMP-0231-probe2 good state not silent")
        return 1
    if not fired_on_bad:
        print("FAILED:IMP-0231-probe2 planted untested did not turn harness red")
        return 1
    if not planted_valid:
        print("FAILED:IMP-0231-probe2 planted member is not a valid discovered blueprint")
        return 1
    print(
        f"fired_on_bad={fired_on_bad} silent_on_good={silent_on_good} "
        f"planted={PLANTED_ID}"
    )
    print("SUCCESS:IMP-0231-probe2 planted untested blueprint detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
